import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import polars as pl

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select

from app.core.db import create_task_session_factory
from app.models.medicamento import CargaArchivo, CargaStatus, Medicamento, PrecioReferencia
from app.services.cum_socrata_service import sincronizar_catalogos_cum
from app.services.invima_service import procesar_maestro_invima


celery_app = Celery(
    "meds_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)

# ---------------------------------------------------------------------------
# Celery Beat – programación de tareas periódicas
# El catálogo CUM se sincroniza el día 1 de cada mes a las 2:00 AM.
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule = {
    "sincronizar-catalogos-cum-mensual": {
        "task": "task_sincronizar_cum",
        "schedule": crontab(minute=0, hour=2, day_of_month=1),
    },
}
celery_app.conf.timezone = "America/Bogota"
logger = logging.getLogger(__name__)


MIN_NAME_LENGTH = 3
REJECTED_NAME_TERMS = ("PENDIENTE", "INSUMO", "VARIOS")
COMPANY_COLUMNS = ("Empresa", "empresa", "Laboratorio", "laboratorio", "Fuente", "fuente")
PRICE_COLUMNS = ("Precio", "precio")
FU_COLUMNS = ("FU", "fu")
VPC_COLUMNS = ("VPC", "vpc")
NAME_COLUMNS = ("nombre_limpio", "Producto", "producto", "Nombre", "nombre")
REPORT_DIR = Path(os.getenv("REJECTION_REPORT_DIR", "/app/output"))
ID_CUM_COST_COLUMNS = ("id_cum", "ID_CUM", "cum", "CUM")
PRECIO_UNITARIO_COST_COLUMNS = ("precio_unitario", "precio unitario", "precio")
PRECIO_EMPAQUE_COST_COLUMNS = ("precio_empaque", "precio empaque")
ES_REGULADO_COST_COLUMNS = ("es_regulado", "regulado")
PRECIO_MAXIMO_COST_COLUMNS = ("precio_maximo", "precio_maximo_regulado", "precio maximo")


def _pick_existing_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _normalize_decimal(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_bool(value: Any) -> bool:
    if value is None:
        return False
    normalized = str(value).strip().upper()
    return normalized in {"SI", "SÍ", "YES", "TRUE", "1"}


def _es_nombre_valido(nombre: str) -> bool:
    nombre_limpio = nombre.strip()
    if len(nombre_limpio) < MIN_NAME_LENGTH:
        return False
    nombre_upper = nombre_limpio.upper()
    return not any(term in nombre_upper for term in REJECTED_NAME_TERMS)


def _read_dataframe(file_path: str) -> pl.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pl.read_excel(path)
    if suffix in {".tsv", ".txt"}:
        return pl.read_csv(path, separator="\t")
    return pl.read_csv(path)


def _construir_upsert_costos(rows: list[dict[str, Any]]):
    statement = pg_insert(Medicamento).values(rows)
    return statement.on_conflict_do_update(
        index_elements=[Medicamento.id_cum],
        set_={
            "precio_unitario": statement.excluded.precio_unitario,
            "precio_empaque": statement.excluded.precio_empaque,
            "es_regulado": statement.excluded.es_regulado,
            "precio_maximo_regulado": statement.excluded.precio_maximo_regulado,
        },
    )


async def _actualizar_estado(
    session_factory: Any,
    carga_uuid: UUID,
    status: CargaStatus,
    errores_log: dict[str, Any] | None = None,
) -> None:
    async with session_factory() as session:
        carga = await session.get(CargaArchivo, carga_uuid)
        if carga is None:
            return
        carga.status = status
        carga.errores_log = errores_log
        session.add(carga)
        await session.commit()


async def _procesar_archivo(carga_id: str, file_path: str) -> dict[str, Any]:
    carga_uuid = UUID(carga_id)
    task_engine, session_factory = create_task_session_factory()
    try:
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.PROCESSING)
        if not Path(file_path).exists():
            raise FileNotFoundError(f"No existe el archivo a procesar: {file_path}")
        dataframe = _read_dataframe(file_path)
        columns = dataframe.columns
        name_column = _pick_existing_column(columns, NAME_COLUMNS)
        company_column = _pick_existing_column(columns, COMPANY_COLUMNS)
        price_column = _pick_existing_column(columns, PRICE_COLUMNS)
        fu_column = _pick_existing_column(columns, FU_COLUMNS)
        vpc_column = _pick_existing_column(columns, VPC_COLUMNS)

        if name_column is None:
            raise ValueError("No se encontró columna de nombre de medicamento.")
        if company_column is None:
            raise ValueError("No se encontró columna de empresa.")

        rejected_rows: list[dict[str, Any]] = []
        valid_rows: list[dict[str, Any]] = []
        for row in dataframe.to_dicts():
            nombre_raw = row.get(name_column)
            empresa_raw = row.get(company_column)
            nombre = "" if nombre_raw is None else str(nombre_raw).strip()
            empresa = "" if empresa_raw is None else str(empresa_raw).strip()
            precio = _normalize_decimal(row.get(price_column)) if price_column else None
            fu = _normalize_decimal(row.get(fu_column)) if fu_column else None
            vpc = _normalize_decimal(row.get(vpc_column)) if vpc_column else None

            rejection_reasons: list[str] = []
            if not _es_nombre_valido(nombre):
                rejection_reasons.append("Nombre Inválido")
            if precio is None or precio <= 0:
                rejection_reasons.append("Precio Cero o Nulo")
            if not empresa:
                rejection_reasons.append("Empresa Vacía")

            if rejection_reasons:
                rejected_rows.append({**row, "motivo_rechazo": "; ".join(rejection_reasons)})
                continue

            valid_rows.append(
                {
                    "nombre_limpio": nombre,
                    "empresa": empresa,
                    "precio": precio,
                    "fu": fu,
                    "vpc": vpc,
                }
            )

        if valid_rows:
            medicamento_ids: dict[str, UUID] = {}
            for item in valid_rows:
                nombre_limpio = item["nombre_limpio"]
                if nombre_limpio not in medicamento_ids:
                    medicamento_ids[nombre_limpio] = uuid4()

            precios_payload = [
                {
                    "id": uuid4(),
                    "medicamento_id": medicamento_ids[item["nombre_limpio"]],
                    "empresa": item["empresa"],
                    "precio": item["precio"],
                    "fu": item["fu"],
                    "vpc": item["vpc"],
                }
                for item in valid_rows
            ]

            async with session_factory() as session:
                existing_medicamentos = (
                    await session.exec(
                        select(Medicamento.id, Medicamento.nombre_limpio).where(
                            Medicamento.nombre_limpio.in_(list(medicamento_ids))
                        )
                    )
                ).all()
                existing_ids = {nombre_limpio: med_id for med_id, nombre_limpio in existing_medicamentos}
                for nombre_limpio, med_id in existing_ids.items():
                    medicamento_ids[nombre_limpio] = med_id

                medicamentos_payload = [
                    {"id": med_id, "nombre_limpio": name}
                    for name, med_id in medicamento_ids.items()
                    if name not in existing_ids
                ]

                if medicamentos_payload:
                    await session.execute(insert(Medicamento), medicamentos_payload)
                await session.execute(insert(PrecioReferencia), precios_payload)
                await session.commit()

        report_path = None
        if rejected_rows:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            report_path = str(REPORT_DIR / f"reporte_rechazos_{carga_id}.csv")
            pl.DataFrame(rejected_rows).write_csv(report_path)

        errores_log = {
            "total_filas": len(dataframe),
            "insertados": len(valid_rows),
            "rechazados": len(rejected_rows),
        }
        if report_path:
            errores_log["reporte_rechazos"] = report_path

        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.COMPLETED, errores_log=errores_log)
        return {"carga_id": carga_id, "status": CargaStatus.COMPLETED.value, **errores_log}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error procesando carga %s desde archivo %s", carga_id, file_path)
        await _actualizar_estado(
            session_factory,
            carga_uuid,
            CargaStatus.FAILED,
            errores_log={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise
    finally:
        await task_engine.dispose()


async def _procesar_invima(carga_id: str, file_path: str) -> dict[str, Any]:
    carga_uuid = UUID(carga_id)
    task_engine, session_factory = create_task_session_factory()
    try:
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.PROCESSING)
        if not Path(file_path).exists():
            raise FileNotFoundError(f"No existe el archivo maestro INVIMA: {file_path}")

        errores_log = await procesar_maestro_invima(file_path, session_factory=session_factory)
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.COMPLETED, errores_log=errores_log)
        return {"carga_id": carga_id, "status": CargaStatus.COMPLETED.value, **errores_log}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error procesando maestro INVIMA %s desde archivo %s", carga_id, file_path)
        await _actualizar_estado(
            session_factory,
            carga_uuid,
            CargaStatus.FAILED,
            errores_log={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise
    finally:
        await task_engine.dispose()


async def _procesar_costos(carga_id: str, file_path: str) -> dict[str, Any]:
    carga_uuid = UUID(carga_id)
    task_engine, session_factory = create_task_session_factory()
    try:
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.PROCESSING)
        if not Path(file_path).exists():
            raise FileNotFoundError(f"No existe el archivo de costos: {file_path}")

        dataframe = _read_dataframe(file_path)
        columns = dataframe.columns
        id_cum_column = _pick_existing_column(columns, ID_CUM_COST_COLUMNS)
        precio_unitario_column = _pick_existing_column(columns, PRECIO_UNITARIO_COST_COLUMNS)
        precio_empaque_column = _pick_existing_column(columns, PRECIO_EMPAQUE_COST_COLUMNS)
        es_regulado_column = _pick_existing_column(columns, ES_REGULADO_COST_COLUMNS)
        precio_maximo_column = _pick_existing_column(columns, PRECIO_MAXIMO_COST_COLUMNS)

        if id_cum_column is None:
            raise ValueError("No se encontró columna id_cum para actualizar costos.")

        incoming_rows: dict[str, dict[str, Any]] = {}
        for row in dataframe.to_dicts():
            id_cum_raw = row.get(id_cum_column)
            id_cum = "" if id_cum_raw is None else str(id_cum_raw).strip()
            if not id_cum:
                continue
            incoming_rows[id_cum] = {
                "id_cum": id_cum,
                "precio_unitario": _normalize_decimal(row.get(precio_unitario_column)) if precio_unitario_column else None,
                "precio_empaque": _normalize_decimal(row.get(precio_empaque_column)) if precio_empaque_column else None,
                "es_regulado": _normalize_bool(row.get(es_regulado_column)) if es_regulado_column else False,
                "precio_maximo_regulado": _normalize_decimal(row.get(precio_maximo_column)) if precio_maximo_column else None,
            }

        actualizados = 0
        if incoming_rows:
            async with session_factory() as session:
                existing_rows = (
                    await session.exec(
                        select(Medicamento.id, Medicamento.id_cum, Medicamento.nombre_limpio).where(
                            Medicamento.id_cum.in_(list(incoming_rows))
                        )
                    )
                ).all()
                existing_by_id_cum = {
                    id_cum: {"id": medicamento_id, "nombre_limpio": nombre_limpio}
                    for medicamento_id, id_cum, nombre_limpio in existing_rows
                    if id_cum
                }
                payload = [
                    {
                        "id": existing_by_id_cum[id_cum]["id"],
                        **incoming_rows[id_cum],
                        "nombre_limpio": existing_by_id_cum[id_cum]["nombre_limpio"],
                    }
                    for id_cum in existing_by_id_cum
                ]
                if payload:
                    await session.execute(_construir_upsert_costos(payload))
                    await session.commit()
                    actualizados = len(payload)

        errores_log = {
            "total_filas": len(dataframe),
            "actualizados": actualizados,
            "omitidos": len(incoming_rows) - actualizados,
        }
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.COMPLETED, errores_log=errores_log)
        return {"carga_id": carga_id, "status": CargaStatus.COMPLETED.value, **errores_log}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error procesando costos %s desde archivo %s", carga_id, file_path)
        await _actualizar_estado(
            session_factory,
            carga_uuid,
            CargaStatus.FAILED,
            errores_log={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise
    finally:
        await task_engine.dispose()


def _cleanup_temp_file(file_path: str) -> None:
    path = Path(file_path)
    if path.suffix.lower() != ".tsv" or not path.exists():
        return
    try:
        path.unlink()
    except OSError:
        logger.exception("No se pudo eliminar archivo temporal %s", file_path)


def _run_async_safely(coro: Any) -> Any:
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


def _mark_failed(carga_id: str, exc: Exception) -> None:
    try:
        carga_uuid = UUID(carga_id)
    except ValueError:
        logger.warning("No se pudo parsear carga_id invalido al marcar FAILED: %s", carga_id)
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


@celery_app.task(name="task_procesar_archivo")
def task_procesar_archivo(carga_id: str, file_path: str) -> dict[str, Any]:
    try:
        return _run_async_safely(_procesar_archivo(carga_id, file_path))
    except Exception as exc:  # noqa: BLE001
        _mark_failed(carga_id, exc)
        raise
    finally:
        _cleanup_temp_file(file_path)


@celery_app.task(name="task_procesar_invima")
def task_procesar_invima(carga_id: str, file_path: str) -> dict[str, Any]:
    try:
        return _run_async_safely(_procesar_invima(carga_id, file_path))
    except Exception as exc:  # noqa: BLE001
        _mark_failed(carga_id, exc)
        raise
    finally:
        _cleanup_temp_file(file_path)


@celery_app.task(name="task_procesar_costos")
def task_procesar_costos(carga_id: str, file_path: str) -> dict[str, Any]:
    try:
        return _run_async_safely(_procesar_costos(carga_id, file_path))
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
