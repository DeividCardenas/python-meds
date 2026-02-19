import unittest

from sqlalchemy.dialects import postgresql

from app.models.medicamento import EMBEDDING_DIMENSION
from app.services.search import _construir_statement_hibrido, _preparar_texto_busqueda


class SearchServiceTests(unittest.TestCase):
    def test_preparar_texto_tolera_diferencias_de_formato(self):
        self.assertEqual(_preparar_texto_busqueda("DOLEX 500MG"), "dolex 500 mg")
        self.assertEqual(_preparar_texto_busqueda("Dolex 500 mg"), "dolex 500 mg")

    def test_preparar_texto_no_hace_equivalencias_de_unidades(self):
        self.assertNotEqual(_preparar_texto_busqueda("Dolex 1g"), _preparar_texto_busqueda("Dolex 1000mg"))

    def test_statement_hibrido_includes_fts_and_vector(self):
        statement, params = _construir_statement_hibrido(
            texto_preparado="dolex 500 mg",
            empresa=None,
            query_embedding=[0.0] * EMBEDDING_DIMENSION,
        )
        sql = str(statement.compile(dialect=postgresql.dialect()))

        self.assertIn("to_tsvector", sql)
        self.assertIn("plainto_tsquery", sql)
        self.assertIn("<=>", sql)
        self.assertIn("forma_farmaceutica", sql)
        self.assertIn("registro_invima", sql)
        self.assertIn("principio_activo", sql)
        self.assertIn("query_embedding", params)


if __name__ == "__main__":
    unittest.main()
