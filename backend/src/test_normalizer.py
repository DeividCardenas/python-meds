"""Tests for the Polars-powered pharmaceutical text normalizer.

Covers Pillar 1: advanced normalization pipeline used before fuzzy CUM
matching against the Golden Source database.
"""
import unittest

import polars as pl

from app.services.normalizer import (
    normalize_dataframe_column,
    normalize_pharma_text,
    normalize_series,
)


class NormalizePharmaTextTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Basic transformations
    # ------------------------------------------------------------------
    def test_lowercase_and_accent_strip(self):
        self.assertEqual(normalize_pharma_text("AMOXICILINA"), "amoxicilina")

    def test_accent_stripped(self):
        result = normalize_pharma_text("PENICILÍNA 500MG")
        self.assertNotIn("í", result)
        self.assertIn("penicilina", result)

    def test_digit_letter_boundary_inserted(self):
        result = normalize_pharma_text("500MG")
        self.assertEqual(result, "500 mg")

    def test_letter_digit_boundary_inserted(self):
        result = normalize_pharma_text("IBUPROFENO400MG")
        self.assertIn("ibuprofeno", result)
        self.assertIn("400", result)
        self.assertIn("mg", result)

    # ------------------------------------------------------------------
    # Packaging noise removal
    # ------------------------------------------------------------------
    def test_removes_caja_x_noise(self):
        result = normalize_pharma_text("AMOXICILINA 500MG CAJA X 30")
        self.assertNotIn("caja", result)
        self.assertNotIn("30", result)

    def test_removes_blister_noise(self):
        result = normalize_pharma_text("PARACETAMOL 500 MG BLISTER X 10")
        self.assertNotIn("blister", result)
        self.assertIn("paracetamol", result)

    def test_removes_frasco_noise(self):
        result = normalize_pharma_text("METFORMINA 850 MG FRASCO X 60")
        self.assertNotIn("frasco", result)

    # ------------------------------------------------------------------
    # Canonical form equivalence
    # ------------------------------------------------------------------
    def test_canonical_equivalence_amoxicilina(self):
        """Two messy variants should produce the same core token."""
        a = normalize_pharma_text("AMOXICILINA 500MG CAP")
        b = normalize_pharma_text("AMOXICILINA 500 MG CAPSULA")
        # Both should contain the active ingredient and dose tokens
        self.assertIn("amoxicilina", a)
        self.assertIn("amoxicilina", b)
        self.assertIn("500", a)
        self.assertIn("500", b)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------
    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_pharma_text(""), "")

    def test_none_like_whitespace_returns_empty(self):
        self.assertEqual(normalize_pharma_text("   "), "")

    def test_non_alphanumeric_removed(self):
        result = normalize_pharma_text("ASPIRINA® 100 mg (Bayer)")
        self.assertNotIn("®", result)
        self.assertNotIn("(", result)
        self.assertNotIn(")", result)

    def test_multiple_spaces_collapsed(self):
        result = normalize_pharma_text("IBUPROFENO   200   MG")
        self.assertNotIn("  ", result)

    def test_dosage_form_noise_removed(self):
        result = normalize_pharma_text("DICLOFENAC 75 MG INYECTABLE")
        self.assertNotIn("inyectable", result)

    # ------------------------------------------------------------------
    # Polars Series vectorization
    # ------------------------------------------------------------------
    def test_normalize_series_returns_correct_types(self):
        series = pl.Series(["AMOXICILINA 500MG", "PARACETAMOL 1G", None])
        result = normalize_series(series)
        self.assertIsInstance(result, pl.Series)
        self.assertEqual(result.dtype, pl.Utf8)
        self.assertEqual(result[2], "")  # None → ""

    def test_normalize_series_applies_normalization(self):
        series = pl.Series(["ASPIRINA 100MG CAJA X 20"])
        result = normalize_series(series)
        self.assertIn("aspirina", result[0])
        self.assertNotIn("caja", result[0])

    # ------------------------------------------------------------------
    # DataFrame column helper
    # ------------------------------------------------------------------
    def test_normalize_dataframe_column_adds_normalized_col(self):
        df = pl.DataFrame({"descripcion": ["AMOXICILINA 500MG CAP", "PARACETAMOL 500 MG"]})
        result_df = normalize_dataframe_column(df, "descripcion")
        self.assertIn("descripcion_normalized", result_df.columns)
        self.assertEqual(result_df.shape[0], 2)

    def test_normalize_dataframe_column_values_are_normalized(self):
        df = pl.DataFrame({"descripcion": ["IBUPROFENO 400MG BLISTER X 15"]})
        result_df = normalize_dataframe_column(df, "descripcion")
        normalized_val = result_df["descripcion_normalized"][0]
        self.assertIn("ibuprofeno", normalized_val)
        self.assertNotIn("blister", normalized_val)


if __name__ == "__main__":
    unittest.main()
