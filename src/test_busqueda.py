import os
from typing import List, Tuple

import google.generativeai as genai
import psycopg2
from dotenv import load_dotenv


EMBEDDING_MODEL = "models/text-embedding-004"


def _to_pgvector(values: List[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def buscar_similares(texto_busqueda: str, top_k: int = 5) -> List[Tuple[int, str, float]]:
    load_dotenv()
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

    connection = psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        sslmode=os.getenv("PGSSLMODE", "prefer"),
    )

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, nombre_original, embedding <=> %s::vector AS distancia
                FROM medicamentos_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vector, query_vector, top_k),
            )
            results = cursor.fetchall()

    connection.close()
    return results


if __name__ == "__main__":
    termino = os.getenv("TEXTO_BUSQUEDA", "Dolex")
    for result_id, nombre, distancia in buscar_similares(termino, top_k=5):
        print(f"{result_id}\t{nombre}\t{distancia:.6f}")
