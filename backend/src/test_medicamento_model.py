import unittest

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.models.medicamento import Medicamento


class MedicamentoModelTests(unittest.TestCase):
    def test_nombre_limpio_trgm_gin_index_is_configured(self):
        index = next((idx for idx in Medicamento.__table__.indexes if idx.name == "ix_medicamentos_nombre_gin"), None)

        self.assertIsNotNone(index)

        sql = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        self.assertIn("USING gin", sql)
        self.assertIn("nombre_limpio gin_trgm_ops", sql)

    def test_costos_y_regulacion_fields_exist(self):
        columns = Medicamento.__table__.columns
        self.assertIn("precio_unitario", columns)
        self.assertIn("precio_empaque", columns)
        self.assertIn("es_regulado", columns)
        self.assertIn("precio_maximo_regulado", columns)


if __name__ == "__main__":
    unittest.main()
