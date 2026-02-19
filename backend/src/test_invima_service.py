import os
import tempfile
import unittest
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.services.invima_service import MERGE_TMP_INVIMA_SQL, construir_upsert_invima, leer_maestro_invima


class InvimaServiceTests(unittest.TestCase):
    def test_lee_tsv_filtra_vigentes_activos_y_mapea_columnas(self):
        content = (
            "EXPEDIENTE\tCONSECUTIVO\tATC\tREGISTRO INVIMA\tNOMBRE COMERCIAL\tPRINCIPIO ACTIVO\t"
            "PRESENTACION COMERCIAL\tLABORATORIO TITULAR\tESTADO REGISTRO\tESTADO CUM\n"
            "123\t1\tA01\tINV-1\tDÓLEX®\tÁCIDO ACETILSALICÍLICO™\tTABLETAS\tLAB UNO\tVigente\tActivo\n"
            "123\t1\tSIN DATO\tINV-1B\tSIN DATO\tCAFÉINA\tTABLETAS\tSIN DATO\tVIGENTE\tACTIVO\n"
            "999\t2\tB02\tINV-2\tX\tY\tZ\tLAB DOS\tVencido\tActivo\n"
            "555\t9\tC03\tINV-3\tX\tY\tZ\tLAB TRES\tNo Vigente\tActivo\n"
            "777\t8\tD04\tINV-4\tX\tY\tZ\tLAB CUATRO\tVigente\tInactivo\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as handle:
            handle.write(content)
            path = handle.name

        try:
            dataframe = leer_maestro_invima(path)
            rows = dataframe.to_dicts()
        finally:
            os.unlink(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id_cum"], "123-1")
        self.assertEqual(rows[0]["atc"], "")
        self.assertEqual(rows[0]["registro_invima"], "INV-1B")
        self.assertEqual(rows[0]["nombre_limpio"], "cafeina")
        self.assertEqual(rows[0]["laboratorio"], "")
        self.assertEqual(rows[0]["estado_regulatorio"], "VIGENTE / ACTIVO")

    def test_upsert_actualiza_solo_campos_regulatorios(self):
        statement = construir_upsert_invima(
            [
                {
                    "id": uuid4(),
                    "id_cum": "123-1",
                    "atc": "A01",
                    "registro_invima": "INV-1",
                    "estado_regulatorio": "Vigente / Activo",
                    "nombre_limpio": "DOLEX ACETAMINOFEN TABLETAS",
                    "laboratorio": "LAB UNO",
                    "embedding_status": "PENDING",
                }
            ]
        )
        sql = str(statement.compile(dialect=postgresql.dialect()))

        self.assertIn("ON CONFLICT (id_cum) DO UPDATE", sql)
        self.assertIn("atc = excluded.atc", sql)
        self.assertIn("registro_invima = excluded.registro_invima", sql)
        self.assertIn("estado_regulatorio = excluded.estado_regulatorio", sql)
        self.assertIn("nombre_limpio = excluded.nombre_limpio", sql)
        self.assertIn("laboratorio = excluded.laboratorio", sql)
        self.assertNotIn("embedding_status = excluded.embedding_status", sql)

    def test_merge_tmp_invima_actualiza_solo_campos_permitidos(self):
        sql = " ".join(MERGE_TMP_INVIMA_SQL.split())

        self.assertIn("ON CONFLICT (id_cum) DO UPDATE SET", sql)
        self.assertIn("atc = EXCLUDED.atc", sql)
        self.assertIn("registro_invima = EXCLUDED.registro_invima", sql)
        self.assertIn("estado_regulatorio = EXCLUDED.estado_regulatorio", sql)
        self.assertIn("nombre_limpio = EXCLUDED.nombre_limpio", sql)
        self.assertIn("laboratorio = EXCLUDED.laboratorio", sql)
        self.assertNotIn("embedding_status = EXCLUDED.embedding_status", sql)
        self.assertNotIn("embedding = EXCLUDED.embedding", sql)


if __name__ == "__main__":
    unittest.main()
