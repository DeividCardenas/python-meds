"""Polars-powered pharmaceutical text normalization pipeline.

Pharmaceutical product names are notoriously messy:
  - "AMOXICILINA 500MG CAP" vs "AMOXICILINA 500 MG CAPSULA"
  - Packaging noise: "CAJA X 30", "BLISTER X 10"
  - Unicode accents, mixed case, irregular spacing

This module exposes ``normalize_pharma_text`` for single strings and
``normalize_series`` for Polars Series, applying a deterministic vectorized
pipeline that produces a canonical lowercase ASCII form suitable for
trigram and FTS matching against the Golden Source (genhospi_catalog).
"""
from __future__ import annotations

import re
import unicodedata

import polars as pl

# ---------------------------------------------------------------------------
# Compiled regex patterns – evaluated once at import time for efficiency
# ---------------------------------------------------------------------------

# Packaging / quantity noise to strip BEFORE core matching.
# Matches constructs like: "CAJA X 30", "BLISTER 10", "FRASCO X 120ML"
_PACKAGING_NOISE = re.compile(
    r"\b(?:caja|blister|frasco|ampolla|vial|tableta|tabletas|capsula|capsulas|"
    r"comprimidos?|sobres?|parche|jeringa|unidades?|und\.?|tab\.?|cap\.?)"
    r"(?:\s*x\s*|\s+)\d+(?:\s*(?:ml|mg|g|mcg|ui|iu|miu))?\b",
    re.IGNORECASE,
)

# Dosage form suffixes that add noise when not part of the active ingredient
_FORM_NOISE = re.compile(
    r"\b(?:oral|intravenoso|iv\b|im\b|sc\b|topico|topica|inyectable|"
    r"soluble|efervescente|rectal|sublingual|inhalador|spray|solucion|"
    r"suspension|emulsion|crema|gel|pomada|jarabe|gotas)\b",
    re.IGNORECASE,
)

# Digit–letter and letter–digit boundaries (e.g. "500MG" → "500 MG")
_DIG_LETTER = re.compile(r"([0-9])([A-Za-zÁÉÍÓÚÜÑáéíóúüñ])")
_LETTER_DIG = re.compile(r"([A-Za-zÁÉÍÓÚÜÑáéíóúüñ])([0-9])")


def normalize_pharma_text(text: str) -> str:
    """
    Apply deterministic normalization to a single pharmaceutical product name.

    Pipeline:
      1. Normalize Unicode (NFKD) and strip accents → lowercase ASCII
      2. Insert space between digit/letter boundaries
      3. Strip packaging/quantity noise (e.g. "CAJA X 30")
      4. Strip dosage form noise
      5. Remove non-alphanumeric characters except spaces
      6. Collapse whitespace

    Returns the cleaned lowercase ASCII string, or ``""`` for empty input.
    """
    if not text or not text.strip():
        return ""

    # 1. Unicode normalization → strip accents → lowercase
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii").lower()

    # 2. Space between digits and letters
    ascii_text = _DIG_LETTER.sub(r"\1 \2", ascii_text)
    ascii_text = _LETTER_DIG.sub(r"\1 \2", ascii_text)

    # 3. Strip packaging noise
    ascii_text = _PACKAGING_NOISE.sub(" ", ascii_text)

    # 4. Strip dosage form noise
    ascii_text = _FORM_NOISE.sub(" ", ascii_text)

    # 5. Remove non-alphanumeric (keep spaces)
    ascii_text = re.sub(r"[^0-9a-z\s]", " ", ascii_text)

    # 6. Collapse whitespace
    return re.sub(r"\s+", " ", ascii_text).strip()


def normalize_series(series: pl.Series) -> pl.Series:
    """
    Apply ``normalize_pharma_text`` to a Polars :class:`~polars.Series` of
    strings using ``map_elements`` for vectorized execution.

    Returns a new ``Utf8`` Series with normalized values (``None`` → ``""``).
    """
    # Fill nulls with empty string so the lambda is always called with a str
    filled = series.fill_null("")
    return filled.map_elements(
        normalize_pharma_text,
        return_dtype=pl.Utf8,
    )


def normalize_dataframe_column(df: pl.DataFrame, col: str) -> pl.DataFrame:
    """
    Return *df* with an additional column ``<col>_normalized`` containing
    the Polars-normalized values of *col*.

    Useful for pre-processing an entire supplier price list before passing
    individual descriptions to the database fuzzy matcher.
    """
    normalized = normalize_series(df[col])
    return df.with_columns(normalized.alias(f"{col}_normalized"))
