from __future__ import annotations

"""
Servicio de extracción y sincronización mensual de los catálogos CUM
(Código Único de Medicamentos) publicados por INVIMA en datos.gov.co
mediante la API Socrata (SODA).
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

import aiohttp
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.medicamento import CUMSyncLog, MedicamentoCUM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de los endpoints Socrata para cada estado de CUM
# ---------------------------------------------------------------------------
SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")

SOCRATA_ENDPOINTS: dict[str, str] = {
    "vigentes": "https://www.datos.gov.co/resource/i7cb-raxc.json",
    "en_tramite": "https://www.datos.gov.co/resource/vgr4-gemg.json",
    "vencidos": "https://www.datos.gov.co/resource/qj5z-zabx.json",
}

# Plantilla de la URL de metadatos de Socrata (SODA discovery API)
SOCRATA_METADATA_URL = "https://www.datos.gov.co/api/views/{dataset_id}.json"

# Tamaño del lote para paginación SoQL – evita desbordamiento de memoria
CUM_BATCH_SIZE = int(os.getenv("CUM_BATCH_SIZE", "5000"))

# Campos esperados de la API Socrata (snake_case como los devuelve SODA)
_CUM_FIELDS = (
    "expediente",
    "consecutivocum",
    "producto",
    "titular",
    "registrosanitario",
    "fechavencimiento",
    "cantidadcum",
    "descripcioncomercial",
    "estadocum",
    "atc",
    "descripcionatc",
    "principioactivo",
)


# ---------------------------------------------------------------------------
# Helpers de conversión
# ---------------------------------------------------------------------------


def _parse_int(value: Any) -> int | None:
    """Convierte un valor a entero; retorna None si no es posible."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    """Convierte un valor a float; retorna None si no es posible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """Convierte una cadena ISO 8601 a datetime con zona horaria UTC; retorna None si falla."""
    if not value:
        return None
    # Socrata devuelve fechas en formato "YYYY-MM-DDTHH:MM:SS.mmm"
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _map_record(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Transforma un registro crudo de la API Socrata al esquema de MedicamentoCUM.

    El id_cum es la concatenación estricta expediente + "-" + consecutivocum,
    tal como lo exige el modelo de la base de datos.
    """
    expediente = _parse_int(raw.get("expediente"))
    consecutivocum = _parse_int(raw.get("consecutivocum"))

    # Construir el PK; omitir el registro si no se pueden construir ambos campos
    if expediente is None or consecutivocum is None:
        return {}

    return {
        "id_cum": f"{expediente}-{consecutivocum:02d}",
        "expediente": expediente,
        "consecutivocum": consecutivocum,
        "producto": raw.get("producto"),
        "titular": raw.get("titular"),
        "registrosanitario": raw.get("registrosanitario"),
        "fechavencimiento": _parse_datetime(raw.get("fechavencimiento")),
        "cantidadcum": _parse_float(raw.get("cantidadcum")),
        "descripcioncomercial": raw.get("descripcioncomercial"),
        "estadocum": raw.get("estadocum"),
        "atc": raw.get("atc"),
        "descripcionatc": raw.get("descripcionatc"),
        "principioactivo": raw.get("principioactivo"),
    }


# ---------------------------------------------------------------------------
# Smart Deduplication – resolver duplicados de id_cum dentro de un lote
# ---------------------------------------------------------------------------

# Estados considerados "activos/vigentes" (mayor prioridad)
_ACTIVE_STATES: frozenset[str] = frozenset({"vigente", "activo"})


def _status_priority(row: dict[str, Any]) -> int:
    """Retorna 0 para estados activos/vigentes, 1 para cualquier otro estado.

    Un valor menor indica mayor prioridad en la deduplicación.
    """
    estado = (row.get("estadocum") or "").lower().strip()
    return 0 if estado in _ACTIVE_STATES else 1


def _deduplicate_chunk(chunk: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Elimina duplicados de id_cum dentro de un lote usando reglas de negocio.

    Prioridades (en orden):
    1. Estado: 'vigente'/'activo' gana sobre 'vencido'/'inactivo'/'en tramite'.
    2. Fecha de vencimiento: la más reciente gana.  Se maneja de forma segura
       cualquier combinación de datetimes con/sin zona horaria.
    3. Desempate: se conserva la última fila procesada (mayor índice en el lote).

    Returns:
        Lista sin duplicados, con un único registro por id_cum.
    """
    best: dict[str, dict[str, Any]] = {}

    for row in chunk:
        key = row.get("id_cum")
        if key is None:
            continue

        if key not in best:
            best[key] = row
            continue

        current = best[key]

        # --- Regla 1: prioridad por estado ---
        current_priority = _status_priority(current)
        new_priority = _status_priority(row)

        if new_priority < current_priority:
            best[key] = row
            continue
        if new_priority > current_priority:
            # El registro actual ya es mejor; conservarlo
            continue

        # --- Regla 2: prioridad por fecha de vencimiento más reciente ---
        current_date: datetime | None = current.get("fechavencimiento")
        new_date: datetime | None = row.get("fechavencimiento")

        if new_date is not None:
            if current_date is None:
                best[key] = row
                continue
            # _parse_datetime siempre asigna UTC; normalizar fechas naive como
            # UTC para garantizar comparaciones seguras entre ambos tipos.
            current_ts = current_date.replace(tzinfo=timezone.utc) if current_date.tzinfo is None else current_date
            new_ts = new_date.replace(tzinfo=timezone.utc) if new_date.tzinfo is None else new_date
            if new_ts > current_ts:
                best[key] = row
                continue
            if new_ts < current_ts:
                # El registro actual tiene fecha más reciente; conservarlo
                continue
            # new_ts == current_ts → desempate por regla 3

        # --- Regla 3: desempate – conservar la última fila procesada ---
        best[key] = row

    return list(best.values())


# ---------------------------------------------------------------------------
# Construcción del UPSERT
# ---------------------------------------------------------------------------


def construir_upsert_cum(rows: list[dict[str, Any]]):
    """
    Construye un INSERT … ON CONFLICT (id_cum) DO UPDATE SET …
    para sincronizar los registros CUM en PostgreSQL.

    Se actualizan todos los campos porque el estado de un CUM puede cambiar
    (ej. de 'Vigente' a 'Vencido').
    """
    statement = pg_insert(MedicamentoCUM).values(rows)
    return statement.on_conflict_do_update(
        index_elements=[MedicamentoCUM.__table__.c.id_cum],
        set_={col: getattr(statement.excluded, col) for col in _CUM_FIELDS},
    )


# ---------------------------------------------------------------------------
# Smart Sync – detección de cambios en Socrata antes de la descarga masiva
# ---------------------------------------------------------------------------


def _extract_dataset_id(url: str) -> str:
    """Extrae el identificador 4x4 del dataset desde una URL de recurso Socrata.

    Ejemplo: "https://www.datos.gov.co/resource/i7cb-raxc.json" → "i7cb-raxc"
    """
    return url.rstrip("/").split("/")[-1].removesuffix(".json")


async def _fetch_rows_updated_at(
    session: aiohttp.ClientSession,
    dataset_id: str,
) -> datetime | None:
    """Consulta los metadatos del dataset Socrata y retorna rowsUpdatedAt en UTC.

    El campo rowsUpdatedAt es un entero Unix (segundos desde epoch).
    Retorna None si la consulta falla o el campo no está disponible.
    """
    metadata_url = SOCRATA_METADATA_URL.format(dataset_id=dataset_id)
    try:
        async with session.get(metadata_url) as response:
            response.raise_for_status()
            metadata: dict[str, Any] = await response.json(content_type=None)
        rows_updated_at = metadata.get("rowsUpdatedAt")
        if rows_updated_at is not None:
            return datetime.fromtimestamp(int(rows_updated_at), tz=timezone.utc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo obtener metadatos del dataset %s: %s", dataset_id, exc)
    return None


async def _get_sync_log(
    session_factory: async_sessionmaker[AsyncSession],
    fuente: str,
) -> CUMSyncLog | None:
    """Recupera el registro de sincronización de la base de datos para *fuente*."""
    async with session_factory() as db_session:
        result = await db_session.exec(
            select(CUMSyncLog).where(CUMSyncLog.fuente == fuente)
        )
        return result.first()


async def _update_sync_log(
    session_factory: async_sessionmaker[AsyncSession],
    fuente: str,
    rows_updated_at: datetime | None,
) -> None:
    """Actualiza (o crea) el registro de sincronización para *fuente*."""
    now = datetime.now(tz=timezone.utc)
    async with session_factory() as db_session:
        log = await db_session.get(CUMSyncLog, fuente)
        if log is None:
            log = CUMSyncLog(fuente=fuente)
            db_session.add(log)
        log.rows_updated_at = rows_updated_at
        log.ultima_sincronizacion = now
        await db_session.commit()


# ---------------------------------------------------------------------------
# Descarga paginada de un único endpoint
# ---------------------------------------------------------------------------


async def _fetch_endpoint(
    session: aiohttp.ClientSession,
    url: str,
    fuente: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """
    Itera todos los registros de *url* en lotes usando paginación SoQL
    ($limit / $offset) y aplica un upsert por cada lote.

    Retorna el número total de registros procesados.
    """
    offset = 0
    total_procesados = 0

    while True:
        params = {"$limit": CUM_BATCH_SIZE, "$offset": offset}
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                batch_raw: list[dict[str, Any]] = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            logger.error("Error HTTP al consumir %s (offset=%s): %s", fuente, offset, exc)
            raise

        if not batch_raw:
            # Sin más registros: paginación finalizada
            break

        # Mapear y filtrar registros inválidos (sin expediente/consecutivocum)
        rows = [mapped for raw in batch_raw if (mapped := _map_record(raw))]

        # Deduplicar dentro del lote antes del upsert para evitar
        # CardinalityViolationError por id_cum duplicados en el mismo chunk
        rows = _deduplicate_chunk(rows)

        if rows:
            try:
                async with session_factory() as db_session:
                    await db_session.execute(construir_upsert_cum(rows))
                    await db_session.commit()
            except Exception as exc:
                logger.error(
                    "Error durante upsert de %s (offset=%s, lote=%s): %s",
                    fuente,
                    offset,
                    len(rows),
                    exc,
                )
                raise

        total_procesados += len(rows)
        logger.info(
            "CUM [%s] offset=%s lote=%s acumulado=%s",
            fuente,
            offset,
            len(rows),
            total_procesados,
        )

        # Si el lote fue menor que el tamaño máximo, ya no hay más páginas
        if len(batch_raw) < CUM_BATCH_SIZE:
            break

        offset += CUM_BATCH_SIZE

    return total_procesados


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------


async def sincronizar_catalogos_cum(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """
    Descarga y sincroniza los tres catálogos CUM (Vigentes, En Trámite y
    Vencidos) desde la API Socrata de datos.gov.co.

    Smart Sync: antes de iniciar la descarga paginada de cada dataset, consulta
    el campo rowsUpdatedAt de los metadatos de Socrata y lo compara con el
    último valor almacenado en cum_sync_log.  Si no hay cambios, omite la
    extracción y registra "No changes detected".

    - Inyecta el App Token en la cabecera X-App-Token.
    - Pagina con $limit / $offset para no saturar la memoria.
    - Aplica upsert por lote para mantener los registros actualizados.
    """
    headers: dict[str, str] = {}
    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN

    resultados: dict[str, Any] = {}

    # Reutilizar una única sesión HTTP para todas las solicitudes
    async with aiohttp.ClientSession(headers=headers) as http_session:
        for fuente, url in SOCRATA_ENDPOINTS.items():
            logger.info("Iniciando sincronización CUM [%s]: %s", fuente, url)

            # --- Smart Sync: verificar si el dataset cambió ---
            dataset_id = _extract_dataset_id(url)
            remote_updated_at = await _fetch_rows_updated_at(http_session, dataset_id)

            if remote_updated_at is not None:
                sync_log = await _get_sync_log(session_factory, fuente)
                stored_updated_at = sync_log.rows_updated_at if sync_log else None
                if stored_updated_at is not None and remote_updated_at <= stored_updated_at:
                    logger.info(
                        "CUM [%s] No changes detected (rowsUpdatedAt=%s). Skipping extraction.",
                        fuente,
                        remote_updated_at.isoformat(),
                    )
                    resultados[fuente] = {"status": "skipped", "reason": "No changes detected"}
                    continue

            try:
                total = await _fetch_endpoint(http_session, url, fuente, session_factory)
                await _update_sync_log(session_factory, fuente, remote_updated_at)
                resultados[fuente] = {"status": "ok", "registros": total}
                logger.info("CUM [%s] completado. Total registros: %s", fuente, total)
            except Exception as exc:  # noqa: BLE001
                logger.error("CUM [%s] falló: %s", fuente, exc)
                resultados[fuente] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    return resultados
