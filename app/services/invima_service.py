from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import AsyncSessionLocal
from app.models.medicamento import Medicamento

INVIMA_BATCH_SIZE = 5000


def leer_maestro_invima(file_path: str) -> pl.DataFrame:
    if not Path(file_path).exists():
        raise FileNotFoundError(f"No existe el archivo maestro INVIMA: {file_path}")

    return (
        pl.scan_csv(file_path, separator="\t", infer_schema_length=0)
        .with_columns(
            pl.col("ESTADO REGISTRO").cast(pl.Utf8).fill_null(""),
            pl.col("ESTADO CUM").cast(pl.Utf8).fill_null(""),
            pl.col("EXPEDIENTE").cast(pl.Utf8).fill_null(""),
            pl.col("CONSECUTIVO").cast(pl.Utf8).fill_null(""),
            pl.col("ATC").cast(pl.Utf8).fill_null(""),
            pl.col("REGISTRO INVIMA").cast(pl.Utf8).fill_null(""),
            pl.col("NOMBRE COMERCIAL").cast(pl.Utf8).fill_null(""),
            pl.col("PRINCIPIO ACTIVO").cast(pl.Utf8).fill_null(""),
            pl.col("PRESENTACION COMERCIAL").cast(pl.Utf8).fill_null(""),
            pl.col("LABORATORIO TITULAR").cast(pl.Utf8).fill_null(""),
        )
        .filter(
            pl.col("ESTADO REGISTRO").str.to_lowercase().str.contains("vigente")
            & pl.col("ESTADO CUM").str.to_lowercase().str.contains("activo")
        )
        .select(
            id_cum=(pl.col("EXPEDIENTE").str.strip_chars() + "-" + pl.col("CONSECUTIVO").str.strip_chars()),
            atc=pl.col("ATC").str.strip_chars(),
            registro_invima=pl.col("REGISTRO INVIMA").str.strip_chars(),
            estado_regulatorio=(pl.col("ESTADO REGISTRO").str.strip_chars() + " / " + pl.col("ESTADO CUM").str.strip_chars()),
            nombre_limpio=pl.concat_str(
                [
                    pl.col("NOMBRE COMERCIAL").str.strip_chars(),
                    pl.col("PRINCIPIO ACTIVO").str.strip_chars(),
                    pl.col("PRESENTACION COMERCIAL").str.strip_chars(),
                ],
                separator=" ",
                ignore_nulls=True,
            ).str.replace_all(r"\s+", " ").str.strip_chars(),
            laboratorio=pl.col("LABORATORIO TITULAR").str.strip_chars(),
        )
        .filter(pl.col("id_cum").str.len_chars() > 1)
        .collect(engine="streaming")
    )


def construir_upsert_invima(rows: list[dict[str, Any]]):
    medicamentos_table = Medicamento.__table__
    statement = pg_insert(medicamentos_table).values(rows)
    return statement.on_conflict_do_update(
        index_elements=[medicamentos_table.c.id_cum],
        set_={
            "atc": statement.excluded.atc,
            "registro_invima": statement.excluded.registro_invima,
            "estado_regulatorio": statement.excluded.estado_regulatorio,
        },
    )


async def procesar_maestro_invima(file_path: str) -> dict[str, int]:
    dataframe = leer_maestro_invima(file_path)
    if dataframe.is_empty():
        return {"total_filas_filtradas": 0, "upsertados": 0}

    total = 0
    async with AsyncSessionLocal() as session:
        for batch in dataframe.iter_slices(n_rows=INVIMA_BATCH_SIZE):
            rows = batch.with_columns(pl.lit("PENDING").alias("embedding_status")).to_dicts()
            if not rows:
                continue
            await session.execute(construir_upsert_invima(rows))
            total += len(rows)
        await session.commit()

    return {"total_filas_filtradas": len(dataframe), "upsertados": total}
