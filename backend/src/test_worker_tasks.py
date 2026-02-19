import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.worker.tasks import (
    _cleanup_temp_file,
    _construir_upsert_costos,
    _es_nombre_valido,
    _normalize_bool,
    _normalize_decimal,
    _run_async_safely,
)


class WorkerTasksTests(unittest.TestCase):
    def test_normalize_decimal_soporta_formatos_comunes(self):
        self.assertEqual(_normalize_decimal("1.234,56"), 1234.56)
        self.assertEqual(_normalize_decimal("1,234.56"), 1234.56)
        self.assertEqual(_normalize_decimal("15"), 15.0)
        self.assertIsNone(_normalize_decimal("invalido"))

    def test_quality_gate_nombre_invalido(self):
        self.assertFalse(_es_nombre_valido("AB"))
        self.assertFalse(_es_nombre_valido("INSUMO"))
        self.assertTrue(_es_nombre_valido("Paracetamol"))

    def test_cleanup_temp_file_elimina_tsv(self):
        with NamedTemporaryFile(suffix=".tsv", delete=False) as handle:
            path = Path(handle.name)
        _cleanup_temp_file(str(path))
        self.assertFalse(path.exists())

    def test_normalize_bool_from_si_no(self):
        self.assertTrue(_normalize_bool("SI"))
        self.assertTrue(_normalize_bool("sí"))
        self.assertFalse(_normalize_bool("NO"))
        self.assertFalse(_normalize_bool(None))

    def test_construir_upsert_costos_actualiza_solo_campos_de_precios(self):
        statement = _construir_upsert_costos(
            [
                {
                    "id": uuid4(),
                    "id_cum": "123-1",
                    "nombre_limpio": "Medicamento X",
                    "precio_unitario": 12.5,
                    "precio_empaque": 100.0,
                    "es_regulado": True,
                    "precio_maximo_regulado": 130.0,
                }
            ]
        )
        sql = str(statement.compile(dialect=postgresql.dialect()))

        self.assertIn("ON CONFLICT (id_cum) DO UPDATE", sql)
        self.assertIn("precio_unitario = excluded.precio_unitario", sql)
        self.assertIn("precio_empaque = excluded.precio_empaque", sql)
        self.assertIn("es_regulado = excluded.es_regulado", sql)
        self.assertIn("precio_maximo_regulado = excluded.precio_maximo_regulado", sql)

    def test_run_async_safely_ejecuta_corutina(self):
        async def _sample() -> str:
            return "ok"

        self.assertEqual(_run_async_safely(_sample()), "ok")


if __name__ == "__main__":
    unittest.main()
