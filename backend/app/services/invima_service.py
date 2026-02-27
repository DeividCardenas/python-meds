from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import text
from sqlalchemy.sql.dml import Insert

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.medicamento import Medicamento

INVIMA_BATCH_SIZE = 2000
EMBEDDING_STATUS_PENDING = "PENDING"
logger = logging.getLogger(__name__)
TMP_INVIMA_COLUMNS = (
    "id",
    "id_cum",
    "nombre_limpio",
    "atc",
    "registro_invima",
    "estado_regulatorio",
    "laboratorio",
    "principio_activo",
    "forma_farmaceutica",
    "embedding_status",
)
REQUIRED_INVIMA_COLUMNS = (
    "ESTADO REGISTRO",
    "ESTADO CUM",
    "EXPEDIENTE",
    "CONSECUTIVO",
    "ATC",
    "REGISTRO INVIMA",
    "NOMBRE COMERCIAL",
    "PRINCIPIO ACTIVO",
    "FORMA FARMACEUTICA",
    "LABORATORIO TITULAR",
)
CREATE_TMP_INVIMA_SQL = "CREATE TEMP TABLE tmp_invima (LIKE medicamentos EXCLUDING INDEXES) ON COMMIT DROP"
MERGE_TMP_INVIMA_SQL = """
INSERT INTO medicamentos (
    id,
    id_cum,
    nombre_limpio,
    atc,
    registro_invima,
    estado_regulatorio,
    laboratorio,
    principio_activo,
    forma_farmaceutica,
    embedding_status
)
SELECT
    id,
    id_cum,
    nombre_limpio,
    atc,
    registro_invima,
    estado_regulatorio,
    laboratorio,
    principio_activo,
    forma_farmaceutica,
    embedding_status
FROM tmp_invima
ON CONFLICT (id_cum) DO UPDATE SET
    atc = EXCLUDED.atc,
    registro_invima = EXCLUDED.registro_invima,
    estado_regulatorio = EXCLUDED.estado_regulatorio,
    nombre_limpio = EXCLUDED.nombre_limpio,
    laboratorio = EXCLUDED.laboratorio,
    principio_activo = EXCLUDED.principio_activo,
    forma_farmaceutica = EXCLUDED.forma_farmaceutica
"""


def leer_maestro_invima(file_path: str) -> pl.DataFrame:
    if not Path(file_path).exists():
        raise FileNotFoundError(f"No existe el archivo maestro INVIMA: {file_path}")

    dataframe = None
    detected_separator = None
    attempted_columns: list[str] = []
    for separator in ("\t", ";", ","):
        candidate = pl.read_csv(
            file_path,
            separator=separator,
            infer_schema_length=0,
            ignore_errors=True,
            truncate_ragged_lines=True,
        )
        attempted_columns = candidate.columns
        if all(column in candidate.columns for column in REQUIRED_INVIMA_COLUMNS):
            dataframe = candidate
            detected_separator = separator
            break
    if dataframe is None:
        raise pl.exceptions.ColumnNotFoundError(
            "No se reconocieron las columnas esperadas del archivo maestro INVIMA. "
            f"Esperadas: {', '.join(REQUIRED_INVIMA_COLUMNS)}. Encontradas: {', '.join(attempted_columns)}"
        )
    logger.info("INVIMA separador detectado: %r", detected_separator)

    dataframe = dataframe.with_columns(
        pl.col("ESTADO REGISTRO").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("ESTADO CUM").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("EXPEDIENTE").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("CONSECUTIVO").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("ATC").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("REGISTRO INVIMA").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("NOMBRE COMERCIAL").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("PRINCIPIO ACTIVO").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("FORMA FARMACEUTICA").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
        pl.col("LABORATORIO TITULAR").cast(pl.Utf8).fill_null("").str.strip_chars().str.replace_all(r"(?i)^sin dato$", ""),
    )
    logger.info("INVIMA registros leidos: %s", len(dataframe))

    dataframe = dataframe.filter(
        (pl.col("ESTADO REGISTRO").str.to_lowercase() == "vigente") & (pl.col("ESTADO CUM").str.to_lowercase() == "activo")
    )
    logger.info("INVIMA registros tras filtrado vigente/activo: %s", len(dataframe))

    dataframe = (
        dataframe.select(
            id_cum=(pl.col("EXPEDIENTE") + "-" + pl.col("CONSECUTIVO")),
            atc=pl.col("ATC"),
            registro_invima=pl.col("REGISTRO INVIMA"),
            estado_regulatorio=(pl.col("ESTADO REGISTRO") + " / " + pl.col("ESTADO CUM")),
            nombre_limpio=pl.concat_str(
                [pl.col("NOMBRE COMERCIAL"), pl.col("PRINCIPIO ACTIVO")],
                separator=" ",
                ignore_nulls=True,
            )
            .str.replace_all(r"[®™]", " ")
            .str.replace_all(r"\s+", " ")
            .str.strip_chars()
            .str.to_lowercase()
            .str.normalize("NFD")
            .str.replace_all(r"\p{M}+", ""),
            laboratorio=pl.col("LABORATORIO TITULAR"),
            principio_activo=pl.col("PRINCIPIO ACTIVO"),
            forma_farmaceutica=pl.col("FORMA FARMACEUTICA"),
        )
        .filter(pl.col("id_cum").str.len_chars() > 1)
        .unique(subset=["id_cum"], keep="last")
    )
    logger.info("INVIMA registros tras deduplicacion por id_cum: %s", len(dataframe))
    return dataframe


def construir_upsert_invima(rows: list[dict[str, Any]]) -> Insert:
    medicamentos_table = Medicamento.__table__
    statement = pg_insert(medicamentos_table).values(rows)
    return statement.on_conflict_do_update(
        index_elements=[medicamentos_table.c.id_cum],
        set_={
            "atc": statement.excluded.atc,
            "registro_invima": statement.excluded.registro_invima,
            "estado_regulatorio": statement.excluded.estado_regulatorio,
            "nombre_limpio": statement.excluded.nombre_limpio,
            "laboratorio": statement.excluded.laboratorio,
            "principio_activo": statement.excluded.principio_activo,
            "forma_farmaceutica": statement.excluded.forma_farmaceutica,
        },
    )


async def procesar_maestro_invima(
    file_path: str,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> dict[str, int]:
    dataframe = leer_maestro_invima(file_path)
    if dataframe.is_empty():
        return {"total_filas_filtradas": 0, "upsertados": 0}

    total = 0
    insert_started_at = time.perf_counter()
    async with session_factory() as session:
        await session.execute(text(CREATE_TMP_INVIMA_SQL))
        raw_conn = await session.connection()
        asyncpg_conn = (await raw_conn.get_raw_connection()).driver_connection
        for batch in dataframe.iter_slices(n_rows=INVIMA_BATCH_SIZE):
            rows = batch.with_columns(pl.lit(EMBEDDING_STATUS_PENDING).alias("embedding_status")).to_dicts()
            for row in rows:
                row["id"] = uuid4()
            records = [tuple(row[column] for column in TMP_INVIMA_COLUMNS) for row in rows]
            if not records:
                continue
            await asyncpg_conn.copy_records_to_table(
                "tmp_invima",
                records=records,
                columns=TMP_INVIMA_COLUMNS,
            )
            total += len(records)
        await session.execute(text(MERGE_TMP_INVIMA_SQL))
        await session.commit()
    logger.info("INVIMA insercion masiva completada en %.2fs. Registros copiados: %s", time.perf_counter() - insert_started_at, total)

    return {"total_filas_filtradas": len(dataframe), "upsertados": total}
