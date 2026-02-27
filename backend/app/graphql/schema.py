from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from uuid import UUID

import strawberry
from strawberry.file_uploads import Upload
from sqlmodel import select

from app.core.db import AsyncSessionLocal
from app.models.medicamento import CargaArchivo, CargaStatus
from app.models.pricing import ProveedorArchivo, StagingPrecioProveedor
from app.services.search import buscar_medicamentos_hibrido
from app.services.pricing_service import (
    detectar_columnas,
    sugerir_mapeo_automatico,
    buscar_sugerencias_cum,
)
from app.services.supplier_detector import detectar_proveedor
from app.worker.tasks import task_procesar_archivo, task_procesar_invima, task_procesar_archivo_proveedor


@strawberry.type
class MedicamentoNode:
    id: strawberry.ID
    nombre_limpio: str
    distancia: float
    id_cum: Optional[str]
    laboratorio: Optional[str]
    forma_farmaceutica: Optional[str]
    registro_invima: Optional[str]
    principio_activo: Optional[str]
    precio_unitario: Optional[float] = None
    precio_empaque: Optional[float] = None
    es_regulado: bool = False
    precio_maximo_regulado: Optional[float] = None


@strawberry.type
class CargaArchivoNode:
    id: strawberry.ID
    filename: str
    status: str


# ---------------------------------------------------------------------------
# Supplier pricing pipeline types
# ---------------------------------------------------------------------------

@strawberry.type
class SugerenciaCUMNode:
    id_cum: str
    nombre: str
    score: float
    principio_activo: Optional[str]
    laboratorio: Optional[str]


@strawberry.type
class ProveedorArchivoNode:
    id: strawberry.ID
    filename: str
    status: str
    columnas_detectadas: Optional[list[str]]
    mapeo_sugerido: Optional[str]  # JSON-encoded dict of auto-detected mapping


@strawberry.type
class StagingFilaNode:
    id: strawberry.ID
    fila_numero: int
    cum_code: Optional[str]
    precio_unitario: Optional[float]
    precio_unidad: Optional[float]
    precio_presentacion: Optional[float]
    porcentaje_iva: Optional[float]
    descripcion_raw: Optional[str]
    estado_homologacion: str
    sugerencias_cum: Optional[str]  # JSON-encoded list
    datos_raw: str  # JSON-encoded dict
    # Pillar 3: missing-date flag
    fecha_vigencia_indefinida: bool = False
    # Pillar 4: normalised confidence score ∈ [0,1]
    confianza_score: Optional[float] = None


@strawberry.input
class MapeoColumnasInput:
    cum_code: Optional[str] = None
    precio_unitario: Optional[str] = None
    precio_unidad: Optional[str] = None
    precio_presentacion: Optional[str] = None
    porcentaje_iva: Optional[str] = None
    descripcion: Optional[str] = None
    vigente_desde: Optional[str] = None
    vigente_hasta: Optional[str] = None


async def _buscar_medicamentos(session, texto: str, empresa: Optional[str]) -> list[MedicamentoNode]:
    medicamentos = await buscar_medicamentos_hibrido(session, texto=texto, empresa=empresa)
    return [
        MedicamentoNode(
            id=strawberry.ID(str(medicamento_id)),
            nombre_limpio=nombre_limpio,
            distancia=float(distancia),
            id_cum=id_cum,
            laboratorio=laboratorio,
            forma_farmaceutica=forma_farmaceutica,
            registro_invima=registro_invima,
            principio_activo=principio_activo,
            precio_unitario=None,
            precio_empaque=None,
            es_regulado=False,
            precio_maximo_regulado=None,
        )
        for (
            medicamento_id,
            nombre_limpio,
            distancia,
            id_cum,
            laboratorio,
            forma_farmaceutica,
            registro_invima,
            principio_activo,
            _rank,
        ) in medicamentos
    ]


@strawberry.type
class Query:
    @strawberry.field
    async def buscar_medicamentos(
        self,
        texto: str,
        empresa: Optional[str] = None,
    ) -> list[MedicamentoNode]:
        async with AsyncSessionLocal() as session:
            return await _buscar_medicamentos(session, texto=texto, empresa=empresa)

    @strawberry.field
    async def get_status_carga(self, id: strawberry.ID) -> Optional[CargaArchivoNode]:
        try:
            carga_id = UUID(str(id))
        except ValueError:
            return None
        async with AsyncSessionLocal() as session:
            carga = (
                await session.exec(select(CargaArchivo).where(CargaArchivo.id == carga_id))
            ).first()
            if carga is None:
                return None
            status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
            return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)

    @strawberry.field
    async def comparativa_precios(self, principio_activo: str) -> list[MedicamentoNode]:
        """Return all medications sharing the same principio_activo for price comparison."""
        from sqlalchemy import func as safunc
        pa_normalizado = principio_activo.strip().lower()
        if not pa_normalizado:
            return []
        async with AsyncSessionLocal() as session:
            from app.models.medicamento import Medicamento
            stmt = (
                select(Medicamento)
                .where(safunc.lower(Medicamento.principio_activo) == pa_normalizado)
                .order_by(Medicamento.nombre_limpio)
                .limit(50)
            )
            medicamentos = (await session.exec(stmt)).all()
        return [
            MedicamentoNode(
                id=strawberry.ID(str(m.id)),
                nombre_limpio=m.nombre_limpio,
                distancia=0.0,
                id_cum=m.id_cum,
                laboratorio=m.laboratorio,
                forma_farmaceutica=m.forma_farmaceutica,
                registro_invima=m.registro_invima,
                principio_activo=m.principio_activo,
                precio_unitario=None,
                precio_empaque=None,
                es_regulado=False,
                precio_maximo_regulado=None,
            )
            for m in medicamentos
        ]

    @strawberry.field
    async def sugerencias_cum(self, texto: str) -> list[SugerenciaCUMNode]:
        """Return up to 3 CUM code suggestions for a free-text description."""
        async with AsyncSessionLocal() as session:
            sugerencias = await buscar_sugerencias_cum(session, texto, limite=3)
        return [
            SugerenciaCUMNode(
                id_cum=s["id_cum"],
                nombre=s["nombre"],
                score=s["score"],
                principio_activo=s.get("principio_activo"),
                laboratorio=s.get("laboratorio"),
            )
            for s in sugerencias
        ]

    @strawberry.field
    async def get_staging_filas(self, archivo_id: strawberry.ID) -> list[StagingFilaNode]:
        """Return all staging rows for a given supplier file upload."""
        try:
            archivo_uuid = UUID(str(archivo_id))
        except ValueError:
            return []
        async with AsyncSessionLocal() as session:
            filas = (
                await session.exec(
                    select(StagingPrecioProveedor)
                    .where(StagingPrecioProveedor.archivo_id == archivo_uuid)
                    .order_by(StagingPrecioProveedor.fila_numero)
                )
            ).all()
        return [
            StagingFilaNode(
                id=strawberry.ID(str(fila.id)),
                fila_numero=fila.fila_numero,
                cum_code=fila.cum_code,
                precio_unitario=float(fila.precio_unitario) if fila.precio_unitario is not None else None,
                precio_unidad=float(fila.precio_unidad) if fila.precio_unidad is not None else None,
                precio_presentacion=float(fila.precio_presentacion) if fila.precio_presentacion is not None else None,
                porcentaje_iva=float(fila.porcentaje_iva) if fila.porcentaje_iva is not None else None,
                descripcion_raw=fila.descripcion_raw,
                estado_homologacion=fila.estado_homologacion,
                sugerencias_cum=json.dumps(fila.sugerencias_cum) if fila.sugerencias_cum else None,
                datos_raw=json.dumps(fila.datos_raw),
                fecha_vigencia_indefinida=bool(fila.fecha_vigencia_indefinida),
                confianza_score=float(fila.confianza_score) if fila.confianza_score is not None else None,
            )
            for fila in filas
        ]


async def _registrar_carga(file: Upload, max_size_bytes: int | None = None) -> tuple[CargaArchivo, Path]:
    if max_size_bytes is not None:
        current_offset = file.file.tell()
        file.file.seek(0, 2)
        if file.file.tell() > max_size_bytes:
            file.file.seek(current_offset)
            raise ValueError("El archivo excede el tamaño máximo permitido (10MB).")
        file.file.seek(current_offset)

    incoming_name = (file.filename or "").replace("\0", "").strip()
    base_name = incoming_name.split("/")[-1].split("\\")[-1]
    if base_name in {"", ".", ".."}:
        base_name = "upload.bin"

    stem, dot, extension = base_name.rpartition(".")
    if not dot:
        stem, extension = base_name, ""

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem) or "upload"
    safe_extension = re.sub(r"[^a-zA-Z0-9]", "", extension)
    filename = f"{safe_stem}.{safe_extension}" if safe_extension else safe_stem
    uploads_dir = Path("/app/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        carga = CargaArchivo(filename=filename, status=CargaStatus.PENDING)
        session.add(carga)
        await session.commit()
        await session.refresh(carga)

    stored_path = uploads_dir / f"{carga.id}_{filename}"
    file.file.seek(0)
    with stored_path.open("wb") as output_file:
        output_file.write(file.file.read())

    return carga, stored_path


async def _guardar_archivo_proveedor(
    file: Upload, max_size_bytes: int | None = 10 * 1024 * 1024
) -> tuple[ProveedorArchivo, Path]:
    """Save an uploaded supplier file and create a ProveedorArchivo record."""
    if max_size_bytes is not None:
        current_offset = file.file.tell()
        file.file.seek(0, 2)
        if file.file.tell() > max_size_bytes:
            file.file.seek(current_offset)
            raise ValueError("El archivo excede el tamaño máximo permitido (10MB).")
        file.file.seek(current_offset)

    incoming_name = (file.filename or "").replace("\0", "").strip()
    base_name = incoming_name.split("/")[-1].split("\\")[-1]
    if base_name in {"", ".", ".."}:
        base_name = "upload.bin"

    stem, dot, extension = base_name.rpartition(".")
    if not dot:
        stem, extension = base_name, ""

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem) or "upload"
    safe_extension = re.sub(r"[^a-zA-Z0-9]", "", extension)
    filename = f"{safe_stem}.{safe_extension}" if safe_extension else safe_stem
    uploads_dir = Path("/app/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        archivo = ProveedorArchivo(filename=filename, status=CargaStatus.PENDING)
        session.add(archivo)
        await session.commit()
        await session.refresh(archivo)

    stored_path = uploads_dir / f"{archivo.id}_{filename}"
    file.file.seek(0)
    with stored_path.open("wb") as output_file:
        output_file.write(file.file.read())

    return archivo, stored_path


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def subir_archivo(self, file: Upload) -> CargaArchivoNode:
        carga, stored_path = await _registrar_carga(file, max_size_bytes=10 * 1024 * 1024)
        task_procesar_archivo.delay(str(carga.id), str(stored_path))
        status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
        return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)

    @strawberry.mutation
    async def cargar_maestro_invima(self, file: Upload) -> CargaArchivoNode:
        carga, stored_path = await _registrar_carga(file)
        task_procesar_invima.delay(str(carga.id), str(stored_path))
        status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
        return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)

    @strawberry.mutation
    async def subir_archivo_proveedor(self, file: Upload) -> ProveedorArchivoNode:
        """
        Step 1 of the supplier ETL: upload the price-list file.
        Returns the detected column headers and an auto-suggested mapping
        so the user can review and adjust in the frontend.

        Pillar 2: The supplier is also auto-identified from the filename and
        header fingerprint; the detected ``proveedor_id`` is persisted when a
        matching ``Proveedor`` record exists in the database.
        """
        archivo, stored_path = await _guardar_archivo_proveedor(file)
        columnas = detectar_columnas(str(stored_path))
        mapeo_sugerido = sugerir_mapeo_automatico(columnas)

        # Pillar 2 – Auto-detect supplier from filename + column fingerprint
        deteccion = detectar_proveedor(archivo.filename, columnas)

        async with AsyncSessionLocal() as session:
            db_archivo = await session.get(ProveedorArchivo, archivo.id)
            if db_archivo:
                db_archivo.columnas_detectadas = columnas
                db_archivo.mapeo_columnas = mapeo_sugerido

                # Resolve proveedor_id when the detected supplier exists in DB
                if deteccion.proveedor_codigo:
                    from app.models.pricing import Proveedor
                    proveedor = (
                        await session.exec(
                            select(Proveedor).where(Proveedor.codigo == deteccion.proveedor_codigo)
                        )
                    ).first()
                    if proveedor:
                        db_archivo.proveedor_id = proveedor.id

                session.add(db_archivo)
                await session.commit()

        return ProveedorArchivoNode(
            id=strawberry.ID(str(archivo.id)),
            filename=archivo.filename,
            status=CargaStatus.PENDING.value,
            columnas_detectadas=columnas,
            mapeo_sugerido=json.dumps(mapeo_sugerido),
        )

    @strawberry.mutation
    async def confirmar_mapeo_proveedor(
        self,
        archivo_id: strawberry.ID,
        mapeo: MapeoColumnasInput,
    ) -> ProveedorArchivoNode:
        """
        Step 2: user confirms (or corrects) the column mapping.
        Triggers background ETL to stage all rows with JSONB vault.
        """
        try:
            archivo_uuid = UUID(str(archivo_id))
        except ValueError:
            raise ValueError("archivo_id inválido")

        mapeo_dict: dict[str, str] = {}
        if mapeo.cum_code:
            mapeo_dict["cum_code"] = mapeo.cum_code
        if mapeo.precio_unitario:
            mapeo_dict["precio_unitario"] = mapeo.precio_unitario
        if mapeo.precio_unidad:
            mapeo_dict["precio_unidad"] = mapeo.precio_unidad
        if mapeo.precio_presentacion:
            mapeo_dict["precio_presentacion"] = mapeo.precio_presentacion
        if mapeo.porcentaje_iva:
            mapeo_dict["porcentaje_iva"] = mapeo.porcentaje_iva
        if mapeo.descripcion:
            mapeo_dict["descripcion"] = mapeo.descripcion
        if mapeo.vigente_desde:
            mapeo_dict["vigente_desde"] = mapeo.vigente_desde
        if mapeo.vigente_hasta:
            mapeo_dict["vigente_hasta"] = mapeo.vigente_hasta

        async with AsyncSessionLocal() as session:
            archivo = await session.get(ProveedorArchivo, archivo_uuid)
            if archivo is None:
                raise ValueError(f"ProveedorArchivo {archivo_id} no encontrado")
            archivo.mapeo_columnas = mapeo_dict
            session.add(archivo)
            await session.commit()
            await session.refresh(archivo)

        uploads_dir = Path("/app/uploads")
        stored_path = next(uploads_dir.glob(f"{archivo_uuid}_*"), None)
        if stored_path is None:
            raise FileNotFoundError(f"No se encontró el archivo para {archivo_uuid}")

        task_procesar_archivo_proveedor.delay(str(archivo_uuid), str(stored_path), mapeo_dict)

        return ProveedorArchivoNode(
            id=strawberry.ID(str(archivo.id)),
            filename=archivo.filename,
            status=CargaStatus.PENDING.value,
            columnas_detectadas=archivo.columnas_detectadas,
            mapeo_sugerido=json.dumps(mapeo_dict),
        )

    @strawberry.mutation
    async def aprobar_staging_fila(
        self,
        staging_id: strawberry.ID,
        id_cum: str,
    ) -> StagingFilaNode:
        """
        Step 3 (human-in-the-loop): approve a specific staging row by assigning
        a CUM code selected from the suggestions (or entered manually).
        """
        try:
            staging_uuid = UUID(str(staging_id))
        except ValueError:
            raise ValueError("staging_id inválido")

        async with AsyncSessionLocal() as session:
            fila = await session.get(StagingPrecioProveedor, staging_uuid)
            if fila is None:
                raise ValueError(f"StagingPrecioProveedor {staging_id} no encontrado")
            fila.cum_code = id_cum.strip()
            fila.estado_homologacion = "APROBADO"
            session.add(fila)
            await session.commit()
            await session.refresh(fila)

        return StagingFilaNode(
            id=strawberry.ID(str(fila.id)),
            fila_numero=fila.fila_numero,
            cum_code=fila.cum_code,
            precio_unitario=float(fila.precio_unitario) if fila.precio_unitario is not None else None,
            precio_unidad=float(fila.precio_unidad) if fila.precio_unidad is not None else None,
            precio_presentacion=float(fila.precio_presentacion) if fila.precio_presentacion is not None else None,
            porcentaje_iva=float(fila.porcentaje_iva) if fila.porcentaje_iva is not None else None,
            descripcion_raw=fila.descripcion_raw,
            estado_homologacion=fila.estado_homologacion,
            sugerencias_cum=json.dumps(fila.sugerencias_cum) if fila.sugerencias_cum else None,
            datos_raw=json.dumps(fila.datos_raw),
            fecha_vigencia_indefinida=bool(fila.fecha_vigencia_indefinida),
            confianza_score=float(fila.confianza_score) if fila.confianza_score is not None else None,
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)

