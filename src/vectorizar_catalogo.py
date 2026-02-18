import os
import time
from pathlib import Path
from typing import Iterable, List

import google.generativeai as genai
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILE = BASE_DIR / "output" / "resultado_cruce_optimizado.xlsx"
EMBEDDING_MODEL = "models/text-embedding-004"
SLEEP_SECONDS = float(os.getenv("EMBEDDING_SLEEP_SECONDS", "0.2"))
MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))


def _pick_source_column(df: pd.DataFrame) -> str:
    for column_name in ("nombre_limpio", "Producto"):
        if column_name in df.columns:
            return column_name
    raise KeyError("No se encontró la columna 'nombre_limpio' ni 'Producto' en el Excel.")


def _extract_unique_names(df: pd.DataFrame, column_name: str) -> List[str]:
    # Optimización crítica: vectorizar solo valores únicos y no vacíos.
    names = (
        df[column_name]
        .dropna()
        .astype(str)
        .map(str.strip)
    )
    return names[names != ""].drop_duplicates().tolist()


def _to_pgvector(values: Iterable[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _embed_text(text: str) -> List[float]:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type="retrieval_document",
            )
            vector = response["embedding"]
            if len(vector) != 768:
                raise ValueError(f"Dimensión inválida: {len(vector)}. Se esperaban 768.")
            time.sleep(SLEEP_SECONDS)
            return vector
        except Exception as exc:  # noqa: BLE001 - control explícito de fallos de API.
            last_error = exc
            wait_time = SLEEP_SECONDS * attempt
            print(f"[WARN] Error embedding '{text[:60]}...' (intento {attempt}/{MAX_RETRIES}): {exc}")
            time.sleep(wait_time)
    raise RuntimeError(f"No se pudo generar embedding para: {text}") from last_error


def main() -> None:
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("Falta GOOGLE_API_KEY en variables de entorno.")

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"No existe el archivo fuente: {SOURCE_FILE}")

    genai.configure(api_key=api_key)

    df = pd.read_excel(SOURCE_FILE)
    source_column = _pick_source_column(df)
    unique_names = _extract_unique_names(df, source_column)

    if not unique_names:
        print("No hay medicamentos válidos para vectorizar.")
        return

    connection = psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        sslmode=os.getenv("PGSSLMODE", "prefer"),
    )

    rows_to_insert = []
    for idx, medicine_name in enumerate(unique_names, start=1):
        try:
            embedding = _embed_text(medicine_name)
            rows_to_insert.append((medicine_name, _to_pgvector(embedding)))
            if idx % 100 == 0:
                print(f"Procesados {idx}/{len(unique_names)} medicamentos únicos...")
        except Exception as exc:  # noqa: BLE001 - se registra y continúa con el resto.
            print(f"[ERROR] No se procesó '{medicine_name}': {exc}")

    if not rows_to_insert:
        print("No se generaron embeddings para insertar.")
        connection.close()
        return

    with connection:
        with connection.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO medicamentos_embeddings (nombre_original, embedding)
                VALUES %s
                ON CONFLICT (nombre_original) DO UPDATE
                SET embedding = EXCLUDED.embedding
                """,
                rows_to_insert,
                template="(%s, %s::vector)",
            )

    connection.close()
    print(
        f"Finalizado. Vectorizados {len(rows_to_insert)} de {len(unique_names)} "
        "medicamentos únicos."
    )


if __name__ == "__main__":
    main()
