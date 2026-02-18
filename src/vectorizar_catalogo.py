import os
import time
import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import google.generativeai as genai
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILE = BASE_DIR / "output" / "resultado_cruce_optimizado.xlsx"
EMBEDDING_MODEL = "models/text-embedding-004"
SLEEP_SECONDS = float(os.getenv("EMBEDDING_SLEEP_SECONDS", "0.2"))
MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "3"))
INSERT_BATCH_SIZE = int(os.getenv("PG_INSERT_BATCH_SIZE", "100"))


def _pick_source_column(df: pd.DataFrame) -> str:
    for column_name in ("nombre_limpio", "Producto"):
        if column_name in df.columns:
            return column_name
    raise KeyError("No se encontró la columna 'nombre_limpio' ni 'Producto' en el Excel.")


def _pick_company_column(df: pd.DataFrame) -> Optional[str]:
    for column_name in ("Empresa", "empresa", "Laboratorio", "laboratorio", "Fuente", "fuente"):
        if column_name in df.columns:
            return column_name
    return None


def _pick_numeric_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    for column_name in candidates:
        if column_name in df.columns:
            return column_name
    return None


def _normalize_decimal(value) -> Optional[float]:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _extract_records(
    df: pd.DataFrame,
    name_column: str,
    company_column: Optional[str],
    default_company: Optional[str],
) -> List[Tuple[str, str, Optional[float], Optional[float], Optional[float]]]:
    if company_column is None and not default_company:
        raise KeyError("No se encontró columna Empresa/Laboratorio/Fuente. Use --empresa para asignar una empresa por defecto.")

    precio_column = _pick_numeric_column(df, "Precio", "precio")
    fu_column = _pick_numeric_column(df, "FU", "fu")
    vpc_column = _pick_numeric_column(df, "VPC", "vpc")

    company_values = df[company_column] if company_column else pd.Series([default_company] * len(df))
    precio_values = df[precio_column] if precio_column else pd.Series([None] * len(df))
    fu_values = df[fu_column] if fu_column else pd.Series([None] * len(df))
    vpc_values = df[vpc_column] if vpc_column else pd.Series([None] * len(df))

    records: Dict[Tuple[str, str], Tuple[str, str, Optional[float], Optional[float], Optional[float]]] = {}
    for raw_name, raw_company, raw_precio, raw_fu, raw_vpc in zip(
        df[name_column], company_values, precio_values, fu_values, vpc_values
    ):
        if pd.isna(raw_name):
            continue
        medicine_name = str(raw_name).strip()
        if not medicine_name:
            continue

        company_name = str(raw_company).strip() if raw_company is not None else ""
        if not company_name:
            company_name = str(default_company or "").strip()
        if not company_name:
            continue

        precio = _normalize_decimal(raw_precio) if precio_column else None
        fu = _normalize_decimal(raw_fu) if fu_column else None
        vpc = _normalize_decimal(raw_vpc) if vpc_column else None
        records[(medicine_name, company_name)] = (medicine_name, company_name, precio, fu, vpc)
    return list(records.values())


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


def _insert_batch(cursor, rows: List[tuple]) -> None:
    execute_values(
        cursor,
        """
        INSERT INTO medicamentos_embeddings (nombre_original, empresa, precio, fu, vpc, embedding)
        VALUES %s
        ON CONFLICT (nombre_original, empresa) DO UPDATE
        SET precio = EXCLUDED.precio,
            fu = EXCLUDED.fu,
            vpc = EXCLUDED.vpc,
            embedding = EXCLUDED.embedding
        """,
        rows,
        template="(%s, %s, %s, %s, %s, %s::vector)",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vectoriza catálogo e inserta embeddings en Postgres.")
    parser.add_argument("--empresa", default=None, help="Empresa por defecto cuando el Excel no contiene columna Empresa/Laboratorio.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("Falta GOOGLE_API_KEY en variables de entorno.")

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"No existe el archivo fuente: {SOURCE_FILE}")

    genai.configure(api_key=api_key)

    df = pd.read_excel(SOURCE_FILE)
    source_column = _pick_source_column(df)
    company_column = _pick_company_column(df)
    records = _extract_records(df, source_column, company_column, args.empresa)
    unique_names = sorted({record[0] for record in records})

    if not records:
        print("No hay medicamentos válidos para vectorizar/insertar.")
        return

    connection = None
    inserted_count = 0
    try:
        connection = psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            port=os.getenv("PGPORT", "5432"),
            dbname=os.getenv("PGDATABASE", "postgres"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", ""),
            sslmode=os.getenv("PGSSLMODE", "prefer"),
        )

        embeddings_cache: Dict[str, str] = {}
        for idx, medicine_name in enumerate(unique_names, start=1):
            try:
                embedding = _embed_text(medicine_name)
                embeddings_cache[medicine_name] = _to_pgvector(embedding)
                if idx % INSERT_BATCH_SIZE == 0:
                    print(f"Procesados {idx}/{len(unique_names)} medicamentos únicos...")
            except Exception as exc:  # noqa: BLE001 - se registra y continúa con el resto.
                print(f"[ERROR] No se procesó '{medicine_name}': {exc}")

        rows_to_insert = []
        for medicine_name, company_name, precio, fu, vpc in records:
            vector = embeddings_cache.get(medicine_name)
            if vector is None:
                continue
            rows_to_insert.append((medicine_name, company_name, precio, fu, vpc, vector))

        with connection.cursor() as cursor:
            for i in range(0, len(rows_to_insert), INSERT_BATCH_SIZE):
                batch = rows_to_insert[i : i + INSERT_BATCH_SIZE]
                _insert_batch(cursor, batch)
                inserted_count += len(batch)
        connection.commit()
    finally:
        if connection is not None:
            connection.close()
    if inserted_count == 0:
        print("No se generaron embeddings para insertar.")
        return
    print(
        f"Finalizado. Insertados/actualizados {inserted_count} registros "
        f"con {len(unique_names)} embeddings únicos."
    )


if __name__ == "__main__":
    main()
