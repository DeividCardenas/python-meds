"""Tests for the supplier auto-identification engine.

Covers Pillar 2: filename pattern matching and header fingerprinting that
maps supplier files to their canonical ``proveedor_codigo``.
"""
import unittest

from app.services.supplier_detector import SupplierDetectionResult, detectar_proveedor


class DetectarProveedorFilenameTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Filename pattern matching
    # ------------------------------------------------------------------
    def test_tecnoquimicas_filename(self):
        result = detectar_proveedor("TECNOQUIMICAS 18 NOV 2025.xlsx")
        self.assertEqual(result.proveedor_codigo, "TECNOQUIMICAS")
        self.assertEqual(result.method, "filename")
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_tecnoquimicas_lowercase(self):
        result = detectar_proveedor("tecnoquimicas nov 2025.xlsx")
        self.assertEqual(result.proveedor_codigo, "TECNOQUIMICAS")

    def test_la_sante_filename(self):
        result = detectar_proveedor("LA SANTE PRECIOS 2025.xlsx")
        self.assertEqual(result.proveedor_codigo, "LA_SANTE")

    def test_fresenius_filename(self):
        result = detectar_proveedor("Fresenius_Lista_Precios.xlsx")
        self.assertEqual(result.proveedor_codigo, "FRESENIUS")

    def test_megalabs_filename(self):
        result = detectar_proveedor("MEGALABS_PRECIOS_Q4_2025.xlsx")
        self.assertEqual(result.proveedor_codigo, "MEGALABS")

    def test_bayer_filename(self):
        result = detectar_proveedor("Bayer Colombia precios.xlsx")
        self.assertEqual(result.proveedor_codigo, "BAYER")

    def test_filename_with_path_prefix_stripped(self):
        result = detectar_proveedor("/uploads/user/TECNOQUIMICAS 2025.xlsx")
        self.assertEqual(result.proveedor_codigo, "TECNOQUIMICAS")

    def test_windows_path_separator_handled(self):
        result = detectar_proveedor("C:\\uploads\\FRESENIUS_2025.xlsx")
        self.assertEqual(result.proveedor_codigo, "FRESENIUS")

    # ------------------------------------------------------------------
    # Header fingerprint matching (fallback when filename unknown)
    # ------------------------------------------------------------------
    def test_megalabs_header_fingerprint(self):
        result = detectar_proveedor(
            "lista_precios_enero.xlsx",
            columnas=["Codigo Axapta", "Descripcion", "Precio UMD", "Laboratorio"],
        )
        self.assertEqual(result.proveedor_codigo, "MEGALABS")
        self.assertEqual(result.method, "header")
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_fresenius_header_fingerprint(self):
        result = detectar_proveedor(
            "archivo_desconocido.xlsx",
            columnas=["CUM", "Vigente Desde", "Vigente Hasta", "Precio"],
        )
        self.assertEqual(result.proveedor_codigo, "FRESENIUS")
        self.assertEqual(result.method, "header")

    def test_la_sante_header_fingerprint(self):
        result = detectar_proveedor(
            "precios.xlsx",
            columnas=["CUM", "Descripcion", "Precio", "Laboratorio"],
        )
        self.assertEqual(result.proveedor_codigo, "LA_SANTE")

    # ------------------------------------------------------------------
    # Unknown supplier
    # ------------------------------------------------------------------
    def test_unknown_filename_returns_none(self):
        result = detectar_proveedor("lista_precios.xlsx")
        self.assertIsNone(result.proveedor_codigo)
        self.assertEqual(result.method, "unknown")
        self.assertEqual(result.confidence, 0.0)

    def test_unknown_with_unrecognised_columns(self):
        result = detectar_proveedor(
            "archivo.xlsx",
            columnas=["Col A", "Col B", "Col C"],
        )
        self.assertIsNone(result.proveedor_codigo)
        self.assertEqual(result.method, "unknown")

    def test_no_columns_provided_falls_through_to_unknown(self):
        result = detectar_proveedor("archivo.xlsx")
        self.assertIsNone(result.proveedor_codigo)

    # ------------------------------------------------------------------
    # Result type
    # ------------------------------------------------------------------
    def test_returns_supplier_detection_result(self):
        result = detectar_proveedor("BAYER_2025.xlsx")
        self.assertIsInstance(result, SupplierDetectionResult)

    def test_filename_takes_priority_over_header(self):
        """Filename match should win even when columns would match a different supplier."""
        result = detectar_proveedor(
            "FRESENIUS_2025.xlsx",
            columnas=["Codigo Axapta", "Descripcion", "Precio UMD"],
        )
        # FRESENIUS should win from filename, not MEGALABS from headers
        self.assertEqual(result.proveedor_codigo, "FRESENIUS")
        self.assertEqual(result.method, "filename")


if __name__ == "__main__":
    unittest.main()
