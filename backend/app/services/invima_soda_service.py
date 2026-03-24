"""
ETL robusto para extraer la malla completa de medicamentos INVIMA desde
SODA 2.1 (datos.gov.co), unificar estados y cargar por upsert.

Incluye:
- Paginacion dinamica con $limit=50000 y $offset incremental de 50000.
- Condicion de parada cuando el endpoint devuelve un arreglo vacio.
- Reintentos con backoff y sleep entre peticiones para reducir riesgo de 429.
- Campo tecnico estado_origen en cada fila transformada.
- Fecha de corte inicial configurable (default 2026-03-16) para backfill.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import aiohttp
import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.medicamento import CUMSyncLog, MedicamentoCUM
from app.services.cum_socrata_service import poblar_medicamentos_desde_cum

logger = logging.getLogger(__name__)

SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")

INVIMA_SODA_ENDPOINTS: dict[str, str] = {
    "vigentes": "https://www.datos.gov.co/resource/i7cb-raxc.json",
    "vencidos": "https://www.datos.gov.co/resource/vwwf-4ftk.json",
    "en_tramite": "https://www.datos.gov.co/resource/vgr4-gemg.json",
    "otros": "https://www.datos.gov.co/resource/spzp-dfuc.json",
}

SOCRATA_METADATA_URL = "https://www.datos.gov.co/api/views/{dataset_id}.json"

# Requerimiento del negocio: offset en pasos de 50,000.
INVIMA_SODA_BATCH_SIZE = int(os.getenv("INVIMA_SODA_BATCH_SIZE", "50000"))
INVIMA_SODA_OFFSET_STEP = 50000

INVIMA_SODA_REQUEST_SLEEP = float(os.getenv("INVIMA_SODA_REQUEST_SLEEP", "0.35"))
INVIMA_SODA_HTTP_RETRIES = int(os.getenv("INVIMA_SODA_HTTP_RETRIES", "5"))
INVIMA_SODA_HTTP_RETRY_BACKOFF = float(os.getenv("INVIMA_SODA_HTTP_RETRY_BACKOFF", "2.5"))
INVIMA_SODA_UPSERT_CHUNK_SIZE = int(os.getenv("INVIMA_SODA_UPSERT_CHUNK_SIZE", "1000"))

# Corte inicial solicitado por negocio para backfill historico.
INVIMA_SODA_INITIAL_CUTOFF_DATE = os.getenv("INVIMA_SODA_INITIAL_CUTOFF_DATE", "2026-03-16")
INVIMA_SODA_USE_INITIAL_CUTOFF = os.getenv("INVIMA_SODA_USE_INITIAL_CUTOFF", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


_CUM_FIELDS = (
    "expediente",
    "consecutivocum",
    "producto",
    "titular",
    "registrosanitario",
    "fechaexpedicion",
    "fechavencimiento",
    "estadoregistro",
    "cantidadcum",
    "descripcioncomercial",
    "estadocum",
    "fechaactivo",
    "fechainactivo",
    "muestramedica",
    "unidad",
    "atc",
    "descripcionatc",
    "viaadministracion",
    "concentracion",
    "principioactivo",
    "unidadmedida",
    "cantidad",
    "unidadreferencia",
    "formafarmaceutica",
    "nombrerol",
    "tiporol",
    "modalidad",
    "estado_origen",
    "fecha_corte_dato",
)


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    text = str(value).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_dataset_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1].removesuffix(".json")


def _normalize_estado_label(estado_origen: str) -> str:
    labels = {
        "vigentes": "Vigente",
        "vencidos": "Vencido",
        "en_tramite": "En tramite",
        "otros": "Otro",
    }
    return labels.get(estado_origen, estado_origen)


def _parse_initial_cutoff_date() -> datetime:
    parsed = _parse_datetime(INVIMA_SODA_INITIAL_CUTOFF_DATE)
    if parsed is not None:
        return parsed
    logger.warning(
        "INVIMA_SODA_INITIAL_CUTOFF_DATE invalida (%s). Se usara 2026-03-16.",
        INVIMA_SODA_INITIAL_CUTOFF_DATE,
    )
    return datetime(2026, 3, 16, tzinfo=timezone.utc)


def _resolve_fecha_corte_dato(has_previous_sync: bool, execution_dt: datetime) -> datetime:
    """Define la fecha de corte por fila.

    - Primera corrida y flag activa: usa corte inicial (backfill).
    - Corridas siguientes: usa fecha real de ejecucion.
    """
    if not has_previous_sync and INVIMA_SODA_USE_INITIAL_CUTOFF:
        return _parse_initial_cutoff_date()
    return execution_dt


def _map_record(raw: dict[str, Any], estado_origen: str, fecha_corte_dato: datetime) -> dict[str, Any]:
    expediente = _parse_int(raw.get("expediente"))
    consecutivocum = _parse_int(raw.get("consecutivocum"))

    if expediente is None or consecutivocum is None:
        return {}

    estadocum = raw.get("estadocum") or _normalize_estado_label(estado_origen)

    return {
        "id_cum": f"{expediente}-{consecutivocum:02d}",
        "expediente": expediente,
        "consecutivocum": consecutivocum,
        "producto": raw.get("producto"),
        "titular": raw.get("titular"),
        "registrosanitario": raw.get("registrosanitario"),
        "fechaexpedicion": _parse_datetime(raw.get("fechaexpedicion")),
        "fechavencimiento": _parse_datetime(raw.get("fechavencimiento")),
        "estadoregistro": raw.get("estadoregistro"),
        "cantidadcum": _parse_int(raw.get("cantidadcum")),
        "descripcioncomercial": raw.get("descripcioncomercial"),
        "estadocum": estadocum,
        "fechaactivo": _parse_datetime(raw.get("fechaactivo")),
        "fechainactivo": _parse_datetime(raw.get("fechainactivo")),
        "muestramedica": raw.get("muestramedica"),
        "unidad": raw.get("unidad"),
        "atc": raw.get("atc"),
        "descripcionatc": raw.get("descripcionatc"),
        "viaadministracion": raw.get("viaadministracion"),
        "concentracion": raw.get("concentracion"),
        "principioactivo": raw.get("principioactivo"),
        "unidadmedida": raw.get("unidadmedida"),
        "cantidad": raw.get("cantidad"),
        "unidadreferencia": raw.get("unidadreferencia"),
        "formafarmaceutica": raw.get("formafarmaceutica"),
        "nombrerol": raw.get("nombrerol"),
        "tiporol": raw.get("tiporol"),
        "modalidad": raw.get("modalidad"),
        "estado_origen": estado_origen,
        "fecha_corte_dato": fecha_corte_dato,
    }


def _deduplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplica por id_cum manteniendo la ultima fila vista.

    Si un id_cum aparece en mas de un endpoint, se preserva trazabilidad en
    estado_origen concatenando etiquetas unicas separadas por coma.
    """
    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        key = row.get("id_cum")
        if not key:
            continue

        if key not in grouped:
            grouped[key] = row
            continue

        previous = grouped[key]
        estados = {
            str(previous.get("estado_origen", "")).strip(),
            str(row.get("estado_origen", "")).strip(),
        }
        estados = {x for x in estados if x}
        merged = row.copy()
        if estados:
            merged["estado_origen"] = ",".join(sorted(estados))

        if (previous.get("fecha_corte_dato") or datetime.min.replace(tzinfo=timezone.utc)) > (
            merged.get("fecha_corte_dato") or datetime.min.replace(tzinfo=timezone.utc)
        ):
            merged["fecha_corte_dato"] = previous.get("fecha_corte_dato")

        grouped[key] = merged

    return list(grouped.values())


def construir_upsert_invima_soda(rows: list[dict[str, Any]]):
    statement = pg_insert(MedicamentoCUM).values(rows)
    return statement.on_conflict_do_update(
        index_elements=[MedicamentoCUM.__table__.c.id_cum],
        set_={col: getattr(statement.excluded, col) for col in _CUM_FIELDS},
    )


async def _fetch_rows_updated_at(
    session: aiohttp.ClientSession,
    dataset_id: str,
) -> datetime | None:
    metadata_url = SOCRATA_METADATA_URL.format(dataset_id=dataset_id)
    try:
        async with session.get(metadata_url) as response:
            response.raise_for_status()
            metadata: dict[str, Any] = await response.json(content_type=None)
        rows_updated_at = metadata.get("rowsUpdatedAt")
        if rows_updated_at is not None:
            return datetime.fromtimestamp(int(rows_updated_at), tz=timezone.utc)
    except (aiohttp.ClientError, TypeError, ValueError) as exc:
        logger.warning("No se pudo obtener rowsUpdatedAt para dataset %s: %s", dataset_id, exc)
    return None


async def _get_sync_log(
    session_factory: async_sessionmaker[AsyncSession],
    fuente: str,
) -> CUMSyncLog | None:
    async with session_factory() as db_session:
        result = await db_session.exec(select(CUMSyncLog).where(CUMSyncLog.fuente == fuente))
        return result.first()


async def _update_sync_log(
    session_factory: async_sessionmaker[AsyncSession],
    fuente: str,
    rows_updated_at: datetime | None,
) -> None:
    now = datetime.now(tz=timezone.utc)
    async with session_factory() as db_session:
        log = await db_session.get(CUMSyncLog, fuente)
        if log is None:
            log = CUMSyncLog(fuente=fuente)
            db_session.add(log)
        log.rows_updated_at = rows_updated_at
        log.ultima_sincronizacion = now
        await db_session.commit()


async def _fetch_endpoint(
    session: aiohttp.ClientSession,
    url: str,
    estado_origen: str,
    fecha_corte_dato: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extrae todos los registros de un endpoint con paginacion while."""
    offset = 0
    total_raw = 0
    rows: list[dict[str, Any]] = []
    pages = 0
    retries_total = 0

    while True:
        params = {
            "$limit": INVIMA_SODA_BATCH_SIZE,
            "$offset": offset,
            "$order": "expediente ASC, consecutivocum ASC",
        }

        batch_raw: list[dict[str, Any]] | None = None

        for attempt in range(1, INVIMA_SODA_HTTP_RETRIES + 1):
            try:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    batch_raw = await response.json(content_type=None)
                break
            except aiohttp.ClientResponseError as exc:
                should_retry = (
                    exc.status == 429 or
                    (exc.status is not None and exc.status >= 500)
                )
                if should_retry and attempt < INVIMA_SODA_HTTP_RETRIES:
                    retries_total += 1
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    wait = INVIMA_SODA_HTTP_RETRY_BACKOFF * (2 ** (attempt - 1))
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning(
                        "INVIMA SODA [%s] HTTP %s offset=%s intento %s/%s. Espera %.1fs.",
                        estado_origen,
                        exc.status,
                        offset,
                        attempt,
                        INVIMA_SODA_HTTP_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error("INVIMA SODA [%s] error HTTP offset=%s: %s", estado_origen, offset, exc)
                raise
            except aiohttp.ClientError as exc:
                if attempt < INVIMA_SODA_HTTP_RETRIES:
                    retries_total += 1
                    wait = INVIMA_SODA_HTTP_RETRY_BACKOFF * (2 ** (attempt - 1))
                    logger.warning(
                        "INVIMA SODA [%s] error de red offset=%s intento %s/%s. Espera %.1fs.",
                        estado_origen,
                        offset,
                        attempt,
                        INVIMA_SODA_HTTP_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error("INVIMA SODA [%s] error de red offset=%s: %s", estado_origen, offset, exc)
                raise

        if batch_raw is None:
            break

        # Condicion de parada solicitada: arreglo vacio.
        if not batch_raw:
            logger.info("INVIMA SODA [%s] finalizado en offset=%s", estado_origen, offset)
            break

        pages += 1
        total_raw += len(batch_raw)

        mapped_rows = [
            mapped for raw in batch_raw if (mapped := _map_record(raw, estado_origen, fecha_corte_dato))
        ]
        rows.extend(mapped_rows)

        logger.info(
            "INVIMA SODA [%s] offset=%s lote_raw=%s lote_valido=%s acumulado=%s",
            estado_origen,
            offset,
            len(batch_raw),
            len(mapped_rows),
            len(rows),
        )

        await asyncio.sleep(INVIMA_SODA_REQUEST_SLEEP)
        offset += INVIMA_SODA_OFFSET_STEP

    stats = {
        "status": "ok",
        "pages": pages,
        "raw": total_raw,
        "validos": len(rows),
        "offset_final": offset,
        "retries": retries_total,
    }
    return rows, stats


async def _upsert_rows(
    session_factory: async_sessionmaker[AsyncSession],
    rows: list[dict[str, Any]],
) -> int:
    total = 0
    for i in range(0, len(rows), INVIMA_SODA_UPSERT_CHUNK_SIZE):
        chunk = rows[i : i + INVIMA_SODA_UPSERT_CHUNK_SIZE]
        if not chunk:
            continue
        async with session_factory() as db_session:
            await db_session.execute(construir_upsert_invima_soda(chunk))
            await db_session.commit()
        total += len(chunk)
    return total


def build_dataframe_invima_soda(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        columns = ["id_cum", "expediente", "consecutivocum", "estado_origen", "fecha_corte_dato"]
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    for col in ("fechaexpedicion", "fechavencimiento", "fechaactivo", "fechainactivo", "fecha_corte_dato"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    if "id_cum" in df.columns:
        df = df.sort_values(by="id_cum").reset_index(drop=True)
    return df


async def extraer_transformar_invima_soda(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    """Extrae + transforma los 4 endpoints y retorna DataFrame + lista de dicts."""
    headers: dict[str, str] = {}
    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=60, sock_read=180)

    all_rows: list[dict[str, Any]] = []
    resumen: dict[str, Any] = {
        "status": "ok",
        "fuente": "datos.gov.co",
        "por_endpoint": {},
        "ejecutado_en": datetime.now(tz=timezone.utc).isoformat(),
    }

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        for estado_origen, url in INVIMA_SODA_ENDPOINTS.items():
            sync_key = f"invima_soda:{estado_origen}"
            existing_log = await _get_sync_log(session_factory, sync_key)
            fecha_corte = _resolve_fecha_corte_dato(
                has_previous_sync=existing_log is not None,
                execution_dt=datetime.now(tz=timezone.utc),
            )

            logger.info("Iniciando endpoint INVIMA SODA [%s]: %s", estado_origen, url)
            endpoint_rows, endpoint_stats = await _fetch_endpoint(
                session=session,
                url=url,
                estado_origen=estado_origen,
                fecha_corte_dato=fecha_corte,
            )

            all_rows.extend(endpoint_rows)

            dataset_id = _extract_dataset_id(url)
            remote_updated_at = await _fetch_rows_updated_at(session, dataset_id)
            await _update_sync_log(session_factory, sync_key, remote_updated_at)

            endpoint_stats["rows_updated_at"] = (
                remote_updated_at.isoformat() if remote_updated_at else None
            )
            endpoint_stats["fecha_corte_dato"] = fecha_corte.isoformat()
            resumen["por_endpoint"][estado_origen] = endpoint_stats

    dedup_rows = _deduplicate_rows(all_rows)
    df = build_dataframe_invima_soda(dedup_rows)

    resumen["registros_extraidos"] = len(all_rows)
    resumen["registros_preparados"] = len(dedup_rows)
    resumen["fecha_corte_inicial_configurada"] = INVIMA_SODA_INITIAL_CUTOFF_DATE

    return df, dedup_rows, resumen


async def sincronizar_invima_soda(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    cargar_bd: bool = True,
    retornar_dataframe: bool = False,
    retornar_rows: bool = False,
) -> dict[str, Any]:
    """Orquestador ETL completo: extract + transform + optional load."""
    df, rows, resumen = await extraer_transformar_invima_soda(session_factory)

    upsert_count = 0
    if cargar_bd and rows:
        upsert_count = await _upsert_rows(session_factory, rows)

        # Mantener la tabla medicamentos alineada con el catalogo CUM consolidado.
        poblar_result = await poblar_medicamentos_desde_cum(session_factory)
        resumen["poblar_medicamentos"] = poblar_result

    resumen["registros_upsert"] = upsert_count

    if retornar_dataframe:
        resumen["dataframe"] = df
    if retornar_rows:
        resumen["rows"] = rows

    return resumen
