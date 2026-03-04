from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from uuid import UUID

import strawberry
from strawberry.file_uploads import Upload
from sqlmodel import select

from app.core.db import AsyncSessionLocal, AsyncPricingSessionLocal
from app.models.enums import CargaStatus
from app.models.pricing import ProveedorArchivo
from app.services.upload_service import (
    registrar_carga_catalogo,
    registrar_carga_proveedor,
    registrar_carga_cotizacion,
)
from app.services.pricing_service import (
    detectar_columnas,
    sugerir_mapeo_automatico,
    publicar_precios_aprobados,
)
from app.services.supplier_detector import detectar_proveedor
from app.repositories import staging_repo
from app.worker.tasks import (
    task_procesar_archivo,
    task_procesar_invima,
    task_procesar_archivo_proveedor,
    task_cotizar_medicamentos,
    task_sincronizar_cum,
    task_sincronizar_precios_sismed,
)
from app.graphql.types.medicamento import CargaArchivoNode
from app.graphql.types.pricing import (
    ProveedorArchivoNode,
    StagingFilaNode,
    PublicarResultadoNode,
    MapeoColumnasInput,
)
from app.graphql.types.cotizacion import CotizacionLoteNode
from app.graphql.types.sync import SincronizacionTareaNode, SincronizacionCatalogosNode


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def subir_archivo(self, file: Upload) -> CargaArchivoNode:
        carga, stored_path = await registrar_carga_catalogo(
            file, AsyncSessionLocal, max_size_bytes=10 * 1024 * 1024
        )
        task_procesar_archivo.delay(str(carga.id), str(stored_path))
        status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
        return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)

    @strawberry.mutation
    async def cargar_maestro_invima(self, file: Upload) -> CargaArchivoNode:
        carga, stored_path = await registrar_carga_catalogo(
            file, AsyncSessionLocal, max_size_bytes=None
        )
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
        archivo, stored_path = await registrar_carga_proveedor(file, AsyncPricingSessionLocal)
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
            fila = await staging_repo.aprobar_fila(session, staging_uuid, id_cum)
            if fila is None:
                raise ValueError(f"StagingPrecioProveedor {staging_id} no encontrado")

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
        lote, stored_path = await registrar_carga_cotizacion(
            file, AsyncPricingSessionLocal, hospital_id=hospital_id
        )

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

    @strawberry.mutation
    async def sincronizar_catalogos(
        self,
        incluir_sismed: bool = True,
    ) -> SincronizacionCatalogosNode:
        """
        Dispara de forma inmediata la sincronización del catálogo CUM (INVIMA)
        y, opcionalmente, los precios SISMED desde datos.gov.co.

        Las tareas corren en segundo plano en el worker Celery.  Esta mutation
        retorna de inmediato con los IDs de tarea para que el cliente pueda
        hacer polling si lo necesita.

        - incluirSismed: si es False solo lanza la sincronización CUM.
        """
        cum_task = task_sincronizar_cum.delay()
        cum_node = SincronizacionTareaNode(
            tarea="task_sincronizar_cum",
            task_id=str(cum_task.id),
            mensaje="Sincronización CUM (INVIMA / datos.gov.co) despachada al worker.",
        )

        if incluir_sismed:
            sismed_task = task_sincronizar_precios_sismed.delay()
            sismed_node = SincronizacionTareaNode(
                tarea="task_sincronizar_precios_sismed",
                task_id=str(sismed_task.id),
                mensaje="Sincronización SISMED (precios / datos.gov.co) despachada al worker.",
            )
        else:
            sismed_node = SincronizacionTareaNode(
                tarea="task_sincronizar_precios_sismed",
                task_id="skipped",
                mensaje="Sincronización SISMED omitida por parámetro incluirSismed=false.",
            )

        return SincronizacionCatalogosNode(cum=cum_node, sismed=sismed_node)
