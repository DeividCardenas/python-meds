import unittest

import pandas as pd

from vectorizar_catalogo import validar_fila


class ValidarFilaTests(unittest.TestCase):
    def test_rechaza_precio_cero_o_nulo(self):
        es_valida, motivo, warning_fu = validar_fila(
            pd.Series({"_nombre_validacion": "Paracetamol", "_precio_validacion": 0, "_fu_validacion": 10})
        )
        self.assertFalse(es_valida)
        self.assertIn("Precio Cero o Nulo", motivo)
        self.assertFalse(warning_fu)

        es_valida, motivo, warning_fu = validar_fila(
            pd.Series({"_nombre_validacion": "Paracetamol", "_precio_validacion": None, "_fu_validacion": 10})
        )
        self.assertFalse(es_valida)
        self.assertIn("Precio Cero o Nulo", motivo)
        self.assertFalse(warning_fu)

    def test_rechaza_nombre_generico_o_corto(self):
        es_valida, motivo, _ = validar_fila(
            pd.Series({"_nombre_validacion": "INSUMO", "_precio_validacion": 20, "_fu_validacion": 10})
        )
        self.assertFalse(es_valida)
        self.assertIn("Nombre Inválido", motivo)

        es_valida, motivo, _ = validar_fila(
            pd.Series({"_nombre_validacion": "AB", "_precio_validacion": 20, "_fu_validacion": 10})
        )
        self.assertFalse(es_valida)
        self.assertIn("Nombre Inválido", motivo)

        es_valida, motivo, _ = validar_fila(
            pd.Series({"_nombre_validacion": "PENDIENTE-123", "_precio_validacion": 20, "_fu_validacion": 10})
        )
        self.assertFalse(es_valida)
        self.assertIn("Nombre Inválido", motivo)

    def test_marca_warning_fu_pero_permite(self):
        es_valida, motivo, warning_fu = validar_fila(
            pd.Series({"_nombre_validacion": "Ibuprofeno", "_precio_validacion": 20, "_fu_validacion": 51})
        )
        self.assertTrue(es_valida)
        self.assertEqual("", motivo)
        self.assertTrue(warning_fu)

        es_valida, _, warning_fu = validar_fila(
            pd.Series({"_nombre_validacion": "Ibuprofeno", "_precio_validacion": 20, "_fu_validacion": 50})
        )
        self.assertTrue(es_valida)
        self.assertFalse(warning_fu)

        es_valida, _, warning_fu = validar_fila(
            pd.Series({"_nombre_validacion": "Ibuprofeno", "_precio_validacion": 20, "_fu_validacion": None})
        )
        self.assertTrue(es_valida)
        self.assertFalse(warning_fu)


if __name__ == "__main__":
    unittest.main()
