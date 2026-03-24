import unittest
from datetime import date
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.services.auditoria_metricas_service import AuditoriaMetricasService


class AuditoriaMetricasServiceTests(unittest.TestCase):
    def test_dashboard_kpis_structure(self):
        class FakeService(AuditoriaMetricasService):
            def __post_init__(self):
                self._driver = None

            def close(self):
                return None

            def calidad_proveedor(self, fecha_desde: date, fecha_hasta: date):
                _ = (fecha_desde, fecha_hasta)
                return [{"proveedor": "DISFARMA", "porcentaje_huerfanos": 15.0}]

            def top_riesgos_huerfanos(self, fecha_desde: date, fecha_hasta: date):
                _ = (fecha_desde, fecha_hasta)
                return [{"cum_recibido": "999-99", "frecuencia": 12}]

            def volumen_revision_pendiente(self):
                return {"nodos_pendientes": 4, "relaciones_pendientes": 17}

        s = FakeService()
        result = s.dashboard_kpis(date(2026, 3, 1), date(2026, 3, 31))

        self.assertIn("rango", result)
        self.assertIn("calidad_proveedor", result)
        self.assertIn("top_riesgos", result)
        self.assertIn("sla_revision", result)
        self.assertEqual(result["sla_revision"]["nodos_pendientes"], 4)


if __name__ == "__main__":
    unittest.main()
