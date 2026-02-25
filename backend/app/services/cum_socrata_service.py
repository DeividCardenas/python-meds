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
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.medicamento import MedicamentoCUM

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
            try:
                total = await _fetch_endpoint(http_session, url, fuente, session_factory)
                resultados[fuente] = {"status": "ok", "registros": total}
                logger.info("CUM [%s] completado. Total registros: %s", fuente, total)
            except Exception as exc:  # noqa: BLE001
                logger.error("CUM [%s] falló: %s", fuente, exc)
                resultados[fuente] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    return resultados
