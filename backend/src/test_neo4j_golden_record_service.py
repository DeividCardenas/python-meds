import unittest
import sys
from pathlib import Path

import polars as pl

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.services.neo4j_golden_record_service import Neo4jGoldenRecordService


class Neo4jGoldenRecordTransformTests(unittest.TestCase):
    def test_split_principios_combinados(self):
        df = pl.DataFrame(
            {
                "cum": ["123-01"],
                "producto": ["AMOXICILINA CLAVULANATO"],
                "estado_origen": ["Vigente"],
                "estadocum": ["Vigente"],
                "titular": ["LAB ABC"],
                "principio_activo_raw": ["AMOXICILINA + ACIDO CLAVULANICO"],
            }
        )

        out = Neo4jGoldenRecordService.transform_chunk_with_polars(df)
        rows = out.to_dicts()

        self.assertEqual(len(rows), 1)
        principios = set(rows[0]["principios"])
        self.assertEqual(principios, {"AMOXICILINA", "ACIDO CLAVULANICO"})
        self.assertTrue(rows[0]["activo"])

    def test_split_with_y_slash_con(self):
        df = pl.DataFrame(
            {
                "cum": ["123-02"],
                "producto": ["TEST"],
                "estado_origen": [None],
                "estadocum": ["Activo"],
                "titular": ["LAB DEF"],
                "principio_activo_raw": ["A Y B / C CON D"],
            }
        )

        out = Neo4jGoldenRecordService.transform_chunk_with_polars(df)
        principios = set(out.to_dicts()[0]["principios"])
        self.assertEqual(principios, {"A", "B", "C", "D"})

    def test_empty_principio_gives_empty_list(self):
        df = pl.DataFrame(
            {
                "cum": ["123-03"],
                "producto": ["TEST"],
                "estado_origen": ["Vencido"],
                "estadocum": ["Vencido"],
                "titular": [""],
                "principio_activo_raw": [None],
            }
        )

        out = Neo4jGoldenRecordService.transform_chunk_with_polars(df)
        row = out.to_dicts()[0]
        self.assertEqual(row["principios"], [])
        self.assertFalse(row["activo"])


if __name__ == "__main__":
    unittest.main()
