import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects import postgresql

from app.models.medicamento import MedicamentoCUM
from app.services.cum_socrata_service import (
    _map_record,
    _parse_datetime,
    _parse_float,
    _parse_int,
    construir_upsert_cum,
)


class MedicamentoCUMModelTests(unittest.TestCase):
    def test_primary_key_is_id_cum(self):
        pk_cols = [col.name for col in MedicamentoCUM.__table__.primary_key.columns]
        self.assertEqual(pk_cols, ["id_cum"])

    def test_required_fields_exist(self):
        cols = MedicamentoCUM.__table__.columns
        for field in (
            "id_cum",
            "expediente",
            "consecutivocum",
            "producto",
            "titular",
            "registrosanitario",
            "fechavencimiento",
            "cantidadcum",
            "descripcioncomercial",
            "estadocum",
            "atc",
            "descripcionatc",
            "principioactivo",
        ):
            self.assertIn(field, cols, f"Campo '{field}' no encontrado en la tabla medicamentos_cum")

    def test_estadocum_has_index(self):
        estadocum_col = MedicamentoCUM.__table__.columns["estadocum"]
        self.assertTrue(estadocum_col.index)

    def test_tablename(self):
        self.assertEqual(MedicamentoCUM.__tablename__, "medicamentos_cum")


class CumSocrataServiceTests(unittest.TestCase):
    def test_parse_int_valid(self):
        self.assertEqual(_parse_int("123456"), 123456)
        self.assertEqual(_parse_int(42), 42)

    def test_parse_int_invalid(self):
        self.assertIsNone(_parse_int(None))
        self.assertIsNone(_parse_int("abc"))

    def test_parse_float_valid(self):
        self.assertEqual(_parse_float("1.5"), 1.5)
        self.assertEqual(_parse_float(3), 3.0)

    def test_parse_float_invalid(self):
        self.assertIsNone(_parse_float(None))
        self.assertIsNone(_parse_float("no-float"))

    def test_parse_datetime_iso(self):
        result = _parse_datetime("2025-12-31T00:00:00.000")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2025)

    def test_parse_datetime_date_only(self):
        result = _parse_datetime("2025-06-15")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.month, 6)

    def test_parse_datetime_invalid(self):
        self.assertIsNone(_parse_datetime("not-a-date"))
        self.assertIsNone(_parse_datetime(None))

    def test_map_record_builds_id_cum(self):
        raw = {
            "expediente": "123456",
            "consecutivocum": "1",
            "producto": "PARACETAMOL TABLETAS",
            "titular": "LAB ABC",
            "registrosanitario": "INVIMA-2021M-001",
            "fechavencimiento": "2027-01-01T00:00:00.000",
            "cantidadcum": "100",
            "descripcioncomercial": "PARACETAMOL 500MG",
            "estadocum": "Vigente",
            "atc": "N02BE01",
            "descripcionatc": "Paracetamol",
            "principioactivo": "ACETAMINOFÉN",
        }
        mapped = _map_record(raw)

        # consecutivocum=1 → zero-padded to "01"
        self.assertEqual(mapped["id_cum"], "123456-01")
        self.assertEqual(mapped["expediente"], 123456)
        self.assertEqual(mapped["consecutivocum"], 1)
        self.assertEqual(mapped["estadocum"], "Vigente")
        self.assertIsInstance(mapped["fechavencimiento"], datetime)

    def test_map_record_no_padding_for_two_digits(self):
        raw = {"expediente": "123456", "consecutivocum": "10"}
        mapped = _map_record(raw)
        # consecutivocum=10 → no extra padding needed
        self.assertEqual(mapped["id_cum"], "123456-10")

    def test_map_record_missing_expediente_returns_empty(self):
        raw = {"consecutivocum": "1", "producto": "X"}
        self.assertEqual(_map_record(raw), {})

    def test_map_record_missing_consecutivo_returns_empty(self):
        raw = {"expediente": "999", "producto": "X"}
        self.assertEqual(_map_record(raw), {})

    def test_construir_upsert_cum_genera_on_conflict(self):
        row = {
            "id_cum": "123456-01",
            "expediente": 123456,
            "consecutivocum": 1,
            "producto": "PARACETAMOL",
            "titular": "LAB",
            "registrosanitario": "RS-001",
            "fechavencimiento": None,
            "cantidadcum": 100.0,
            "descripcioncomercial": "PAR 500MG",
            "estadocum": "Vigente",
            "atc": "N02BE01",
            "descripcionatc": "Paracetamol",
            "principioactivo": "ACETAMINOFÉN",
        }
        stmt = construir_upsert_cum([row])
        sql = str(stmt.compile(dialect=postgresql.dialect()))

        self.assertIn("ON CONFLICT (id_cum) DO UPDATE", sql)
        # Campos que deben actualizarse en caso de conflicto
        for field in ("estadocum", "principioactivo", "producto", "atc"):
            self.assertIn(field, sql)


class CeleryBeatConfigTests(unittest.TestCase):
    def test_beat_schedule_contains_cum_task(self):
        from celery.schedules import crontab

        from app.worker.tasks import celery_app

        schedule = celery_app.conf.beat_schedule
        self.assertIn("sincronizar-catalogos-cum-mensual", schedule)
        entry = schedule["sincronizar-catalogos-cum-mensual"]
        self.assertEqual(entry["task"], "task_sincronizar_cum")
        self.assertIsInstance(entry["schedule"], crontab)
        # Verify the crontab fields match the required schedule
        sched = entry["schedule"]
        self.assertIn(2, sched.hour)
        self.assertIn(0, sched.minute)
        self.assertIn(1, sched.day_of_month)

    def test_timezone_is_bogota(self):
        from app.worker.tasks import celery_app

        self.assertEqual(celery_app.conf.timezone, "America/Bogota")


if __name__ == "__main__":
    unittest.main()
