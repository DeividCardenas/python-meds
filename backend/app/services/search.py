from __future__ import annotations

import asyncio
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
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        return None

    try:
        client = genai.Client(api_key=api_key)
        embedding = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texto,
            config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        ).embeddings[0].values
    except (ConnectionError, TimeoutError, KeyError, TypeError, ValueError, Exception) as exc:
        logger.debug("No se pudo calcular embedding de búsqueda: %s", exc)
        return None

    if len(embedding) != EMBEDDING_DIMENSION:
        return None
    return embedding


async def _obtener_embedding_query_async(texto: str) -> list[float] | None:
    """Wrapper asíncrono: ejecuta la llamada HTTP síncrona a Google en un
    thread pool para no bloquear el event loop de uvicorn (Anomalía 4)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _obtener_embedding_query, texto)


async def buscar_medicamentos_hibrido(
    session: AsyncSession,
    texto: str,
    empresa: Optional[str],
    solo_activos: bool = True,
    forma_farmaceutica: Optional[str] = None,
) -> list[tuple]:
    texto_preparado = _preparar_texto_busqueda(texto)
    if not texto_preparado:
        return []

    # Llamada asíncrona: la API de embeddings se ejecuta en thread pool (Fix 4).
    query_embedding = await _obtener_embedding_query_async(texto_preparado)
    statement, params = _construir_statement_hibrido(
        texto_preparado=texto_preparado,
        empresa=empresa,
        query_embedding=query_embedding,
        solo_activos=solo_activos,
        forma_farmaceutica=forma_farmaceutica,
    )
    return (await session.exec(statement.params(**params))).all()


def _construir_statement_hibrido(
    texto_preparado: str,
    empresa: Optional[str],
    query_embedding: Optional[list[float]],
    solo_activos: bool = True,
    forma_farmaceutica: Optional[str] = None,
):

    # Usa la columna STORED GENERATED nombre_tsvector (migración 0018) para FTS.
    # El índice GIN ix_medicamentos_nombre_tsvector_gin hace que @@ sea O(log N+k)
    # en lugar de seqscan O(N) con to_tsvector() inline sobre regexp_replace.
    # Fix para Anomalía 2 (ALTO): p(95) buscarMedicamentos 6.46s → < 1500ms.
    tsquery_expr = func.plainto_tsquery("simple", bindparam("texto_busqueda"))
    rank_expr = func.ts_rank_cd(Medicamento.nombre_tsvector, tsquery_expr).label("rank")
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
            Medicamento.activo,
            Medicamento.estado_cum,
            rank_expr,
        )
        .where(Medicamento.nombre_tsvector.op("@@")(tsquery_expr))
        .order_by(rank_expr.desc(), distancia_expr.asc(), Medicamento.nombre_limpio.asc())
        .limit(10)
    )
    params = {
        "texto_busqueda": texto_preparado,
    }
    if query_embedding:
        params["query_embedding"] = query_embedding

    # Filtro: solo medicamentos activos (CUM Vigente/Activo o sin CUM vinculado)
    if solo_activos:
        statement = statement.where(Medicamento.activo == True)  # noqa: E712

    # Filtro: forma farmacéutica (búsqueda parcial, case-insensitive)
    if forma_farmaceutica and forma_farmaceutica.strip():
        ff_norm = forma_farmaceutica.strip().lower()
        statement = statement.where(
            func.lower(Medicamento.forma_farmaceutica).contains(ff_norm)
        )

    if empresa:
        statement = (
            statement.join(PrecioReferencia, PrecioReferencia.medicamento_id == Medicamento.id)
            .where(PrecioReferencia.empresa == bindparam("empresa"))
            .distinct()
        )
        params["empresa"] = empresa

    return statement, params
