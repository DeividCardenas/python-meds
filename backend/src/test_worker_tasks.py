import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.worker.tasks import (
    _cleanup_temp_file,
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

    def test_run_async_safely_ejecuta_corutina(self):
        async def _sample() -> str:
            return "ok"

        self.assertEqual(_run_async_safely(_sample()), "ok")


if __name__ == "__main__":
    unittest.main()
