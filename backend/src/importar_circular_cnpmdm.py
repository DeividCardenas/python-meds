"""
importar_circular_cnpmdm.py
===========================
Carga el Anexo Técnico de la Circular de Precios CNPMDM (Ministerio de Salud)
en la tabla ``precios_regulados_cnpmdm``.

Uso
---
    python importar_circular_cnpmdm.py <ruta_csv> [opciones]

Ejemplos
--------
    # Inferir columnas automáticamente (modo interactivo):
    python importar_circular_cnpmdm.py anexo_circular_013.csv

    # Especificar columnas directamente:
    python importar_circular_cnpmdm.py anexo_circular_013.csv \\
        --col-cum CUM \\
        --col-precio "PRECIO MAXIMO VENTA" \\
        --circular "Circular 013 de 2022" \\
        --delimiter ";"

Formato del CSV esperado
------------------------
El script asume que el archivo tiene al menos dos columnas relevantes:
- Una columna con el código CUM (formato "expediente-NN", e.g. "100454-01")
  Se acepta también la forma suelta: expediente y consecutivo en columnas
  separadas (el script intentará encontrarlas automáticamente).
- Una columna con el precio máximo de venta al público.

El delimitador por defecto es ',' pero puede ser ';' o tabulación.

El script construye el id_cum como "<expediente>-<consecutivo:02d>" y hace
UPSERT (INSERT ON CONFLICT DO UPDATE) para ser idempotente.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configurar path para importar modelos del backend
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.medicamento import PrecioReguladoCNPMDM  # noqa: F401 – needed to create table

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
_UPSERT_BATCH = 500

# Posibles nombres de la columna CUM (normalizada a minúsculas)
_CUM_COLUMN_CANDIDATES = [
    "cum", "id_cum", "codigo cum", "código cum", "codigo_cum",
    "código_cum", "expediente-consecutivo",
]
# Posibles nombres de la columna de precio
_PRICE_COLUMN_CANDIDATES = [
    "precio maximo venta", "precio máximo venta", "precio_maximo_venta",
    "precio maximo", "precio máximo", "pvp", "precio venta",
    "valor maximo", "valor máximo", "precio", "price",
]
# Posibles columnas de expediente y consecutivo separados
_EXPEDIENTE_CANDIDATES = ["expediente", "exp", "nro expediente"]
_CONSECUTIVO_CANDIDATES = [
    "consecutivo", "consecutivocum", "consecutivo cum", "consec",
]


# ---------------------------------------------------------------------------
# Helpers de parsing
# ---------------------------------------------------------------------------

def _normalizar(s: str) -> str:
    """Quita acentos y caracteres especiales, pasa a minúsculas."""
    return re.sub(r"[^a-z0-9 _-]", "", s.lower().strip())


def _parse_float(value: str) -> float | None:
    """Convierte una cadena de precio (con puntos/comas) a float."""
    if not value or not value.strip():
        return None
    # Limpiar símbolos de moneda y espacios
    clean = re.sub(r"[^\d,.\-]", "", value.strip())
    if not clean:
        return None
    # Detectar formato europeo: 1.234,56 → 1234.56
    if re.search(r"\d{1,3}(\.\d{3})+,\d+", clean):
        clean = clean.replace(".", "").replace(",", ".")
    else:
        # Formato anglosajón o ya correcto: quitar comas de miles
        clean = clean.replace(",", "")
    try:
        return float(clean)
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    try:
        return int(re.sub(r"[^\d]", "", value.strip()))
    except (ValueError, AttributeError):
        return None


def _construir_id_cum(expediente: str, consecutivo: str) -> str | None:
    exp = _parse_int(expediente)
    cons = _parse_int(consecutivo)
    if exp is None or cons is None:
        return None
    return f"{exp}-{cons:02d}"


def _detectar_columnas(
    fieldnames: list[str],
    col_cum: str | None,
    col_precio: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Devuelve (col_cum, col_precio, col_expediente, col_consecutivo).
    col_cum y col_expediente/col_consecutivo son mutuamente excluyentes.
    """
    normalized = {_normalizar(f): f for f in fieldnames}

    # --- Precio ---
    if col_precio is None:
        for cand in _PRICE_COLUMN_CANDIDATES:
            if cand in normalized:
                col_precio = normalized[cand]
                break

    # --- CUM directo ---
    if col_cum is None:
        for cand in _CUM_COLUMN_CANDIDATES:
            if cand in normalized:
                col_cum = normalized[cand]
                break

    # --- Expediente + Consecutivo (fallback) ---
    col_exp = col_cons = None
    if col_cum is None:
        for cand in _EXPEDIENTE_CANDIDATES:
            if cand in normalized:
                col_exp = normalized[cand]
                break
        for cand in _CONSECUTIVO_CANDIDATES:
            if cand in normalized:
                col_cons = normalized[cand]
                break

    return col_cum, col_precio, col_exp, col_cons


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

def cargar_csv(
    path: str,
    col_cum: str | None = None,
    col_precio: str | None = None,
    circular: str | None = None,
    delimiter: str = ",",
    encoding: str = "utf-8-sig",
) -> list[dict]:
    """
    Lee el CSV y retorna una lista de dicts listos para el UPSERT.
    Cada dict tiene: id_cum, precio_maximo_venta, circular_origen,
    ultima_actualizacion.
    """
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    records: list[dict] = []
    omitidos = 0
    ahora = datetime.now(timezone.utc)

    with open(path_obj, newline="", encoding=encoding, errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("El CSV no tiene encabezados o está vacío.")

        col_cum_det, col_precio_det, col_exp, col_cons = _detectar_columnas(
            list(reader.fieldnames), col_cum, col_precio
        )

        if col_precio_det is None:
            raise ValueError(
                "No se encontró columna de precio. "
                "Usa --col-precio para especificarla.\n"
                f"Columnas disponibles: {list(reader.fieldnames)}"
            )

        has_cum = col_cum_det is not None
        has_split = col_exp is not None and col_cons is not None

        if not has_cum and not has_split:
            raise ValueError(
                "No se encontró columna de CUM ni columnas de expediente+consecutivo. "
                "Usa --col-cum para especificarla.\n"
                f"Columnas disponibles: {list(reader.fieldnames)}"
            )

        logger.info(
            "Detectado → CUM: %s | Precio: %s | Expediente: %s | Consecutivo: %s",
            col_cum_det, col_precio_det, col_exp, col_cons,
        )

        for row in reader:
            # Obtener id_cum
            if has_cum:
                raw_cum = (row.get(col_cum_det) or "").strip()
                # Normalizar por si viene sin padding de consecutivo
                parts = raw_cum.replace(" ", "").split("-")
                if len(parts) == 2:
                    exp_val = _parse_int(parts[0])
                    cons_val = _parse_int(parts[1])
                    if exp_val is not None and cons_val is not None:
                        id_cum = f"{exp_val}-{cons_val:02d}"
                    else:
                        id_cum = raw_cum if raw_cum else None
                else:
                    id_cum = raw_cum if raw_cum else None
            else:
                id_cum = _construir_id_cum(
                    row.get(col_exp, ""), row.get(col_cons, "")
                )

            if not id_cum:
                omitidos += 1
                continue

            precio = _parse_float(row.get(col_precio_det, ""))
            records.append(
                {
                    "id_cum": id_cum,
                    "precio_maximo_venta": precio,
                    "circular_origen": circular,
                    "ultima_actualizacion": ahora,
                }
            )

    logger.info(
        "CSV procesado: %d registros válidos, %d filas omitidas (sin CUM).",
        len(records),
        omitidos,
    )
    return records


async def upsert_en_bd(records: list[dict], database_url: str) -> int:
    """Hace UPSERT de los registros en precios_regulados_cnpmdm. Retorna filas afectadas."""
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    tabla = PrecioReguladoCNPMDM.__table__
    total = 0

    async with async_session() as session:
        for i in range(0, len(records), _UPSERT_BATCH):
            batch = records[i : i + _UPSERT_BATCH]
            stmt = pg_insert(tabla).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["id_cum"],
                set_={
                    "precio_maximo_venta": stmt.excluded.precio_maximo_venta,
                    "circular_origen": stmt.excluded.circular_origen,
                    "ultima_actualizacion": stmt.excluded.ultima_actualizacion,
                },
            )
            result = await session.execute(stmt)
            total += result.rowcount
            logger.info("  Lote %d-%d → %d filas", i + 1, i + len(batch), result.rowcount)

        await session.commit()

    await engine.dispose()
    return total


async def main_async(args: argparse.Namespace) -> None:
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error(
            "Debes proporcionar --database-url o definir DATABASE_URL en el entorno."
        )
        sys.exit(1)

    # Asegurar driver asyncpg
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

    records = cargar_csv(
        path=args.archivo,
        col_cum=args.col_cum,
        col_precio=args.col_precio,
        circular=args.circular,
        delimiter=args.delimiter,
        encoding=args.encoding,
    )

    if not records:
        logger.warning("No se encontraron registros válidos. Nada que insertar.")
        return

    if args.dry_run:
        logger.info("--dry-run activo: mostrando primeras 5 filas y terminando.")
        for row in records[:5]:
            print(row)
        return

    logger.info("Insertando/actualizando %d registros en BD...", len(records))
    total = await upsert_en_bd(records, database_url)
    logger.info("UPSERT completado. Total filas afectadas: %d", total)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carga el Anexo Técnico de la Circular CNPMDM en la BD.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "archivo",
        help="Ruta al archivo CSV del Anexo Técnico.",
    )
    parser.add_argument(
        "--col-cum",
        metavar="COLUMNA",
        default=None,
        help="Nombre exacto de la columna que contiene el código CUM. "
             "Si no se indica, el script lo detecta automáticamente.",
    )
    parser.add_argument(
        "--col-precio",
        metavar="COLUMNA",
        default=None,
        help="Nombre exacto de la columna del precio máximo de venta.",
    )
    parser.add_argument(
        "--circular",
        metavar="TEXTO",
        default=None,
        help='Identificador de la circular, ej. "Circular 013 de 2022".',
    )
    parser.add_argument(
        "--delimiter",
        metavar="CHAR",
        default=",",
        help="Delimitador del CSV (por defecto ',').",
    )
    parser.add_argument(
        "--encoding",
        metavar="ENC",
        default="utf-8-sig",
        help="Codificación del archivo (por defecto 'utf-8-sig', compatible con "
             "archivos exportados desde Excel con BOM).",
    )
    parser.add_argument(
        "--database-url",
        metavar="URL",
        default=None,
        help="URL de conexión PostgreSQL. Si se omite, se usa DATABASE_URL del entorno.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lee y parsea el CSV pero no escribe en la BD.",
    )

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
