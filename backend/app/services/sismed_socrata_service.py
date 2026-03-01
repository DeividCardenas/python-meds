from __future__ import annotations

"""
Servicio de extracción y sincronización de precios de medicamentos desde el
dataset público SISMED publicado por el Ministerio de Salud en datos.gov.co.

Dataset : Consulta Pública de Precios de Medicamentos (SISMED)
Resource: https://www.datos.gov.co/resource/3he6-m866.json
Estándar: CNPMDM – "Estándar de Datos de Medicamentos de Uso Humano en Colombia"

Periodicidad sugerida: El ministerio actualiza SISMED trimestralmente; sin
embargo, Socrata puede recibir parches intermedios.  La tarea Celery Beat
está programada el día 2 de cada mes a las 3:00 AM para ejecutarse siempre
después de la sincronización CUM (día 1 a las 2:00 AM).
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import aiohttp
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.medicamento import PrecioMedicamento

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

SOCRATA_APP_TOKEN: str = os.getenv("SOCRATA_APP_TOKEN", "")

# Endpoint SISMED en Socrata (datos.gov.co)
SISMED_ENDPOINT = "https://www.datos.gov.co/resource/3he6-m866.json"

# Tamaño del lote para paginación SoQL
SISMED_BATCH_SIZE: int = int(os.getenv("SISMED_BATCH_SIZE", "5000"))

# Máximo de filas por sentencia UPSERT.
# Numeric(14,4) tiene 3 columnas numéricas + 2 string + id + audit = ~12 campos
# → margen seguro de 800 filas por sub-chunk
_UPSERT_CHUNK_SIZE: int = int(os.getenv("SISMED_UPSERT_CHUNK_SIZE", "800"))

# Reintentos ante errores HTTP 5xx
_HTTP_RETRIES: int = int(os.getenv("SISMED_HTTP_RETRIES", "5"))
_HTTP_RETRY_BACKOFF: float = float(os.getenv("SISMED_HTTP_RETRY_BACKOFF", "3.0"))

# Canales de mercado válidos según la norma CNPMDM
_CANALES_VALIDOS: frozenset[str] = frozenset({"INS", "COM"})

# Regímenes válidos (1, 2, 3)
_REGIMEN_RANGE: range = range(1, 4)

# ---------------------------------------------------------------------------
# Mapeo flexible de columnas del dataset Socrata
# ---------------------------------------------------------------------------
# Columnas reales del resource 3he6-m866 (verificadas contra el endpoint vivo):
#   expedientecum, consecutivo, transaccionsismeddesc, valorminimo, valormaximo
#
# Se mantienen candidatos alternativos por si cambia la versión del dataset.

_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "expediente": (
        "expedientecum",   # nombre real del dataset
        "expediente",      # alternativa histórica
    ),
    "consecutivocum": (
        "consecutivo",     # nombre real del dataset
        "consecutivocum",  # alternativa histórica
        "consecutivo_cum",
    ),
    "canal_mercado": (
        "transaccionsismeddesc",  # nombre real: "TRANSACCION PRIMARIA INSTITUCIONAL/COMERCIAL"
        "canal",
        "canal_mercado",
        "tipo_canal",
    ),
    "regimen_precios": (
        "regimen",
        "regimen_precios",
        "regimen_precio",
        "id_regimen",
    ),
    "precio_regulado_maximo": (
        "precio_maximo_venta_regulado",
        "precio_regulado_maximo",
        "precio_regulado",
        "precio_maximo_regulado",
        "precioreguladomaximo",
    ),
    "acto_administrativo_precio": (
        "acto_administrativo",
        "acto_administrativo_precio",
        "acto_adm",
        "circular",
        "acto_adm_precio",
    ),
    "precio_sismed_minimo": (
        "valorminimo",          # nombre real del dataset
        "precio_minimo_venta",
        "precio_minimo",
        "precio_sismed_minimo",
        "preciomin",
    ),
    "precio_sismed_maximo": (
        "valormaximo",          # nombre real del dataset
        "precio_maximo_venta",
        "precio_maximo",
        "precio_sismed_maximo",
        "preciomax",
    ),
    # Fecha de corte del reporte – usada para deduplicar (mantener el más reciente)
    "fechacorte": (
        "fechacorte",
        "fecha_corte",
        "fecha_reporte",
    ),
}


def _resolve_field(raw: dict[str, Any], field_key: str) -> Any:
    """Retorna el valor del primer candidato que exista en *raw*."""
    for candidate in _FIELD_CANDIDATES[field_key]:
        if candidate in raw:
            return raw[candidate]
    return None


# ---------------------------------------------------------------------------
# Helpers de conversión (misma interfaz que cum_socrata_service)
# ---------------------------------------------------------------------------


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    # Fallback: handle float-strings like "1.0", "3.0" (SISMED occasionally sends these)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    """Convierte a Decimal con limpieza de separadores de miles."""
    if value is None:
        return None
    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    if not text or text in ("-", ""):
        return None
    # Manejo de separadores mixtos: "1.234,56" → "1234.56"
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except Exception:  # noqa: BLE001
        return None


def _normalize_canal(value: Any) -> str | None:
    """Normaliza el canal a 'INS' o 'COM'; retorna None si no es válido.

    El dataset SISMED (3he6-m866) devuelve el campo transaccionsismeddesc con
    valores como:
      "TRANSACCION PRIMARIA INSTITUCIONAL"  → 'INS'
      "TRANSACCION PRIMARIA COMERCIAL"      → 'COM'
      "TRANSACCION SECUNDARIA INSTITUCIONAL" → 'INS'
      "TRANSACCION SECUNDARIA COMERCIAL"    → 'COM'
    """
    if value is None:
        return None
    canal = str(value).strip().upper()
    # Coincidencia por subcadena para absorber todas las variantes de Socrata
    if "INSTITUCIONAL" in canal:
        return "INS"
    if "COMERCIAL" in canal:
        return "COM"
    # Valores cortos directos (otras fuentes o versiones futuras del dataset)
    _ALIAS: dict[str, str] = {
        "INS": "INS",
        "COM": "COM",
        "I": "INS",
        "C": "COM",
    }
    mapped = _ALIAS.get(canal)
    return mapped if mapped in _CANALES_VALIDOS else None


def _normalize_regimen(value: Any) -> int | None:
    """Convierte el régimen a entero 1/2/3; retorna None si no es válido."""
    parsed = _parse_int(value)
    return parsed if parsed in _REGIMEN_RANGE else None


# ---------------------------------------------------------------------------
# Mapeo de un registro crudo al esquema PrecioMedicamento
# ---------------------------------------------------------------------------


def _map_record(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Transforma un registro crudo del endpoint SISMED al dict de PrecioMedicamento.

    El id_cum se construye concatenando expediente + "-" + consecutivocum
    (mismo formato que MedicamentoCUM.id_cum) para garantizar el cruce exacto
    con la tabla medicamentos_cum.

    Retorna un dict vacío si los campos clave no son parseables.
    """
    expediente = _parse_int(_resolve_field(raw, "expediente"))
    consecutivocum = _parse_int(_resolve_field(raw, "consecutivocum"))

    if expediente is None or consecutivocum is None:
        return {}

    id_cum = f"{expediente}-{consecutivocum:02d}"

    canal_mercado = _normalize_canal(_resolve_field(raw, "canal_mercado"))
    if canal_mercado is None:
        # Sin canal válido no podemos construir la clave natural
        return {}

    return {
        "id_cum": id_cum,
        "canal_mercado": canal_mercado,
        "regimen_precios": _normalize_regimen(_resolve_field(raw, "regimen_precios")),
        "precio_regulado_maximo": _parse_decimal(
            _resolve_field(raw, "precio_regulado_maximo")
        ),
        "acto_administrativo_precio": _resolve_field(raw, "acto_administrativo_precio"),
        "precio_sismed_minimo": _parse_decimal(
            _resolve_field(raw, "precio_sismed_minimo")
        ),
        "precio_sismed_maximo": _parse_decimal(
            _resolve_field(raw, "precio_sismed_maximo")
        ),
        "ultima_actualizacion": datetime.now(tz=timezone.utc),
        # Campo auxiliar para deduplicación intra-lote; NO se persiste en la BD
        "_fechacorte": str(_resolve_field(raw, "fechacorte") or ""),
    }


# ---------------------------------------------------------------------------
# Construcción del UPSERT  (ON CONFLICT (id_cum, canal_mercado) DO UPDATE)
# ---------------------------------------------------------------------------

# Campos actualizables en un conflicto (excluye id y id_cum que son la llave)
_UPSERT_UPDATE_FIELDS: tuple[str, ...] = (
    "regimen_precios",
    "precio_regulado_maximo",
    "acto_administrativo_precio",
    "precio_sismed_minimo",
    "precio_sismed_maximo",
    "ultima_actualizacion",
)


# ---------------------------------------------------------------------------
# Deduplicación intra-lote
# ---------------------------------------------------------------------------


def _deduplicate_chunk_precios(
    chunk: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Elimina duplicados de (id_cum, canal_mercado) dentro de un lote.

    El dataset SISMED es histórico; un mismo CUM+canal aparece múltiples veces
    con distintas fechas de corte.  Se conserva únicamente el registro con la
    fechacorte más reciente (orden lexicográfico sobre el string YYYY/MM/DD).
    En empate se conserva la última fila procesada.

    El campo auxiliar '_fechacorte' se elimina antes de retornar para que no
    intente persistirse en la base de datos.
    """
    best: dict[tuple[str, str], dict[str, Any]] = {}

    for row in chunk:
        key = (row.get("id_cum", ""), row.get("canal_mercado", ""))
        if not key[0] or not key[1]:
            continue

        if key not in best:
            best[key] = row
            continue

        current_fecha = best[key].get("_fechacorte") or ""
        new_fecha = row.get("_fechacorte") or ""

        # Mayor fecha (lexicográfica) gana; en empate la última fila
        if new_fecha >= current_fecha:
            best[key] = row

    # Retirar el campo auxiliar antes de persistir
    result = []
    for row in best.values():
        clean = {k: v for k, v in row.items() if k != "_fechacorte"}
        result.append(clean)
    return result


def construir_upsert_precios(rows: list[dict[str, Any]]):
    """
    Construye un INSERT … ON CONFLICT (id_cum, canal_mercado) DO UPDATE SET …
    usando el constraint único definido en el modelo PrecioMedicamento.

    • Si el par (id_cum, canal_mercado) no existe → inserta una fila nueva.
    • Si ya existe → actualiza únicamente los campos de precio y auditoría.
    """
    statement = pg_insert(PrecioMedicamento).values(rows)
    return statement.on_conflict_do_update(
        constraint="uq_precio_cum_canal",
        set_={col: getattr(statement.excluded, col) for col in _UPSERT_UPDATE_FIELDS},
    )


# ---------------------------------------------------------------------------
# Descarga paginada del endpoint SISMED
# ---------------------------------------------------------------------------


async def _fetch_latest_fechacorte(
    http_session: aiohttp.ClientSession,
) -> str | None:
    """
    Consulta el endpoint SISMED para obtener la fechacorte más reciente
    disponible en el dataset.

    El dataset es histórico (múltiples años); filtrar por la fechacorte máxima
    reduce el volumen de registros de cientos de miles a decenas de miles,
    acelerando la sincronización en >10×.

    Retorna la fecha en formato 'YYYY/MM/DD' o None si no se pudo determinar.
    """
    params: dict[str, str] = {
        "$select": "max(fechacorte) as max_fecha",
        "$limit": "1",
    }
    try:
        async with http_session.get(SISMED_ENDPOINT, params=params) as response:
            response.raise_for_status()
            data: list[dict[str, Any]] = await response.json(content_type=None)
        if data and isinstance(data, list) and data[0].get("max_fecha"):
            return str(data[0]["max_fecha"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo obtener la fechacorte máxima de SISMED: %s", exc)
    return None


async def _fetch_sismed(
    http_session: aiohttp.ClientSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """
    Itera todos los registros de SISMED en lotes usando paginación SoQL
    ($limit / $offset) y aplica upsert por cada lote.

    Optimización: filtra por la fechacorte más reciente del dataset para
    evitar paginar millones de filas históricas.  Esto reduce el volumen a
    sólo el período más reciente (~50 000 filas vs >500 000 históricas).

    Retorna el número total de registros válidos procesados.
    """
    # ── Paso 1: determinar la fechacorte más reciente ──────────────────────
    latest_fecha = await _fetch_latest_fechacorte(http_session)
    if latest_fecha:
        logger.info(
            "SISMED filtrando por fechacorte más reciente: %s", latest_fecha
        )
        where_filter: str | None = f"fechacorte='{latest_fecha}'"
    else:
        logger.warning(
            "SISMED: no se pudo determinar la fechacorte máxima; "
            "se descargará el dataset completo (puede tardar varios minutos)."
        )
        where_filter = None

    offset = 0
    total_procesados = 0

    while True:
        params: dict[str, Any] = {
            "$limit": SISMED_BATCH_SIZE,
            "$offset": offset,
            # Columnas reales del dataset 3he6-m866
            "$order": "expedientecum ASC, consecutivo ASC",
        }
        if where_filter:
            params["$where"] = where_filter

        batch_raw: list[dict[str, Any]] | None = None

        for attempt in range(1, _HTTP_RETRIES + 1):
            try:
                async with http_session.get(
                    SISMED_ENDPOINT, params=params
                ) as response:
                    response.raise_for_status()
                    batch_raw = await response.json(content_type=None)
                break
            except aiohttp.ClientResponseError as exc:
                if exc.status and exc.status >= 500 and attempt < _HTTP_RETRIES:
                    wait = _HTTP_RETRY_BACKOFF * (2 ** (attempt - 1))
                    logger.warning(
                        "SISMED HTTP %s en offset=%s, intento %s/%s. Reintentando en %.1fs…",
                        exc.status,
                        offset,
                        attempt,
                        _HTTP_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "Error HTTP SISMED (offset=%s): %s", offset, exc
                    )
                    raise
            except aiohttp.ClientError as exc:
                logger.error("Error de conexión SISMED (offset=%s): %s", offset, exc)
                raise

        if batch_raw is None:
            break

        if not batch_raw:
            logger.info("SISMED paginación completa en offset=%s", offset)
            break

        # Mapear y filtrar registros inválidos
        from uuid import uuid4

        rows: list[dict[str, Any]] = []
        for raw in batch_raw:
            mapped = _map_record(raw)
            if mapped:
                mapped["id"] = uuid4()
                rows.append(mapped)

        if rows:
            # Deduplicar dentro del lote para evitar CardinalityViolationError:
            # el dataset es histórico y puede traer N filas por (id_cum, canal).
            # Conservamos sólo la con fechacorte más reciente.
            rows = _deduplicate_chunk_precios(rows)

            # Sub-batching para no superar el límite de parámetros de PostgreSQL
            for i in range(0, len(rows), _UPSERT_CHUNK_SIZE):
                sub_chunk = rows[i : i + _UPSERT_CHUNK_SIZE]
                try:
                    async with session_factory() as db_session:
                        await db_session.execute(construir_upsert_precios(sub_chunk))
                        await db_session.commit()
                except Exception as exc:
                    logger.error(
                        "Error upsert SISMED (offset=%s, chunk=%s-%s, size=%s): %s",
                        offset,
                        i,
                        i + len(sub_chunk),
                        len(sub_chunk),
                        exc,
                    )
                    raise

        total_procesados += len(rows)
        logger.info(
            "SISMED offset=%s lote=%s (válidos=%s) acumulado=%s",
            offset,
            len(batch_raw),
            len(rows),
            total_procesados,
        )

        if len(batch_raw) < SISMED_BATCH_SIZE:
            break

        offset += SISMED_BATCH_SIZE

    return total_procesados


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------


async def sincronizar_precios_sismed(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """
    Descarga y sincroniza el catálogo de precios SISMED desde datos.gov.co.

    • Inyecta el App Token en la cabecera X-App-Token si está configurado.
    • Pagina con $limit/$offset en bloques de SISMED_BATCH_SIZE (default 5 000).
    • Aplica ON CONFLICT (id_cum, canal_mercado) DO UPDATE por lote.
    • Retorna un dict con el resumen de la sincronización.
    """
    headers: dict[str, str] = {}
    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN

    logger.info("Iniciando sincronización SISMED: %s", SISMED_ENDPOINT)
    try:
        async with aiohttp.ClientSession(headers=headers) as http_session:
            total = await _fetch_sismed(http_session, session_factory)

        logger.info("SISMED sincronización completada. Total registros: %s", total)
        return {"status": "ok", "registros": total}
    except Exception as exc:  # noqa: BLE001
        logger.error("SISMED sincronización falló: %s", exc)
        return {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
