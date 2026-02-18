import os
from typing import List, Optional, Tuple

import google.generativeai as genai
import psycopg2
from dotenv import load_dotenv


EMBEDDING_MODEL = "models/text-embedding-004"
load_dotenv()


def _to_pgvector(values: List[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def buscar_similares(
    texto_busqueda: str,
    empresa: Optional[str] = None,
    top_k: int = 5,
) -> List[Tuple[int, str, str, Optional[float], Optional[float], Optional[float], float]]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("Falta GOOGLE_API_KEY en variables de entorno.")

    genai.configure(api_key=api_key)
    query_embedding = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=texto_busqueda,
        task_type="retrieval_query",
    )["embedding"]
    query_vector = _to_pgvector(query_embedding)

    connection = None
    try:
        connection = psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            port=os.getenv("PGPORT", "5432"),
            dbname=os.getenv("PGDATABASE", "postgres"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", ""),
            sslmode=os.getenv("PGSSLMODE", "prefer"),
        )

        with connection.cursor() as cursor:
            if empresa is not None:
                cursor.execute(
                    """
                    SELECT id, nombre_original, empresa, precio, fu, vpc, embedding <=> %s::vector AS distancia
                    FROM medicamentos_embeddings
                    WHERE empresa = %s
                    ORDER BY distancia
                    LIMIT %s
                    """,
                    (query_vector, empresa, top_k),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, nombre_original, empresa, precio, fu, vpc, embedding <=> %s::vector AS distancia
                    FROM medicamentos_embeddings
                    ORDER BY distancia
                    LIMIT %s
                    """,
                    (query_vector, top_k),
                )
            return cursor.fetchall()
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    termino = os.getenv("TEXTO_BUSQUEDA", "Dolex")
    empresa = os.getenv("EMPRESA_BUSQUEDA")
    for result_id, nombre, empresa_nombre, precio, fu, vpc, distancia in buscar_similares(termino, empresa=empresa, top_k=5):
        print(f"{result_id}\t{nombre}\t{empresa_nombre}\t{precio}\t{fu}\t{vpc}\t{distancia:.6f}")
