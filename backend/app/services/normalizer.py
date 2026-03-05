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

# ---------------------------------------------------------------------------
# Supplier-specific normalisation helpers
# ---------------------------------------------------------------------------

# Salt / polymorph qualifiers that are NOT part of the canonical INN.
# Stripping them improves FTS recall: "Amoxicilina Trihidrato 875 mg"
# becomes "amoxicilina 875 mg" which matches the catalog entry.
_SALT_QUALIFIERS = re.compile(
    r"\b(?:clorhidrato|hidrocloruro|trihidrato|monohidrato|dihidrato|"
    r"anhidro|mesilato|mesilas|etabonato|besylato|tartrato|maleato|"
    r"fumarato|gluconato)\b",
    re.IGNORECASE,
)

# Concatenated packaging tokens used in some supplier formats (e.g. LA SANTE).
# Applied BEFORE digit/letter spacing so the full token is matched:
#   "PPSFCOX50ML" → removed (not "ppsfcox 50 ml" left in the query)
_CONCAT_PACKAGING_NOISE = re.compile(
    r"\b(?:ppsfcox|fcox|cjax|jbefcox|grancjax|cjaxsob|fcoxsob)\d+\w*\b",
    re.IGNORECASE,
)

# Provider-specific trailing codes that carry no pharmacological information.
# Applied AFTER step 5 (non-alnum strip) so only standalone tokens remain:
#   "COL" (country), "EOF" (end-of-formulary), "NI" (no incluido), etc.
_PROVIDER_SUFFIX_NOISE = re.compile(
    r"\b(?:col|eof|ni|pps|fco|cja|jbe|sob)\b",
    re.IGNORECASE,
)

# Pharmaceutical abbreviations used by some suppliers (e.g. LA SANTE).
# Keys are *lower-cased* abbreviated forms; values are the full INN.
_PHARMA_ABBREVIATIONS: dict[str, str] = {
    "claritromi": "claritromicina",
    "gluco": "glucosamina",
    "condro": "condroitin",
}
# Pre-compile so we do a single regex pass per string (longest match first)
_ABBREV_WORDS_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_PHARMA_ABBREVIATIONS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def normalize_pharma_text(text: str) -> str:
    """
    Apply deterministic normalization to a single pharmaceutical product name.

    Pipeline:
      1.   Normalize Unicode (NFKD) and strip accents → lowercase ASCII
      1.5. Expand supplier-specific pharmaceutical abbreviations
      1.6. Strip concatenated packaging codes (e.g. "PPSFCOX50ML", "CJAX4")
      2.   Insert space between digit/letter boundaries
      3.   Strip packaging/quantity noise (e.g. "CAJA X 30")
      4.   Strip dosage form noise
      4.5. Strip salt/polymorph qualifiers (e.g. "Trihidrato", "Mesilato")
      5.   Remove non-alphanumeric characters except spaces
      5.5. Strip provider-specific trailing codes (COL, EOF, NI, PPS…)
      6.   Collapse whitespace

    Returns the cleaned lowercase ASCII string, or ``""`` for empty input.
    """
    if not text or not text.strip():
        return ""

    # 1. Unicode normalization → strip accents → lowercase
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii").lower()

    # 1.5. Expand supplier-specific abbreviations (e.g. "CLARITROMI" → "claritromicina")
    ascii_text = _ABBREV_WORDS_RE.sub(
        lambda m: _PHARMA_ABBREVIATIONS[m.group(0).lower()], ascii_text
    )

    # 1.6. Strip concatenated packaging codes before digit/letter spacing
    ascii_text = _CONCAT_PACKAGING_NOISE.sub(" ", ascii_text)

    # 2. Space between digits and letters
    ascii_text = _DIG_LETTER.sub(r"\1 \2", ascii_text)
    ascii_text = _LETTER_DIG.sub(r"\1 \2", ascii_text)

    # 3. Strip packaging noise
    ascii_text = _PACKAGING_NOISE.sub(" ", ascii_text)

    # 4. Strip dosage form noise
    ascii_text = _FORM_NOISE.sub(" ", ascii_text)

    # 4.5. Strip salt/polymorph qualifiers for better INN matching
    ascii_text = _SALT_QUALIFIERS.sub(" ", ascii_text)

    # 5. Remove non-alphanumeric (keep spaces)
    ascii_text = re.sub(r"[^0-9a-z\s]", " ", ascii_text)

    # 5.5. Strip provider-specific suffix codes (COL, EOF, NI, PPS, etc.)
    ascii_text = _PROVIDER_SUFFIX_NOISE.sub(" ", ascii_text)

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
