from __future__ import annotations

import logging
import os
import re
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, func, literal, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.medicamento import EMBEDDING_DIMENSION, Medicamento, PrecioReferencia

EMBEDDING_MODEL = "models/text-embedding-004"
LETRA_PATTERN = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"
logger = logging.getLogger(__name__)


def _preparar_texto_busqueda(texto: str) -> str:
    normalized = re.sub(rf"([0-9])([{LETRA_PATTERN}])", r"\1 \2", texto)
    normalized = re.sub(rf"([{LETRA_PATTERN}])([0-9])", r"\1 \2", normalized)
    normalized = re.sub(rf"[^0-9{LETRA_PATTERN}]+", " ", normalized).strip().lower()
    return normalized


def _obtener_embedding_query(texto: str) -> list[float] | None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    try:
        from google.api_core.exceptions import GoogleAPIError
    except ImportError:
        GoogleAPIError = RuntimeError

    try:
        genai.configure(api_key=api_key)
        embedding = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=texto,
            task_type="retrieval_query",
        )["embedding"]
    except (GoogleAPIError, ConnectionError, TimeoutError, KeyError, TypeError, ValueError) as exc:
        logger.debug("No se pudo calcular embedding de búsqueda: %s", exc)
        return None

    if len(embedding) != EMBEDDING_DIMENSION:
        return None
    return embedding


async def buscar_medicamentos_hibrido(
    session: AsyncSession,
    texto: str,
    empresa: Optional[str],
) -> list[tuple]:
    texto_preparado = _preparar_texto_busqueda(texto)
    if not texto_preparado:
        return []

    query_embedding = _obtener_embedding_query(texto_preparado)
    statement, params = _construir_statement_hibrido(
        texto_preparado=texto_preparado,
        empresa=empresa,
        query_embedding=query_embedding,
    )
    return (await session.exec(statement.params(**params))).all()


def _construir_statement_hibrido(
    texto_preparado: str,
    empresa: Optional[str],
    query_embedding: Optional[list[float]],
):

    nombre_preparado = func.regexp_replace(
        func.regexp_replace(
            func.lower(Medicamento.nombre_limpio),
            r"([0-9])([[:alpha:]])",
            r"\1 \2",
            "g",
        ),
        r"([[:alpha:]])([0-9])",
        r"\1 \2",
        "g",
    )
    tsvector_expr = func.to_tsvector("simple", nombre_preparado)
    tsquery_expr = func.plainto_tsquery("simple", bindparam("texto_busqueda"))
    rank_expr = func.ts_rank_cd(tsvector_expr, tsquery_expr).label("rank")
    if query_embedding:
        embedding_param = bindparam("query_embedding", type_=Vector(EMBEDDING_DIMENSION))
        distancia_expr = Medicamento.embedding.op("<=>")(embedding_param).label("distancia")
    else:
        distancia_expr = literal(0.0).label("distancia")

    statement = (
        select(
            Medicamento.id,
            Medicamento.nombre_limpio,
            distancia_expr,
            Medicamento.id_cum,
            Medicamento.laboratorio,
            Medicamento.forma_farmaceutica,
            Medicamento.registro_invima,
            Medicamento.principio_activo,
            rank_expr,
        )
        .where(tsvector_expr.op("@@")(tsquery_expr))
        .order_by(rank_expr.desc(), distancia_expr.asc(), Medicamento.nombre_limpio.asc())
        .limit(10)
    )
    params = {
        "texto_busqueda": texto_preparado,
    }
    if query_embedding:
        params["query_embedding"] = query_embedding

    if empresa:
        statement = (
            statement.join(PrecioReferencia, PrecioReferencia.medicamento_id == Medicamento.id)
            .where(PrecioReferencia.empresa == bindparam("empresa"))
            .distinct()
        )
        params["empresa"] = empresa

    return statement, params
