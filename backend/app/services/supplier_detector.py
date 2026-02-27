"""Supplier auto-identification engine.

Detects the laboratory/supplier from:
  1. Filename pattern matching  – e.g. "TECNOQUIMICAS 18 NOV 2025.xlsx"
     maps to supplier code "TECNOQUIMICAS".
  2. Header fingerprinting – unique column-name combinations characteristic
     of a specific supplier's spreadsheet format.

The detection result includes a ``confidence`` score:
  * ``0.95`` for filename matches (nearly certain)
  * ``0.90`` for header-fingerprint matches
  * ``0.0``  when no pattern matches

The detected ``proveedor_codigo`` is the canonical supplier identifier used
in the ``proveedores.codigo`` column of the database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SupplierDetectionResult:
    """Result returned by :func:`detectar_proveedor`."""

    proveedor_codigo: str | None
    """Canonical supplier code, or ``None`` when undetected."""

    confidence: float
    """Detection confidence in the range ``[0.0, 1.0]``."""

    method: str
    """One of ``"filename"``, ``"header"``, or ``"unknown"``."""


# ---------------------------------------------------------------------------
# Filename patterns → supplier code
# Patterns are matched case-insensitively against the file *stem*
# (filename without its extension).
# ---------------------------------------------------------------------------
_FILENAME_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"tecno\s*quimicas?", re.IGNORECASE), "TECNOQUIMICAS"),
    (re.compile(r"la\s*sante?", re.IGNORECASE), "LA_SANTE"),
    (re.compile(r"fresenius", re.IGNORECASE), "FRESENIUS"),
    (re.compile(r"megalabs?", re.IGNORECASE), "MEGALABS"),
    (re.compile(r"procaps?", re.IGNORECASE), "PROCAPS"),
    (re.compile(r"bayer", re.IGNORECASE), "BAYER"),
    (re.compile(r"pfizer", re.IGNORECASE), "PFIZER"),
    (re.compile(r"novartis", re.IGNORECASE), "NOVARTIS"),
    (re.compile(r"genfar", re.IGNORECASE), "GENFAR"),
    (re.compile(r"lafrancol", re.IGNORECASE), "LAFRANCOL"),
    (re.compile(r"\bmk\b", re.IGNORECASE), "MK"),
    (re.compile(r"coaspharma|coas\s*pharma", re.IGNORECASE), "COASPHARMA"),
    (re.compile(r"roche", re.IGNORECASE), "ROCHE"),
    (re.compile(r"sanofi", re.IGNORECASE), "SANOFI"),
    (re.compile(r"merck", re.IGNORECASE), "MERCK"),
]

# ---------------------------------------------------------------------------
# Header fingerprints → supplier code
# A fingerprint matches when ALL its column names (lowercased and stripped)
# are a subset of the file's actual column set.
# ---------------------------------------------------------------------------
_HEADER_FINGERPRINTS: list[tuple[frozenset[str], str]] = [
    (frozenset({"codigo axapta", "descripcion", "precio umd"}), "MEGALABS"),
    (frozenset({"cum", "vigente desde", "vigente hasta", "precio"}), "FRESENIUS"),
    (frozenset({"cum", "descripcion", "precio"}), "LA_SANTE"),
    (frozenset({"codigo cum", "producto", "precio unitario"}), "TECNOQUIMICAS"),
    (frozenset({"reg. invima", "descripcion", "precio"}), "PROCAPS"),
]


def detectar_proveedor(
    filename: str,
    columnas: list[str] | None = None,
) -> SupplierDetectionResult:
    """
    Auto-detect the supplier code from a *filename* and optional *columnas*.

    Detection order:
      1. Filename pattern match (confidence 0.95)
      2. Header fingerprint match (confidence 0.90)
      3. Unknown (confidence 0.0)

    Parameters
    ----------
    filename:
        Original filename including extension (e.g.
        ``"TECNOQUIMICAS 18 NOV 2025.xlsx"``).
    columnas:
        Optional list of raw column headers detected from the file.

    Returns
    -------
    SupplierDetectionResult
    """
    # Strip path separators and extension to get the bare stem
    stem = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = re.sub(r"\.[^.]+$", "", stem)

    # 1 – Filename pattern match
    for pattern, codigo in _FILENAME_PATTERNS:
        if pattern.search(stem):
            return SupplierDetectionResult(
                proveedor_codigo=codigo,
                confidence=0.95,
                method="filename",
            )

    # 2 – Header fingerprint match
    if columnas:
        cols_lower = frozenset(c.lower().strip() for c in columnas)
        for fingerprint, codigo in _HEADER_FINGERPRINTS:
            if fingerprint.issubset(cols_lower):
                return SupplierDetectionResult(
                    proveedor_codigo=codigo,
                    confidence=0.90,
                    method="header",
                )

    return SupplierDetectionResult(
        proveedor_codigo=None,
        confidence=0.0,
        method="unknown",
    )
