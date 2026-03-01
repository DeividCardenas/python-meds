from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from uuid import UUID

import strawberry
from strawberry.file_uploads import Upload
from sqlmodel import select

from sqlalchemy import tuple_ as sa_tuple_

from app.core.db import AsyncSessionLocal, AsyncPricingSessionLocal
from app.models.medicamento import CargaArchivo, CargaStatus, PrecioMedicamento, PrecioReguladoCNPMDM
from app.models.pricing import ProveedorArchivo, StagingPrecioProveedor
from app.models.cotizacion import CotizacionLote
from app.services.search import buscar_medicamentos_hibrido
from app.services.pricing_service import (
    detectar_columnas,
    sugerir_mapeo_automatico,
    buscar_sugerencias_cum,
    publicar_precios_aprobados,
)
from app.services.supplier_detector import detectar_proveedor
from app.worker.tasks import task_procesar_archivo, task_procesar_invima, task_procesar_archivo_proveedor, task_cotizar_medicamentos


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
    activo: bool = True
    estado_cum: Optional[str] = None


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


@strawberry.type
class PublicarResultadoNode:
    """Result returned by the publicarPreciosProveedor mutation."""

    filas_publicadas: int
    archivo_id: strawberry.ID
    status: str


# ---------------------------------------------------------------------------
# Hospital bulk-quotation types
# ---------------------------------------------------------------------------

@strawberry.type
class PrecioItemNode:
    """One supplier price entry for a matched drug."""
    proveedor_id:        Optional[str]
    proveedor_nombre:    str
    proveedor_codigo:    Optional[str]
    precio_unitario:     Optional[float]
    precio_unidad:       Optional[float]
    precio_presentacion: Optional[float]
    porcentaje_iva:      Optional[float]
    vigente_desde:       Optional[str]
    vigente_hasta:       Optional[str]
    fecha_publicacion:   Optional[str]


@strawberry.type
class CotizacionFilaNode:
    """Per-drug result row within a bulk-quotation job."""
    nombre_input:           str
    parse_warnings:         list[str]
    match_stage:            str    # EXACT | FUZZY_INN_SAFE | SYNONYM_DICT | NO_MATCH | ERROR
    match_confidence:       float
    cum_id:                 Optional[str]
    nombre_matcheado:       Optional[str]
    forma_farmaceutica:     Optional[str]
    concentracion:          Optional[str]
    reject_reason:          Optional[str]
    inn_score:              Optional[float]
    precios_count:          int
    mejor_precio:           Optional[PrecioItemNode]
    todos_precios:          list[PrecioItemNode]
    es_regulado:            bool = False
    precio_maximo_regulado: Optional[float] = None


@strawberry.type
class ResumenCotizacionNode:
    total:       int
    con_match:   int
    sin_match:   int
    con_precio:  int
    sin_precio:  int
    tasa_match:  float
    tasa_precio: float


@strawberry.type
class CotizacionLoteNode:
    """A hospital bulk-quotation job (upload → process → results)."""
    id:               strawberry.ID
    hospital_id:      str
    filename:         str
    status:           str   # PENDING | PROCESSING | COMPLETED | FAILED
    fecha_creacion:   str
    fecha_completado: Optional[str]
    resumen:          Optional[ResumenCotizacionNode]
    filas:            Optional[list[CotizacionFilaNode]]


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


# ---------------------------------------------------------------------------
# Helper: CotizacionLote DB row → GraphQL node
# ---------------------------------------------------------------------------

def _precio_dict_to_node(d: dict) -> PrecioItemNode:
    return PrecioItemNode(
        proveedor_id=d.get("proveedor_id"),
        proveedor_nombre=d.get("proveedor_nombre") or "Desconocido",
        proveedor_codigo=d.get("proveedor_codigo"),
        precio_unitario=d.get("precio_unitario"),
        precio_unidad=d.get("precio_unidad"),
        precio_presentacion=d.get("precio_presentacion"),
        porcentaje_iva=d.get("porcentaje_iva"),
        vigente_desde=d.get("vigente_desde"),
        vigente_hasta=d.get("vigente_hasta"),
        fecha_publicacion=d.get("fecha_publicacion"),
    )


def _fila_dict_to_node(
    d: dict, regulacion_map: Optional[dict] = None
) -> CotizacionFilaNode:
    mejor_raw = d.get("mejor_precio")
    todos_raw = d.get("todos_precios") or []
    cum_id = d.get("cum_id")
    reg = (regulacion_map or {}).get(cum_id) if cum_id else None
    return CotizacionFilaNode(
        nombre_input=d.get("nombre_input", ""),
        parse_warnings=d.get("parse_warnings") or [],
        match_stage=d.get("match_stage", "ERROR"),
        match_confidence=float(d.get("match_confidence", 0.0)),
        cum_id=cum_id,
        nombre_matcheado=d.get("nombre_matcheado"),
        forma_farmaceutica=d.get("forma_farmaceutica"),
        concentracion=d.get("concentracion"),
        reject_reason=d.get("reject_reason"),
        inn_score=float(d["inn_score"]) if d.get("inn_score") is not None else None,
        precios_count=int(d.get("precios_count", 0)),
        mejor_precio=_precio_dict_to_node(mejor_raw) if mejor_raw else None,
        todos_precios=[_precio_dict_to_node(p) for p in todos_raw],
        es_regulado=reg is not None,
        precio_maximo_regulado=float(reg.precio_maximo_venta)
            if reg and reg.precio_maximo_venta is not None else None,
    )


def _lote_to_node(
    lote: CotizacionLote, regulacion_map: Optional[dict] = None
) -> CotizacionLoteNode:
    resumen_node: Optional[ResumenCotizacionNode] = None
    if lote.resumen:
        r = lote.resumen
        resumen_node = ResumenCotizacionNode(
            total=r.get("total", 0),
            con_match=r.get("con_match", 0),
            sin_match=r.get("sin_match", 0),
            con_precio=r.get("con_precio", 0),
            sin_precio=r.get("sin_precio", 0),
            tasa_match=float(r.get("tasa_match", 0.0)),
            tasa_precio=float(r.get("tasa_precio", 0.0)),
        )

    filas_nodes: Optional[list[CotizacionFilaNode]] = None
    if lote.resultado is not None:
        filas_nodes = [_fila_dict_to_node(f, regulacion_map) for f in lote.resultado]

    return CotizacionLoteNode(
        id=strawberry.ID(str(lote.id)),
        hospital_id=lote.hospital_id,
        filename=lote.filename,
        status=lote.status,
        fecha_creacion=lote.fecha_creacion.isoformat(),
        fecha_completado=lote.fecha_completado.isoformat() if lote.fecha_completado else None,
        resumen=resumen_node,
        filas=filas_nodes,
    )


async def _cargar_regulacion_cnpmdm(
    session, id_cums: list[str]
) -> dict[str, PrecioReguladoCNPMDM]:
    """
    Carga registros de precios_regulados_cnpmdm para los id_cums dados.
    Retorna dict {id_cum: PrecioReguladoCNPMDM}.
    Un medicamento está regulado si y solo si su id_cum aparece en esta tabla.
    """
    if not id_cums:
        return {}
    rows = (
        await session.exec(
            select(PrecioReguladoCNPMDM).where(
                PrecioReguladoCNPMDM.id_cum.in_(id_cums)  # type: ignore[attr-defined]
            )
        )
    ).all()
    return {row.id_cum: row for row in rows}


async def _cargar_precios_sismed(
    session, id_cums: list[str]
) -> dict[str, PrecioMedicamento]:
    """
    Carga un registro de precios_medicamentos por id_cum (canal INS preferido,
    COM como fallback).  Retorna dict {id_cum: PrecioMedicamento}.
    """
    if not id_cums:
        return {}
    rows = (
        await session.exec(
            select(PrecioMedicamento).where(
                PrecioMedicamento.id_cum.in_(id_cums)  # type: ignore[attr-defined]
            )
        )
    ).all()
    # Preferir INS sobre COM; si no hay INS tomar COM
    best: dict[str, PrecioMedicamento] = {}
    for row in rows:
        existing = best.get(row.id_cum)
        if existing is None or (row.canal_mercado == "INS" and existing.canal_mercado != "INS"):
            best[row.id_cum] = row
    return best


async def _buscar_medicamentos(
    session,
    texto: str,
    empresa: Optional[str],
    solo_activos: bool = True,
    forma_farmaceutica: Optional[str] = None,
) -> list[MedicamentoNode]:
    medicamentos = await buscar_medicamentos_hibrido(
        session,
        texto=texto,
        empresa=empresa,
        solo_activos=solo_activos,
        forma_farmaceutica=forma_farmaceutica,
    )

    id_cums = [row[3] for row in medicamentos if row[3]]
    precios_map = await _cargar_precios_sismed(session, id_cums)
    regulacion_map = await _cargar_regulacion_cnpmdm(session, id_cums)

    return [
        MedicamentoNode(
            id=strawberry.ID(str(medicamento_id)),
            nombre_limpio=nombre_limpio,
            distancia=float(distancia),
            id_cum=id_cum,
            laboratorio=laboratorio,
            forma_farmaceutica=forma_farmaceutica_val,
            registro_invima=registro_invima,
            principio_activo=principio_activo,
            precio_unitario=float(precios_map[id_cum].precio_sismed_minimo)
                if id_cum and id_cum in precios_map and precios_map[id_cum].precio_sismed_minimo is not None
                else None,
            precio_empaque=float(precios_map[id_cum].precio_sismed_maximo)
                if id_cum and id_cum in precios_map and precios_map[id_cum].precio_sismed_maximo is not None
                else None,
            es_regulado=bool(id_cum and id_cum in regulacion_map),
            precio_maximo_regulado=float(regulacion_map[id_cum].precio_maximo_venta)
                if id_cum and id_cum in regulacion_map and regulacion_map[id_cum].precio_maximo_venta is not None
                else None,
            activo=bool(activo),
            estado_cum=estado_cum,
        )
        for (
            medicamento_id,
            nombre_limpio,
            distancia,
            id_cum,
            laboratorio,
            forma_farmaceutica_val,
            registro_invima,
            principio_activo,
            activo,
            estado_cum,
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
        solo_activos: bool = True,
        forma_farmaceutica: Optional[str] = None,
    ) -> list[MedicamentoNode]:
        async with AsyncSessionLocal() as session:
            return await _buscar_medicamentos(
                session,
                texto=texto,
                empresa=empresa,
                solo_activos=solo_activos,
                forma_farmaceutica=forma_farmaceutica,
            )

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
        from app.models.medicamento import Medicamento
        pa_normalizado = principio_activo.strip().lower()
        if not pa_normalizado:
            return []
        async with AsyncSessionLocal() as session:
            stmt = (
                select(Medicamento)
                .where(safunc.lower(Medicamento.principio_activo) == pa_normalizado)
                .order_by(Medicamento.nombre_limpio)
                .limit(50)
            )
            medicamentos = (await session.exec(stmt)).all()
            id_cums = [m.id_cum for m in medicamentos if m.id_cum]
            precios_map = await _cargar_precios_sismed(session, id_cums)
            regulacion_map = await _cargar_regulacion_cnpmdm(session, id_cums)
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
                precio_unitario=float(precios_map[m.id_cum].precio_sismed_minimo)
                    if m.id_cum and m.id_cum in precios_map and precios_map[m.id_cum].precio_sismed_minimo is not None
                    else None,
                precio_empaque=float(precios_map[m.id_cum].precio_sismed_maximo)
                    if m.id_cum and m.id_cum in precios_map and precios_map[m.id_cum].precio_sismed_maximo is not None
                    else None,
                es_regulado=bool(m.id_cum and m.id_cum in regulacion_map),
                precio_maximo_regulado=float(regulacion_map[m.id_cum].precio_maximo_venta)
                    if m.id_cum and m.id_cum in regulacion_map and regulacion_map[m.id_cum].precio_maximo_venta is not None
                    else None,
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
        async with AsyncPricingSessionLocal() as session:
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

    @strawberry.field
    async def get_cotizacion(self, id: strawberry.ID) -> Optional[CotizacionLoteNode]:
        """Return the status and results of a bulk-quotation job."""
        try:
            lote_uuid = UUID(str(id))
        except ValueError:
            return None
        async with AsyncPricingSessionLocal() as session:
            lote: CotizacionLote | None = await session.get(CotizacionLote, lote_uuid)
        if lote is None:
            return None
        # Look up regulation data for all matched cum_ids
        regulacion_map: dict = {}
        if lote.resultado:
            cum_ids = [f.get("cum_id") for f in lote.resultado if f.get("cum_id")]
            if cum_ids:
                async with AsyncSessionLocal() as session:
                    regulacion_map = await _cargar_regulacion_cnpmdm(session, cum_ids)
        return _lote_to_node(lote, regulacion_map)


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

    async with AsyncPricingSessionLocal() as session:
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

        async with AsyncPricingSessionLocal() as session:
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

        async with AsyncPricingSessionLocal() as session:
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

        async with AsyncPricingSessionLocal() as session:
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

    @strawberry.mutation
    async def publicar_precios_proveedor(
        self,
        archivo_id: strawberry.ID,
    ) -> PublicarResultadoNode:
        """
        Step 4 (Publish): promote all APROBADO staging rows to the production
        ``precios_proveedor`` table in a single ACID transaction, then mark the
        ProveedorArchivo record as PUBLICADO.

        Raises if the archivo does not exist or has no APROBADO rows.
        """
        try:
            archivo_uuid = UUID(str(archivo_id))
        except ValueError:
            raise ValueError("archivo_id inválido")

        resultado = await publicar_precios_aprobados(
            str(archivo_uuid),
            AsyncPricingSessionLocal,
            catalog_session_factory=AsyncSessionLocal,
        )

        return PublicarResultadoNode(
            filas_publicadas=resultado["filas_publicadas"],
            archivo_id=archivo_id,
            status="PUBLICADO",
        )

    @strawberry.mutation
    async def iniciar_cotizacion(
        self,
        file: Upload,
        hospital_id: str = "GLOBAL",
    ) -> CotizacionLoteNode:
        """
        Start a bulk-quotation job for a hospital drug list.

        Accepts a CSV/Excel file with a 'nombre' column containing free-text
        drug names.  Creates a CotizacionLote record (status=PROCESSING) and
        dispatches a Celery background task that:
          1. Parses each drug name via drug_parser.
          2. Matches against the INVIMA catalog (matching_engine).
          3. Retrieves all supplier prices from precios_proveedor.
          4. Selects the most-recently published price as the best price.
          5. Stores results as JSONB in cotizaciones_lote.

        Poll ``getCotizacion(id)`` until status == 'COMPLETED', then call
        ``GET /cotizacion/{id}/exportar?formato=csv`` to download results.
        """
        incoming_name = (file.filename or "").replace("\0", "").strip()
        base_name = incoming_name.split("/")[-1].split("\\")[-1] or "lista.csv"
        stem, dot, extension = base_name.rpartition(".")
        if not dot:
            stem, extension = base_name, ""
        safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem) or "lista"
        safe_ext  = re.sub(r"[^a-zA-Z0-9]", "", extension)
        filename  = f"{safe_stem}.{safe_ext}" if safe_ext else safe_stem

        uploads_dir = Path("/app/uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)

        from app.models.cotizacion import CotizacionLote
        from datetime import datetime

        async with AsyncPricingSessionLocal() as session:
            lote = CotizacionLote(
                hospital_id=hospital_id,
                filename=filename,
                status="PROCESSING",
            )
            session.add(lote)
            await session.commit()
            await session.refresh(lote)

        stored_path = uploads_dir / f"{lote.id}_{filename}"
        file.file.seek(0)
        with stored_path.open("wb") as out:
            out.write(file.file.read())

        task_cotizar_medicamentos.delay(str(lote.id), str(stored_path), hospital_id)

        return CotizacionLoteNode(
            id=strawberry.ID(str(lote.id)),
            hospital_id=lote.hospital_id,
            filename=lote.filename,
            status=lote.status,
            fecha_creacion=lote.fecha_creacion.isoformat(),
            fecha_completado=None,
            resumen=None,
            filas=None,
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)

