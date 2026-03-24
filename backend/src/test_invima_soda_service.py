import unittest
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from app.models.medicamento import MedicamentoCUM
from app.services.invima_soda_service import (
    _deduplicate_rows,
    _map_record,
    _resolve_fecha_corte_dato,
    build_dataframe_invima_soda,
    construir_upsert_invima_soda,
)


class InvimaSodaModelFieldsTests(unittest.TestCase):
    def test_medicamentos_cum_has_estado_origen_and_fecha_corte(self):
        cols = MedicamentoCUM.__table__.columns
        self.assertIn("estado_origen", cols)
        self.assertIn("fecha_corte_dato", cols)


class InvimaSodaMappingTests(unittest.TestCase):
    def test_map_record_adds_estado_origen(self):
        raw = {
            "expediente": "123456",
            "consecutivocum": "1",
            "producto": "PARACETAMOL",
            "descripcioncomercial": "PARACETAMOL 500MG",
        }
        fecha_corte = datetime(2026, 3, 16, tzinfo=timezone.utc)

        mapped = _map_record(raw, "vigentes", fecha_corte)

        self.assertEqual(mapped["id_cum"], "123456-01")
        self.assertEqual(mapped["estado_origen"], "vigentes")
        self.assertEqual(mapped["fecha_corte_dato"], fecha_corte)
        self.assertEqual(mapped["estadocum"], "Vigente")

    def test_map_record_invalid_returns_empty(self):
        raw = {"producto": "X"}
        fecha_corte = datetime(2026, 3, 16, tzinfo=timezone.utc)
        self.assertEqual(_map_record(raw, "otros", fecha_corte), {})

    def test_deduplicate_merges_estado_origen(self):
        fecha_a = datetime(2026, 3, 16, tzinfo=timezone.utc)
        fecha_b = datetime(2026, 3, 20, tzinfo=timezone.utc)
        rows = [
            {
                "id_cum": "123-01",
                "estado_origen": "vigentes",
                "fecha_corte_dato": fecha_a,
                "producto": "A",
            },
            {
                "id_cum": "123-01",
                "estado_origen": "vencidos",
                "fecha_corte_dato": fecha_b,
                "producto": "B",
            },
        ]

        dedup = _deduplicate_rows(rows)
        self.assertEqual(len(dedup), 1)
        self.assertEqual(dedup[0]["id_cum"], "123-01")
        self.assertIn("vigentes", dedup[0]["estado_origen"])
        self.assertIn("vencidos", dedup[0]["estado_origen"])

    def test_resolve_fecha_corte_first_run_uses_initial(self):
        execution_dt = datetime(2026, 3, 23, tzinfo=timezone.utc)
        resolved = _resolve_fecha_corte_dato(False, execution_dt)
        self.assertEqual(resolved.date().isoformat(), "2026-03-16")


class InvimaSodaOutputTests(unittest.TestCase):
    def test_build_dataframe_returns_columns_on_empty(self):
        df = build_dataframe_invima_soda([])
        self.assertEqual(len(df), 0)
        self.assertIn("estado_origen", df.columns)

    def test_construir_upsert_contains_on_conflict(self):
        row = {
            "id_cum": "123456-01",
            "expediente": 123456,
            "consecutivocum": 1,
            "producto": "PARACETAMOL",
            "estado_origen": "vigentes",
            "fecha_corte_dato": datetime(2026, 3, 16, tzinfo=timezone.utc),
        }
        stmt = construir_upsert_invima_soda([row])
        sql = str(stmt.compile(dialect=postgresql.dialect()))

        self.assertIn("ON CONFLICT (id_cum) DO UPDATE", sql)
        self.assertIn("estado_origen", sql)
        self.assertIn("fecha_corte_dato", sql)


if __name__ == "__main__":
    unittest.main()
