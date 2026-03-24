from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import polars as pl
from neo4j import GraphDatabase
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.medicamento import MedicamentoCUM

logger = logging.getLogger(__name__)


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

GOLDEN_RECORD_CHUNK_SIZE = int(os.getenv("GOLDEN_RECORD_CHUNK_SIZE", "5000"))


CONSTRAINTS_CYPHER = [
    "CREATE CONSTRAINT medicamento_oficial_cum IF NOT EXISTS FOR (m:Medicamento_Oficial) REQUIRE m.cum IS UNIQUE",
    "CREATE CONSTRAINT principio_activo_nombre IF NOT EXISTS FOR (p:Principio_Activo) REQUIRE p.nombre IS UNIQUE",
    "CREATE CONSTRAINT laboratorio_nombre IF NOT EXISTS FOR (l:Laboratorio) REQUIRE l.nombre IS UNIQUE",
]


UPSERT_GOLDEN_RECORD_CYPHER = """
UNWIND $rows AS row
MERGE (m:Medicamento_Oficial {cum: row.cum})
SET m.producto = row.producto,
    m.estado_origen = row.estado_origen,
    m.activo = row.activo,
    m.updated_at = datetime()

FOREACH (lab_name IN CASE WHEN row.laboratorio IS NULL OR trim(row.laboratorio) = '' THEN [] ELSE [row.laboratorio] END |
    MERGE (l:Laboratorio {nombre: lab_name})
    MERGE (l)-[:FABRICADO_POR]->(m)
)

FOREACH (principio IN row.principios |
    MERGE (p:Principio_Activo {nombre: principio})
    MERGE (p)-[:CONTIENE_PRINCIPIO]->(m)
)
"""


@dataclass(slots=True)
class GoldenRecordStats:
    chunks: int = 0
    rows_sql: int = 0
    rows_neo4j: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "chunks": self.chunks,
            "rows_sql": self.rows_sql,
            "rows_neo4j": self.rows_neo4j,
        }


class Neo4jGoldenRecordService:
    """Construye Golden Record en Neo4j desde medicamentos_cum."""

    def __init__(
        self,
        *,
        neo4j_uri: str = NEO4J_URI,
        neo4j_user: str = NEO4J_USER,
        neo4j_password: str = NEO4J_PASSWORD,
        neo4j_database: str = NEO4J_DATABASE,
        chunk_size: int = GOLDEN_RECORD_CHUNK_SIZE,
    ) -> None:
        self._driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self._database = neo4j_database
        self._chunk_size = max(100, chunk_size)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jGoldenRecordService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_constraints(self) -> None:
        with self._driver.session(database=self._database) as session:
            for query in CONSTRAINTS_CYPHER:
                session.run(query)

    def _upsert_rows_neo4j(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        with self._driver.session(database=self._database) as session:
            session.run(UPSERT_GOLDEN_RECORD_CYPHER, rows=rows)

    async def _fetch_sql_chunk(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        last_cum: str | None,
    ) -> tuple[pl.DataFrame, str | None]:
        """Extrae un chunk ordenado por id_cum con paginacion keyset."""
        async with session_factory() as db_session:
            stmt = select(MedicamentoCUM).order_by(MedicamentoCUM.id_cum).limit(self._chunk_size)
            if last_cum is not None:
                stmt = stmt.where(MedicamentoCUM.id_cum > last_cum)

            result = await db_session.exec(stmt)
            items = result.all()

        if not items:
            return pl.DataFrame(), None

        rows = [
            {
                "cum": item.id_cum,
                "producto": item.descripcioncomercial or item.producto,
                "estado_origen": item.estado_origen,
                "estadocum": item.estadocum,
                "titular": item.titular,
                "principio_activo_raw": item.principioactivo,
            }
            for item in items
        ]

        return pl.DataFrame(rows), items[-1].id_cum

    @staticmethod
    def transform_chunk_with_polars(df: pl.DataFrame) -> pl.DataFrame:
        """Limpia y divide principio_activo con regex vectorizado de Polars."""
        if df.is_empty():
            return pl.DataFrame(
                schema={
                    "cum": pl.Utf8,
                    "producto": pl.Utf8,
                    "estado_origen": pl.Utf8,
                    "activo": pl.Boolean,
                    "laboratorio": pl.Utf8,
                    "principios": pl.List(pl.Utf8),
                }
            )

        estado_expr = (
            pl.when(pl.col("estado_origen").cast(pl.Utf8).str.strip_chars() == "")
            .then(None)
            .otherwise(pl.col("estado_origen"))
            .fill_null(pl.col("estadocum"))
            .cast(pl.Utf8)
            .str.strip_chars()
            .alias("estado_origen")
        )

        activo_expr = (
            pl.coalesce([
                pl.col("estado_origen").cast(pl.Utf8),
                pl.col("estadocum").cast(pl.Utf8),
                pl.lit(""),
            ])
            .str.to_lowercase()
            .str.contains(r"(vigente|activo)")
            .fill_null(False)
            & ~pl.coalesce([
                pl.col("estado_origen").cast(pl.Utf8),
                pl.col("estadocum").cast(pl.Utf8),
                pl.lit(""),
            ])
            .str.to_lowercase()
            .str.contains(r"(vencid|inactiv|cancelad)")
            .fill_null(False)
        ).alias("activo")

        principios_expr = (
            pl.when(
                pl.col("principio_activo_raw").cast(pl.Utf8).fill_null("").str.strip_chars() == ""
            )
            .then(pl.lit([], dtype=pl.List(pl.Utf8)))
            .otherwise(
                pl.col("principio_activo_raw")
                .cast(pl.Utf8)
                .str.to_uppercase()
                .str.replace_all(r"\s+", " ")
                .str.replace_all(r"\s*(\+|/|\bY\b|\bCON\b)\s*", "|")
                .str.split("|")
                .list.eval(pl.element().str.strip_chars())
                .list.eval(pl.element().str.replace_all(r"\s+", " "))
                .list.eval(pl.element().str.strip_chars())
            )
            .alias("principios")
        )

        base_df = (
            df.with_columns(
                [
                    pl.col("cum").cast(pl.Utf8).str.strip_chars(),
                    pl.col("producto").cast(pl.Utf8).fill_null("").str.strip_chars(),
                    pl.col("titular").cast(pl.Utf8).fill_null("").str.strip_chars().alias("laboratorio"),
                    estado_expr,
                    activo_expr,
                    principios_expr,
                ]
            )
            .with_columns(
                [
                    pl.when(pl.col("laboratorio") == "").then(None).otherwise(pl.col("laboratorio")).alias("laboratorio"),
                    pl.col("principios").list.unique(),
                ]
            )
            .select(["cum", "producto", "estado_origen", "activo", "laboratorio", "principios"])
        )

        # Validacion vectorizada con explode para limpiar principios vacios.
        # Esta parte usa explode() para cumplir con el requerimiento de aplanado eficiente.
        principles_flat = (
            base_df.explode("principios")
            .select(["cum", pl.col("principios").alias("principio")])
            .with_columns(pl.col("principio").cast(pl.Utf8).fill_null("").str.strip_chars())
            .filter(pl.col("principio") != "")
            .group_by("cum")
            .agg(pl.col("principio").unique().alias("principios_limpios"))
        )

        return base_df.join(principles_flat, on="cum", how="left").with_columns(
            pl.when(pl.col("principios_limpios").is_null())
            .then(pl.lit([], dtype=pl.List(pl.Utf8)))
            .otherwise(pl.col("principios_limpios"))
            .alias("principios")
        ).drop("principios_limpios")

    async def build_golden_record(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> dict[str, int]:
        self._ensure_constraints()

        last_cum: str | None = None
        stats = GoldenRecordStats()

        while True:
            sql_df, last_cum_candidate = await self._fetch_sql_chunk(session_factory, last_cum)
            if sql_df.is_empty():
                break

            transformed_df = self.transform_chunk_with_polars(sql_df)
            rows_to_ingest = transformed_df.to_dicts()

            self._upsert_rows_neo4j(rows_to_ingest)

            stats.chunks += 1
            stats.rows_sql += sql_df.height
            stats.rows_neo4j += len(rows_to_ingest)
            last_cum = last_cum_candidate

            logger.info(
                "GoldenRecord chunk=%s sql_rows=%s neo4j_rows=%s last_cum=%s",
                stats.chunks,
                sql_df.height,
                len(rows_to_ingest),
                last_cum,
            )

        return stats.to_dict()
