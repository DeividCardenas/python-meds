import unittest

from app.worker.tasks import _es_nombre_valido, _normalize_decimal


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


if __name__ == "__main__":
    unittest.main()
