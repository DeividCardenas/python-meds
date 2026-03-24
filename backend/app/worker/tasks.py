import logging
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from celery import Celery
from celery.schedules import crontab

from app.core.db import create_pricing_task_session_factory, create_task_session_factory
from app.services.cum_socrata_service import sincronizar_catalogos_cum
from app.services.invima_soda_service import sincronizar_invima_soda
from app.services.neo4j_golden_record_service import Neo4jGoldenRecordService
from app.services.legacy_import_service import procesar_archivo_legacy, procesar_invima as procesar_invima_legacy
from app.services.neo4j_proveedor_ingesta_service import Neo4jProveedorIngestaService
from app.services.pricing_integrity_service import auditar_integridad_precios_publicados
from app.services.pricing_service import procesar_archivo_proveedor
from app.services.sismed_socrata_service import sincronizar_precios_sismed
from app.worker.utils import (
    _cleanup_temp_file,
    _mark_cotizacion_failed,
    _mark_failed,
    _mark_pricing_failed,
    _run_async_safely,
)
from app.models.enums import CargaStatus
from app.models.pricing import ProveedorArchivo


celery_app = Celery(
    "meds_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

# ---------------------------------------------------------------------------
# Celery Beat – programación de tareas periódicas
#
# Día 1 a las 2:00 AM  → sincroniza catálogos CUM (INVIMA / Socrata)
# Día 2 a las 3:00 AM  → sincroniza precios SISMED (CNPMDM / Socrata)
# Día 3 a las 4:00 AM  → sincroniza malla completa INVIMA SODA (4 endpoints)
# Día 3 a las 5:00 AM  → sincroniza Golden Record SQL -> Neo4j
# Día 4 a las 6:00 AM  → auditoría de integridad precios_proveedor vs catálogo
#   El día 2 garantiza que los CUM ya estén actualizados antes de cruzar
#   la FK id_cum al insertar precios.
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule = {
    "sincronizar-catalogos-cum-mensual": {
        "task": "task_sincronizar_cum",
        "schedule": crontab(minute=0, hour=2, day_of_month=1),
    },
    "sincronizar-precios-sismed-mensual": {
        "task": "task_sincronizar_precios_sismed",
        "schedule": crontab(minute=0, hour=3, day_of_month=2),
    },
    "sincronizar-invima-soda-mensual": {
        "task": "task_sincronizar_invima_soda",
        "schedule": crontab(minute=0, hour=4, day_of_month=3),
    },
    "sincronizar-golden-record-neo4j-mensual": {
        "task": "task_sincronizar_golden_record_neo4j",
        "schedule": crontab(minute=0, hour=5, day_of_month=3),
    },
    "auditar-integridad-precios-mensual": {
        "task": "task_auditar_integridad_precios_publicados",
        "schedule": crontab(minute=0, hour=6, day_of_month=4),
    },
}
celery_app.conf.timezone = "America/Bogota"
logger = logging.getLogger(__name__)


async def _set_proveedor_archivo_status(
    archivo_id: str,
    status: CargaStatus,
    errores_log: dict[str, Any] | None = None,
) -> None:
    pricing_engine, pricing_sf = create_pricing_task_session_factory()
    try:
        archivo_uuid = UUID(archivo_id)
        async with pricing_sf() as session:
            archivo = await session.get(ProveedorArchivo, archivo_uuid)
            if archivo is None:
                return
            archivo.status = status
            if errores_log is not None:
                archivo.errores_log = errores_log
            session.add(archivo)
            await session.commit()
    finally:
        await pricing_engine.dispose()


async def _resolver_archivo_proveedor_input(
    archivo_id: str | None,
    file_path: str | None,
    column_map: dict[str, str] | None,
    proveedor: str | None,
    id_documento: str | None,
    fecha_documento: str | None,
) -> dict[str, Any]:
    """Resuelve parámetros del procesamiento Neo4j a partir de id o ruta."""
    def _normalize_neo4j_column_map(raw_map: dict[str, str]) -> dict[str, str]:
        """Adapta mapeos legacy (cum_code, descripcion, etc.) al contrato Neo4j."""
        normalized = dict(raw_map)
        aliases = {
            "cum_code": "cum",
            "precio_unitario": "precio_proveedor",
            "descripcion": "texto_original",
        }
        for old_key, new_key in aliases.items():
            if old_key in normalized and new_key not in normalized:
                normalized[new_key] = normalized[old_key]
        return normalized

    resolved: dict[str, Any] = {
        "archivo_id": archivo_id,
        "file_path": file_path,
        "column_map": _normalize_neo4j_column_map(column_map or {}),
        "proveedor": proveedor,
        "id_documento": id_documento,
        "fecha_documento": fecha_documento,
    }

    if archivo_id is None:
        if not file_path:
            raise ValueError("Se requiere archivo_id o file_path para task_procesar_archivo_proveedor_neo4j")
        if resolved["proveedor"] is None:
            resolved["proveedor"] = "DESCONOCIDO"
        if resolved["id_documento"] is None:
            resolved["id_documento"] = f"DOC-{Path(file_path).stem}"
        if resolved["fecha_documento"] is None:
            resolved["fecha_documento"] = date.today().isoformat()
        return resolved

    pricing_engine, pricing_sf = create_pricing_task_session_factory()
    try:
        archivo_uuid = UUID(archivo_id)
        async with pricing_sf() as session:
            archivo = await session.get(ProveedorArchivo, archivo_uuid)
            if archivo is None:
                raise ValueError(f"ProveedorArchivo {archivo_id} no encontrado")

            if resolved["file_path"] is None:
                resolved["file_path"] = str(Path("/app/uploads") / f"{archivo.id}_{archivo.filename}")
            if not resolved["column_map"] and archivo.mapeo_columnas:
                resolved["column_map"] = _normalize_neo4j_column_map(dict(archivo.mapeo_columnas))
            if resolved["id_documento"] is None:
                resolved["id_documento"] = str(archivo.id)
            if resolved["proveedor"] is None:
                resolved["proveedor"] = "DESCONOCIDO"
            if resolved["fecha_documento"] is None:
                resolved["fecha_documento"] = date.today().isoformat()
    finally:
        await pricing_engine.dispose()

    return resolved


@celery_app.task(name="task_procesar_archivo")
def task_procesar_archivo(carga_id: str, file_path: str) -> dict[str, Any]:
    task_engine, session_factory = create_task_session_factory()

    async def _coro() -> dict[str, Any]:
        try:
            return await procesar_archivo_legacy(carga_id, file_path, session_factory)
        finally:
            await task_engine.dispose()

    try:
        return _run_async_safely(_coro())
    except Exception as exc:  # noqa: BLE001
        _mark_failed(carga_id, exc)
        raise
    finally:
        _cleanup_temp_file(file_path)


@celery_app.task(name="task_procesar_invima")
def task_procesar_invima(carga_id: str, file_path: str) -> dict[str, Any]:
    task_engine, session_factory = create_task_session_factory()

    async def _coro() -> dict[str, Any]:
        try:
            return await procesar_invima_legacy(carga_id, file_path, session_factory)
        finally:
            await task_engine.dispose()

    try:
        return _run_async_safely(_coro())
    except Exception as exc:  # noqa: BLE001
        _mark_failed(carga_id, exc)
        raise
    finally:
        _cleanup_temp_file(file_path)


async def _sincronizar_cum() -> dict[str, Any]:
    """
    Corrutina que descarga y sincroniza los catálogos CUM desde la API Socrata.
    Crea su propio engine/session para no interferir con el engine principal.
    """
    task_engine, session_factory = create_task_session_factory()
    try:
        return await sincronizar_catalogos_cum(session_factory)
    finally:
        await task_engine.dispose()


@celery_app.task(name="task_sincronizar_cum")
def task_sincronizar_cum() -> dict[str, Any]:
    """
    Tarea Celery que sincroniza mensualmente los catálogos CUM de INVIMA
    (Vigentes, En Trámite y Vencidos) desde la API Socrata de datos.gov.co.

    Programada para ejecutarse el día 1 de cada mes a las 2:00 AM (América/Bogotá)
    mediante Celery Beat (ver beat_schedule en la configuración del worker).
    """
    try:
        return _run_async_safely(_sincronizar_cum())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error en sincronización mensual de catálogos CUM: %s", exc)
        raise


async def _procesar_archivo_proveedor_async(
    archivo_id: str, file_path: str, mapeo: dict[str, str]
) -> dict[str, Any]:
    # pricing DB: ProveedorArchivo + StagingPrecioProveedor
    pricing_engine, pricing_session_factory = create_pricing_task_session_factory()
    # catalog DB: medicamentos (for buscar_sugerencias_cum)
    catalog_engine, catalog_session_factory = create_task_session_factory()
    try:
        return await procesar_archivo_proveedor(
            archivo_id=archivo_id,
            file_path=file_path,
            mapeo=mapeo,
            session_factory=pricing_session_factory,
            catalog_session_factory=catalog_session_factory,
        )
    finally:
        await pricing_engine.dispose()
        await catalog_engine.dispose()


@celery_app.task(name="task_procesar_archivo_proveedor")
def task_procesar_archivo_proveedor(
    archivo_id: str, file_path: str, mapeo: dict[str, str]
) -> dict[str, Any]:
    """
    Tarea Celery para procesar un archivo de lista de precios de proveedor.
    Utiliza el mapeo de columnas confirmado por el usuario para extraer los
    campos estándar e insertar las filas en staging con vault JSONB completo.
    """
    try:
        return _run_async_safely(_procesar_archivo_proveedor_async(archivo_id, file_path, mapeo))
    except Exception as exc:  # noqa: BLE001
        _mark_pricing_failed(archivo_id, exc)
        raise
    finally:
        _cleanup_temp_file(file_path)


async def _procesar_archivo_proveedor_neo4j_async(
    archivo_id: str | None,
    file_path: str | None,
    column_map: dict[str, str] | None,
    proveedor: str | None,
    id_documento: str | None,
    fecha_documento: str | None,
    progress_callback: Any = None,
) -> dict[str, Any]:
    resolved = await _resolver_archivo_proveedor_input(
        archivo_id=archivo_id,
        file_path=file_path,
        column_map=column_map,
        proveedor=proveedor,
        id_documento=id_documento,
        fecha_documento=fecha_documento,
    )

    if resolved["archivo_id"] is not None:
        await _set_proveedor_archivo_status(str(resolved["archivo_id"]), CargaStatus.PROCESSING)

    try:
        parsed_date = date.fromisoformat(str(resolved["fecha_documento"]))
        with Neo4jProveedorIngestaService() as service:
            stats = service.ingestar_archivo_proveedor(
                file_path=str(resolved["file_path"]),
                id_documento=str(resolved["id_documento"]),
                proveedor=str(resolved["proveedor"]),
                fecha_documento=parsed_date,
                column_map=dict(resolved["column_map"]),
                progress_callback=progress_callback,
            )

        if resolved["archivo_id"] is not None:
            await _set_proveedor_archivo_status(
                str(resolved["archivo_id"]),
                CargaStatus.COMPLETED,
                errores_log={"neo4j_ingesta": stats},
            )
        return stats
    except Exception as exc:  # noqa: BLE001
        if resolved["archivo_id"] is not None:
            await _set_proveedor_archivo_status(
                str(resolved["archivo_id"]),
                CargaStatus.FAILED,
                errores_log={"error": f"{type(exc).__name__}: {exc}"},
            )
        raise


@celery_app.task(name="task_procesar_archivo_proveedor_neo4j", bind=True)
def task_procesar_archivo_proveedor_neo4j(
    self,
    archivo_id: str | None = None,
    file_path: str | None = None,
    column_map: dict[str, str] | None = None,
    proveedor: str | None = None,
    id_documento: str | None = None,
    fecha_documento: str | None = None,
) -> dict[str, Any]:
    """
    Procesa un archivo de proveedor contra Golden Record Neo4j.

    Puede ejecutarse con:
    - archivo_id (resuelve ruta y mapeo desde ProveedorArchivo)
    - file_path (modo directo)
    """
    try:
        def _report_progress(current: int, total: int) -> None:
            safe_total = total if total > 0 else 1
            safe_current = current if current <= safe_total else safe_total
            self.update_state(
                state="PROCESSING",
                meta={
                    "current": safe_current,
                    "total": safe_total,
                    "mensaje": f"Procesando {safe_current} de {safe_total}...",
                    "message": f"Procesando {safe_current} de {safe_total}...",
                },
            )

        self.update_state(
            state="STARTED",
            meta={
                "current": 0,
                "total": 0,
                "stage": "initializing",
                "message": "Inicializando procesamiento del archivo proveedor.",
                "mensaje": "Inicializando procesamiento del archivo proveedor.",
            },
        )
        return _run_async_safely(
            _procesar_archivo_proveedor_neo4j_async(
                archivo_id=archivo_id,
                file_path=file_path,
                column_map=column_map,
                proveedor=proveedor,
                id_documento=id_documento,
                fecha_documento=fecha_documento,
                progress_callback=_report_progress,
            )
        )
    except Exception as exc:  # noqa: BLE001
        if archivo_id:
            _mark_pricing_failed(archivo_id, exc)
        raise


async def _auditar_integridad_precios_publicados_async() -> dict[str, Any]:
    pricing_engine, pricing_sf = create_pricing_task_session_factory()
    catalog_engine, catalog_sf = create_task_session_factory()
    try:
        return await auditar_integridad_precios_publicados(
            pricing_session_factory=pricing_sf,
            catalog_session_factory=catalog_sf,
        )
    finally:
        await pricing_engine.dispose()
        await catalog_engine.dispose()


@celery_app.task(name="task_auditar_integridad_precios_publicados")
def task_auditar_integridad_precios_publicados() -> dict[str, Any]:
    try:
        return _run_async_safely(_auditar_integridad_precios_publicados_async())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error auditando integridad de precios publicados: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Hospital bulk-quotation pipeline
# ---------------------------------------------------------------------------

async def _cotizar_lista_async(
    lote_id: str,
    file_path: str,
    hospital_id: str,
) -> dict[str, Any]:
    from app.services.bulk_quote_service import cotizar_lista

    catalog_engine, catalog_sf = create_task_session_factory()
    pricing_engine, pricing_sf  = create_pricing_task_session_factory()
    try:
        return await cotizar_lista(
            file_path=file_path,
            hospital_id=hospital_id,
            lote_id=UUID(lote_id),
            catalog_session_factory=catalog_sf,
            pricing_session_factory=pricing_sf,
        )
    finally:
        await catalog_engine.dispose()
        await pricing_engine.dispose()


@celery_app.task(name="task_cotizar_medicamentos")
def task_cotizar_medicamentos(
    lote_id: str,
    file_path: str,
    hospital_id: str = "GLOBAL",
) -> dict[str, Any]:
    """
    Tarea Celery para procesar una lista de medicamentos del hospital y
    encontrar los precios más recientes por proveedor para cada uno.

    Flujo
    -----
    1. Lee el CSV/Excel con una columna 'nombre'.
    2. Por cada nombre: drug_parser → matching_engine → precios_proveedor.
    3. 'Mejor precio' = precio con fecha_publicacion más reciente.
    4. Persiste resultados en cotizaciones_lote (JSONB) y cambia status → COMPLETED.
    """
    try:
        return _run_async_safely(_cotizar_lista_async(lote_id, file_path, hospital_id))
    except Exception as exc:  # noqa: BLE001
        _mark_cotizacion_failed(lote_id, exc)
        raise
    finally:
        _cleanup_temp_file(file_path)


# ---------------------------------------------------------------------------
# Sincronización de precios SISMED (CNPMDM)
# ---------------------------------------------------------------------------


async def _sincronizar_precios_sismed_async() -> dict[str, Any]:
    """
    Corrutina que descarga y sincroniza el catálogo de precios SISMED desde
    datos.gov.co (resource 3he6-m866) usando la Catalog DB.

    Se usa la misma DB de catálogo porque la tabla precios_medicamentos tiene
    FK hacia medicamentos_cum, que vive en genhospi_catalog.
    """
    task_engine, session_factory = create_task_session_factory()
    try:
        return await sincronizar_precios_sismed(session_factory)
    finally:
        await task_engine.dispose()


@celery_app.task(name="task_sincronizar_precios_sismed")
def task_sincronizar_precios_sismed() -> dict[str, Any]:
    """
    Tarea Celery que sincroniza mensualmente los precios de medicamentos desde
    el dataset público SISMED del Ministerio de Salud (datos.gov.co).

    Programada para ejecutarse el día 2 de cada mes a las 3:00 AM
    (América/Bogotá) mediante Celery Beat, siempre después de que la tarea
    "task_sincronizar_cum" (día 1, 2:00 AM) haya actualizado medicamentos_cum.

    Implementa ON CONFLICT (id_cum, canal_mercado) DO UPDATE para upsert
    idempotente: puede ejecutarse múltiples veces sin duplicar registros.
    """
    try:
        return _run_async_safely(_sincronizar_precios_sismed_async())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error en sincronización mensual de precios SISMED: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Sincronización INVIMA SODA (4 endpoints)
# ---------------------------------------------------------------------------


async def _sincronizar_invima_soda_async() -> dict[str, Any]:
    """Corrutina que ejecuta ETL completo INVIMA SODA y carga en Catalog DB."""
    task_engine, session_factory = create_task_session_factory()
    try:
        return await sincronizar_invima_soda(
            session_factory,
            cargar_bd=True,
            retornar_dataframe=False,
            retornar_rows=False,
        )
    finally:
        await task_engine.dispose()


@celery_app.task(name="task_sincronizar_invima_soda")
def task_sincronizar_invima_soda() -> dict[str, Any]:
    """Tarea mensual para extraer vigentes/vencidos/en tramite/otros desde SODA."""
    try:
        return _run_async_safely(_sincronizar_invima_soda_async())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error en sincronización INVIMA SODA: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Sincronización Golden Record en Neo4j
# ---------------------------------------------------------------------------


async def _sincronizar_golden_record_neo4j_async() -> dict[str, Any]:
    """Construye/actualiza el Golden Record en Neo4j desde medicamentos_cum."""
    task_engine, session_factory = create_task_session_factory()
    try:
        with Neo4jGoldenRecordService() as service:
            return await service.build_golden_record(session_factory)
    finally:
        await task_engine.dispose()


@celery_app.task(name="task_sincronizar_golden_record_neo4j")
def task_sincronizar_golden_record_neo4j() -> dict[str, Any]:
    """
    Tarea Celery que sincroniza el Golden Record en Neo4j después del ETL SODA.

    Programada para correr el día 3 a las 5:00 AM (America/Bogota),
    una hora después de "task_sincronizar_invima_soda".
    """
    try:
        return _run_async_safely(_sincronizar_golden_record_neo4j_async())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error en sincronización Golden Record Neo4j: %s", exc)
        raise
