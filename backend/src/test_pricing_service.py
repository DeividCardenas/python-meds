import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import polars as pl

from app.services.pricing_service import (
    _parse_date,
    _parse_decimal,
    _parse_percentage,
    detectar_columnas,
    sugerir_mapeo_automatico,
)


class PricingServiceTests(unittest.TestCase):
    # -----------------------------------------------------------------------
    # _parse_decimal
    # -----------------------------------------------------------------------
    def test_parse_decimal_entero(self):
        self.assertEqual(_parse_decimal("12000"), Decimal("12000"))

    def test_parse_decimal_europeo_con_punto_y_coma(self):
        self.assertEqual(_parse_decimal("1.234,56"), Decimal("1234.56"))

    def test_parse_decimal_us_con_coma_y_punto(self):
        self.assertEqual(_parse_decimal("1,234.56"), Decimal("1234.56"))

    def test_parse_decimal_coma_decimal(self):
        self.assertEqual(_parse_decimal("1234,56"), Decimal("1234.56"))

    def test_parse_decimal_ninguno_devuelve_none(self):
        self.assertIsNone(_parse_decimal(None))

    def test_parse_decimal_invalido_devuelve_none(self):
        self.assertIsNone(_parse_decimal("N/A"))

    def test_parse_decimal_float_nativo(self):
        self.assertEqual(_parse_decimal(9500.75), Decimal("9500.75"))

    # -----------------------------------------------------------------------
    # _parse_date
    # -----------------------------------------------------------------------
    def test_parse_date_iso(self):
        from datetime import date

        self.assertEqual(_parse_date("2025-12-31"), date(2025, 12, 31))

    def test_parse_date_latin_slash(self):
        from datetime import date

        self.assertEqual(_parse_date("31/12/2025"), date(2025, 12, 31))

    def test_parse_date_invalido_devuelve_none(self):
        self.assertIsNone(_parse_date("no es fecha"))

    def test_parse_date_none_devuelve_none(self):
        self.assertIsNone(_parse_date(None))

    # -----------------------------------------------------------------------
    # detectar_columnas
    # -----------------------------------------------------------------------
    def test_detectar_columnas_csv(self):
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("Código Axapta,Descripción,Precio UMD\n")
            f.write("AX-001,Paracetamol 500mg,1500\n")
            tmp_path = f.name
        try:
            cols = detectar_columnas(tmp_path)
            self.assertEqual(cols, ["Código Axapta", "Descripción", "Precio UMD"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_detectar_columnas_xlsx(self):
        with NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp_path = f.name
        try:
            df = pl.DataFrame({"CUM": ["123-01"], "Producto": ["Test"], "Precio": [2000]})
            df.write_excel(tmp_path)
            cols = detectar_columnas(tmp_path)
            self.assertEqual(cols, ["CUM", "Producto", "Precio"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # -----------------------------------------------------------------------
    # sugerir_mapeo_automatico
    # -----------------------------------------------------------------------
    def test_sugerencia_cum_detecta_columna_cum(self):
        mapping = sugerir_mapeo_automatico(["Código CUM", "Precio", "Descripción"])
        self.assertEqual(mapping.get("cum_code"), "Código CUM")

    def test_sugerencia_precio_detecta_precio_umd(self):
        mapping = sugerir_mapeo_automatico(["Código Axapta", "Precio UMD", "Descripción"])
        self.assertEqual(mapping.get("precio_unitario"), "Precio UMD")

    def test_sugerencia_descripcion(self):
        mapping = sugerir_mapeo_automatico(["Nombre Producto", "Precio", "CUM"])
        self.assertIn(mapping.get("descripcion"), ["Nombre Producto"])

    def test_sugerencia_fechas(self):
        mapping = sugerir_mapeo_automatico(
            ["Vigente Desde", "Vigente Hasta", "CUM Code", "Precio Unitario"]
        )
        self.assertEqual(mapping.get("vigente_desde"), "Vigente Desde")
        self.assertEqual(mapping.get("vigente_hasta"), "Vigente Hasta")

    def test_sugerencia_columnas_vacias(self):
        mapping = sugerir_mapeo_automatico([])
        self.assertEqual(mapping, {})

    def test_sugerencia_sin_coincidencias(self):
        mapping = sugerir_mapeo_automatico(["Columna1", "Columna2"])
        self.assertEqual(mapping, {})

    # -----------------------------------------------------------------------
    # _parse_percentage
    # -----------------------------------------------------------------------
    def test_parse_percentage_percent_string(self):
        self.assertEqual(_parse_percentage("19%"), Decimal("0.1900"))

    def test_parse_percentage_float_string(self):
        self.assertEqual(_parse_percentage("0.19"), Decimal("0.1900"))

    def test_parse_percentage_integer_string(self):
        self.assertEqual(_parse_percentage("19"), Decimal("0.1900"))

    def test_parse_percentage_zero(self):
        self.assertEqual(_parse_percentage("0%"), Decimal("0.0000"))

    def test_parse_percentage_none_returns_none(self):
        self.assertIsNone(_parse_percentage(None))

    def test_parse_percentage_invalid_returns_none(self):
        self.assertIsNone(_parse_percentage("N/A"))

    # -----------------------------------------------------------------------
    # sugerir_mapeo_automatico – new financial columns
    # -----------------------------------------------------------------------
    def test_sugerencia_precio_unidad_minima(self):
        mapping = sugerir_mapeo_automatico(["CUM", "NOMBRE", "PRECIO UNIDAD MINIMA"])
        self.assertEqual(mapping.get("precio_unidad"), "PRECIO UNIDAD MINIMA")

    def test_sugerencia_precio_presentacion(self):
        mapping = sugerir_mapeo_automatico(["CUM", "Precio Presentacion", "Precio UMD"])
        self.assertEqual(mapping.get("precio_presentacion"), "Precio Presentacion")

    def test_sugerencia_porcentaje_iva(self):
        mapping = sugerir_mapeo_automatico(["CUM", "Descripcion", "Precio", "IVA"])
        self.assertEqual(mapping.get("porcentaje_iva"), "IVA")


if __name__ == "__main__":
    unittest.main()
