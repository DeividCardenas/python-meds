import logging
import os
from typing import Any
from uuid import UUID

from celery import Celery
from celery.schedules import crontab

from app.core.db import create_pricing_task_session_factory, create_task_session_factory
from app.services.cum_socrata_service import sincronizar_catalogos_cum
from app.services.legacy_import_service import procesar_archivo_legacy, procesar_invima as procesar_invima_legacy
from app.services.pricing_service import procesar_archivo_proveedor
from app.services.sismed_socrata_service import sincronizar_precios_sismed
from app.worker.utils import (
    _cleanup_temp_file,
    _mark_cotizacion_failed,
    _mark_failed,
    _mark_pricing_failed,
    _run_async_safely,
)


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
}
celery_app.conf.timezone = "America/Bogota"
logger = logging.getLogger(__name__)


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
