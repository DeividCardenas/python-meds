import unittest
from datetime import date
import sys
from pathlib import Path

import polars as pl

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.services.neo4j_proveedor_ingesta_service import Neo4jProveedorIngestaService


class Neo4jProveedorIngestaTransformTests(unittest.TestCase):
    def test_transform_dataframe_basic(self):
        df = pl.DataFrame(
            {
                "cum": ["123-01", "999-99"],
                "precio": ["12.500,25", "15000"],
                "porcentaje_aumento": ["5", None],
                "descripcion": ["AMOXI", "TEST"],
                "moneda": ["COP", None],
            }
        )

        out = Neo4jProveedorIngestaService.transform_proveedor_dataframe(
            df,
            id_documento="DOC-1",
            proveedor="DISFARMA",
            fecha_documento=date(2026, 3, 23),
            column_map={
                "cum": "cum",
                "precio_proveedor": "precio",
                "porcentaje_aumento": "porcentaje_aumento",
                "texto_original": "descripcion",
                "moneda": "moneda",
            },
        )

        rows = out.to_dicts()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id_documento"], "DOC-1")
        self.assertEqual(rows[0]["proveedor"], "DISFARMA")
        self.assertEqual(rows[0]["cum"], "123-01")
        self.assertAlmostEqual(rows[0]["precio_proveedor"], 12500.25, places=2)

    def test_split_matched_vs_orphan(self):
        rows = [
            {"cum": "123-01", "id_documento": "A", "proveedor": "X", "fecha": "2026-03-23", "texto_original": "ok", "precio_proveedor": 1.0, "porcentaje_aumento": 0.0, "moneda": "COP"},
            {"cum": "", "id_documento": "A", "proveedor": "X", "fecha": "2026-03-23", "texto_original": "sin cum", "precio_proveedor": 2.0, "porcentaje_aumento": None, "moneda": "COP"},
            {"cum": "999-99", "id_documento": "A", "proveedor": "X", "fecha": "2026-03-23", "texto_original": "no existe", "precio_proveedor": 3.0, "porcentaje_aumento": None, "moneda": "COP"},
        ]

        matched, orphan = Neo4jProveedorIngestaService.split_matched_vs_orphan(rows, {"123-01"})
        self.assertEqual(len(matched), 1)
        self.assertEqual(len(orphan), 2)
        self.assertEqual(orphan[0]["cum_recibido"], "")


if __name__ == "__main__":
    unittest.main()
