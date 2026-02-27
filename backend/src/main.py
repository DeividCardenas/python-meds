import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

import polars as pl


# ------------------------------------------------------------
# Configuración
# ------------------------------------------------------------
INPUT_DIR = Path(__file__).resolve().parent.parent / "input"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "reporte_cruzado.xlsx"

# Columnas esperadas
PRODUCT_NAME_COLS = ["Producto", "Nombre"]
NUMERIC_COLS = ["Precio", "Costo", "FU", "VPC"]

# Palabras clave para forma farmacéutica (se pueden ampliar)
FORMA_FARMACEUTICA_KEYWORDS = [
    "TAB", "TABLETA", "TABLETAS",
    "CAP", "CAPS", "CAPSULA", "CAPSULAS",
    "SOL", "SOLUCION",
    "JBE", "JARABE",
    "SUSP", "SUSPENSION",
    "AMP", "AMPO", "AMPOLLA", "AMPOLLAS",
    "CREMA", "UNG", "UNGUENTO",
    "GEL",
    "PARCHE", "PARCHES",
    "GOTAS", "GOTA",
]

# Unidades para concentración
UNIDADES = ["MG", "G", "MCG", "ML", "%", "GR", "MGR", "µG", "KG", "MGM"]


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------
def find_input_files(directory: Path) -> List[Path]:
    exts = ("*.csv", "*.tsv", "*.txt", "*.xlsx", "*.xls")
    files: List[Path] = []
    for pattern in exts:
        files.extend(directory.glob(pattern))
    return sorted(files)


def read_any(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix in [".csv"]:
        return pl.read_csv(path, infer_schema_length=2000)
    if suffix in [".tsv", ".txt"]:
        return pl.read_csv(path, separator="\t", infer_schema_length=2000)
    if suffix in [".xlsx", ".xls"]:
        # polars puede leer Excel directamente
        return pl.read_excel(path)
    raise ValueError(f"Extensión no soportada: {path}")


def pick_first_existing(df: pl.DataFrame, candidates: Iterable[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"No se encontró ninguna de las columnas: {candidates}")


def normalize_numeric(val) -> Optional[float]:
    """
    Normaliza strings numéricos con separadores mixtos a float.
    No redondea.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    # Elimina espacios y caracteres no numéricos/.,-
    s = re.sub(r"[^\d,.\-]", "", s)

    # Determina el último separador decimal candidato
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")
    last_sep = max(last_comma, last_dot)

    if last_sep == -1:
        cleaned = re.sub(r"[^\d\-]", "", s)
        return float(cleaned) if cleaned else None

    decimal_sep = s[last_sep]
    integer_part = re.sub(r"[^\d\-]", "", s[:last_sep])
    decimal_part = re.sub(r"[^\d]", "", s[last_sep + 1 :])

    cleaned = f"{integer_part}.{decimal_part}" if decimal_part else integer_part
    return float(cleaned) if cleaned else None


def normalize_numeric_columns(df: pl.DataFrame, cols: List[str]) -> pl.DataFrame:
    cols_present = [c for c in cols if c in df.columns]
    if not cols_present:
        return df
    return df.with_columns(
        [
            pl.col(c).map_elements(normalize_numeric, return_dtype=pl.Float64).alias(c)
            for c in cols_present
        ]
    )


def clean_text_basic(txt: str) -> str:
    txt = txt.upper()
    txt = re.sub(r"[^\w\s]", " ", txt)  # elimina puntuación
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def extract_fields(df: pl.DataFrame, name_col: str) -> pl.DataFrame:
    # Patrones
    unidades_pattern = "|".join(map(re.escape, UNIDADES))
    concentration_regex = rf"(\d+[.,]?\d*\s*(?:{unidades_pattern}))"
    forma_pattern = "|".join(FORMA_FARMACEUTICA_KEYWORDS)

    return df.with_columns(
        [
            # Limpieza base
            pl.col(name_col)
            .cast(pl.Utf8)
            .fill_null("")
            .map_elements(clean_text_basic)
            .alias("producto_limpio"),
            # Concentración
            pl.col(name_col)
            .cast(pl.Utf8)
            .fill_null("")
            .str.extract(concentration_regex, group_index=1)
            .alias("concentracion"),
            # Forma farmacéutica
            pl.col(name_col)
            .cast(pl.Utf8)
            .fill_null("")
            .str.extract(rf"\b({forma_pattern})\b", group_index=1)
            .alias("forma_farmaceutica"),
        ]
    ).with_columns(
        [
            # Principio activo: producto sin concentración ni forma
            pl.when(
                pl.col("producto_limpio").str.lengths() > 0
            )
            .then(
                pl.col("producto_limpio")
                .str.replace_all(concentration_regex, " ")
                .str.replace_all(rf"\b({forma_pattern})\b", " ")
                .str.replace_all(r"\s+", " ")
                .str.strip()
            )
            .otherwise("")
            .alias("principio_activo"),
            # Laboratorio (heurística: última palabra si es mayúscula corta)
            pl.col("producto_limpio")
            .str.extract(r"\b([A-Z]{2,10})$", group_index=1)
            .alias("laboratorio"),
        ]
    )


def build_key(df: pl.DataFrame, base_cols: List[str]) -> pl.DataFrame:
    cols_present = [c for c in base_cols if c in df.columns]
    if not cols_present:
        raise KeyError("No hay columnas base para llave normalizada.")
    return df.with_columns(
        pl.concat_str([pl.col(c).fill_null("").cast(pl.Utf8) for c in cols_present], separator=" ")
        .map_elements(clean_text_basic)
        .str.replace_all(r"\s+", " ")
        .str.strip()
        .alias("llave_norm")
    )


def autosize_columns(writer, dataframe, sheet_name: str):
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(dataframe.columns):
        max_len = max(
            [len(str(col))]
            + [len(str(x)) for x in dataframe[col].astype(str).tolist()]
        )
        worksheet.set_column(idx, idx, min(max_len + 2, 60))


def export_with_format(df: pl.DataFrame, path: Path):
    import pandas as pd  # solo para la exportación con formato

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = df.to_pandas()

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        sheet_name = "Cruce"
        pdf.to_excel(writer, sheet_name=sheet_name, index=False)

        workbook = writer.book
        worksheet = writer.sheets[sheet_name]

        money_fmt = workbook.add_format({"num_format": "#,##0.00"})
        fu_fmt = workbook.add_format({"num_format": "0.00000000"})

        # Aplica formatos
        for col_idx, col_name in enumerate(pdf.columns):
            if col_name == "FU":
                worksheet.set_column(col_idx, col_idx, None, fu_fmt)
            if col_name in {"Precio", "Costo", "VPC"}:
                worksheet.set_column(col_idx, col_idx, None, money_fmt)

        autosize_columns(writer, pdf, sheet_name)


# ------------------------------------------------------------
# Pipeline principal
# ------------------------------------------------------------
def main():
    files = find_input_files(INPUT_DIR)
    if not files:
        print(f"No se encontraron archivos en {INPUT_DIR}", file=sys.stderr)
        sys.exit(1)

    consumo_frames = []
    maestro_frames = []

    for f in files:
        df = read_any(f)
        try:
            name_col = pick_first_existing(df, PRODUCT_NAME_COLS)
        except KeyError:
            # Si no tiene columna de producto, lo ignoramos
            continue

        # Normaliza numéricos
        df = normalize_numeric_columns(df, NUMERIC_COLS)

        # Enriquecimiento
        df = extract_fields(df, name_col)
        df = build_key(df, ["producto_limpio", "principio_activo", "laboratorio"])

        # Heurística de clasificación por nombre de archivo
        fname = f.name.lower()
        if "maestro" in fname or "precio" in fname:
            maestro_frames.append(df)
        else:
            consumo_frames.append(df)

    if not consumo_frames:
        print("No se identificaron archivos de Consumo.", file=sys.stderr)
        sys.exit(1)
    if not maestro_frames:
        print("No se identificaron archivos de Maestro de Precios.", file=sys.stderr)
        sys.exit(1)

    consumo = pl.concat(consumo_frames, how="vertical_relaxed")
    maestro = pl.concat(maestro_frames, how="vertical_relaxed")

    # Deduplicar maestro por llave_norm conservando el último
    maestro = maestro.sort("llave_norm").unique(subset=["llave_norm"], keep="last")

    # Left join
    joined = consumo.join(maestro, on="llave_norm", how="left", suffix="_maestro")

    export_with_format(joined, OUTPUT_FILE)
    print(f"Archivo generado: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()