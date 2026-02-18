import argparse
import os
from pathlib import Path

import pandas as pd
import psycopg2


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta tarifario por empresa.")
    parser.add_argument("--empresa", required=True, help="Nombre de la empresa a exportar.")
    parser.add_argument(
        "--output",
        default=None,
        help="Ruta de salida opcional para el Excel. Si no se especifica, se usa /output/tarifario_<empresa>.xlsx",
    )
    return parser.parse_args()


def _connect():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        sslmode=os.getenv("PGSSLMODE", "prefer"),
    )


def main() -> None:
    args = _parse_args()
    output_path = Path(args.output) if args.output else OUTPUT_DIR / f"tarifario_{args.empresa}.xlsx"

    connection = None
    try:
        connection = _connect()
        query = """
            SELECT nombre_original AS "Nombre", precio AS "Precio", fu AS "FU", vpc AS "VPC"
            FROM medicamentos_embeddings
            WHERE empresa = %s
            ORDER BY nombre_original
        """
        df = pd.read_sql_query(query, connection, params=[args.empresa])
    finally:
        if connection is not None:
            connection.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        sheet_name = "Tarifario"
        df.to_excel(writer, sheet_name=sheet_name, index=False)

        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        money_fmt = workbook.add_format({"num_format": "#,##0.00"})
        fu_fmt = workbook.add_format({"num_format": "0.00000000"})

        for col_idx, col_name in enumerate(df.columns):
            if col_name == "FU":
                worksheet.set_column(col_idx, col_idx, 14, fu_fmt)
            elif col_name in {"Precio", "VPC"}:
                worksheet.set_column(col_idx, col_idx, 14, money_fmt)
            else:
                worksheet.set_column(col_idx, col_idx, 40)

    print(f"Tarifario exportado: {output_path}")


if __name__ == "__main__":
    main()
