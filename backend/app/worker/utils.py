"""Infraestructura async/sync compartida por las tareas Celery del worker.

Contiene:
- _run_async_safely   — ejecuta corutinas desde contexto sync sin conflictos de event loop.
- _actualizr_estado   — actualiza el estado de CargaArchivo en DB.
- helpers _mark_*     — marcan entidades como FAILED desde contexto síncrono.
- helpers async _set_*_failed — corutinas internas usadas por los _mark_*.
- _cleanup_temp_file  — elimina TSV temporales.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.db import create_pricing_task_session_factory, create_task_session_factory
from app.models.enums import CargaStatus, CotizacionStatus
from app.models.medicamento import CargaArchivo
from app.models.pricing import ProveedorArchivo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event-loop bridge
# ---------------------------------------------------------------------------


def _run_async_safely(coro: Any) -> Any:
    """Ejecuta una corutina desde un contexto síncrono (Celery) sin conflictos
    de event loop.

    Si ya hay un loop corriendo (e.g. pytest con anyio) lanza la corutina en
    un hilo separado con su propio loop para evitar el error
    ``This event loop is already running``.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        result: dict[str, Any] = {}
        error: dict[str, Exception] = {}

        def _run_in_thread() -> None:
            local_loop = asyncio.new_event_loop()
            try:
                result["value"] = local_loop.run_until_complete(coro)
            except Exception as exc:  # noqa: BLE001
                error["value"] = exc
            finally:
                local_loop.close()

        thread = threading.Thread(target=_run_in_thread)
        thread.start()
        thread.join()
        if "value" in error:
            raise error["value"]
        return result.get("value")

    new_loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(new_loop)
        return new_loop.run_until_complete(coro)
    finally:
        new_loop.close()
        asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# Helpers de estado — async
# ---------------------------------------------------------------------------


async def _actualizar_estado(
    session_factory: Any,
    carga_uuid: UUID,
    status: CargaStatus,
    errores_log: dict[str, Any] | None = None,
) -> None:
    """Actualiza status y errores_log de un CargaArchivo dado su UUID."""
    async with session_factory() as session:
        carga = await session.get(CargaArchivo, carga_uuid)
        if carga is None:
            return
        carga.status = status
        carga.errores_log = errores_log
        session.add(carga)
        await session.commit()


async def _set_proveedor_archivo_failed(archivo_id: str, exc: Exception) -> None:
    """Corutina interna: marca ProveedorArchivo como FAILED."""
    pricing_engine, pricing_sf = create_pricing_task_session_factory()
    try:
        archivo_uuid = UUID(archivo_id)
        async with pricing_sf() as session:
            archivo = await session.get(ProveedorArchivo, archivo_uuid)
            if archivo:
                archivo.status = CargaStatus.FAILED
                archivo.errores_log = {"error": f"{type(exc).__name__}: {exc}"}
                session.add(archivo)
                await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo marcar ProveedorArchivo FAILED para %s", archivo_id)
    finally:
        await pricing_engine.dispose()


async def _set_cotizacion_lote_failed(lote_id: str, exc: Exception) -> None:
    """Corutina interna: marca CotizacionLote como FAILED."""
    from app.models.cotizacion import CotizacionLote  # import tardío para evitar ciclos

    pricing_engine, pricing_sf = create_pricing_task_session_factory()
    try:
        lote_uuid = UUID(lote_id)
        async with pricing_sf() as session:
            lote = await session.get(CotizacionLote, lote_uuid)
            if lote:
                lote.status = CotizacionStatus.FAILED.value
                lote.resumen = {"error": f"{type(exc).__name__}: {exc}"}
                session.add(lote)
                await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo marcar CotizacionLote FAILED para %s", lote_id)
    finally:
        await pricing_engine.dispose()


# ---------------------------------------------------------------------------
# Helpers de estado — síncronos (llamados desde tareas Celery)
# ---------------------------------------------------------------------------


def _mark_failed(carga_id: str, exc: Exception) -> None:
    """Marca CargaArchivo como FAILED desde contexto síncrono."""
    try:
        carga_uuid = UUID(carga_id)
    except ValueError:
        logger.warning("No se pudo parsear carga_id inválido al marcar FAILED: %s", carga_id)
        return
    task_engine = None
    try:
        task_engine, session_factory = create_task_session_factory()
        _run_async_safely(
            _actualizar_estado(
                session_factory,
                carga_uuid,
                CargaStatus.FAILED,
                errores_log={"error": f"{type(exc).__name__}: {exc}"},
            )
        )
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo actualizar estado FAILED para carga %s", carga_id)
    finally:
        if task_engine is not None:
            try:
                _run_async_safely(task_engine.dispose())
            except Exception:  # noqa: BLE001
                logger.exception("No se pudo cerrar engine temporal para carga %s", carga_id)


def _mark_pricing_failed(archivo_id: str, exc: Exception) -> None:
    """Marca ProveedorArchivo como FAILED desde contexto síncrono."""
    try:
        _run_async_safely(_set_proveedor_archivo_failed(archivo_id, exc))
    except Exception:  # noqa: BLE001
        logger.exception("Error en _mark_pricing_failed para archivo %s", archivo_id)


def _mark_cotizacion_failed(lote_id: str, exc: Exception) -> None:
    """Marca CotizacionLote como FAILED desde contexto síncrono."""
    try:
        _run_async_safely(_set_cotizacion_lote_failed(lote_id, exc))
    except Exception:  # noqa: BLE001
        logger.exception("Error en _mark_cotizacion_failed para lote %s", lote_id)


# ---------------------------------------------------------------------------
# Limpieza de archivos temporales
# ---------------------------------------------------------------------------


def _cleanup_temp_file(file_path: str) -> None:
    """Elimina archivos TSV temporales creados durante el pipeline de importación."""
    path = Path(file_path)
    if path.suffix.lower() != ".tsv" or not path.exists():
        return
    try:
        path.unlink()
    except OSError:
        logger.exception("No se pudo eliminar archivo temporal %s", file_path)
