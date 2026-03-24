from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from neo4j import GraphDatabase


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


CALIDAD_PROVEEDOR_CYPHER = """
MATCH (c:Cotizacion_Proveedor)
WHERE c.fecha >= date($fecha_desde) AND c.fecha <= date($fecha_hasta)
CALL {
    WITH c
    OPTIONAL MATCH (c)-[:TIENE_DETALLE]->(d:Detalle_Cotizacion_Proveedor)
    RETURN count(d) AS total_det
}
CALL {
    WITH c
    OPTIONAL MATCH (c)-[:TIENE_DETALLE]->(d:Detalle_Cotizacion_Proveedor)-[:COTIZADO_A]->(:Medicamento_Oficial)
    RETURN count(d) AS matched_det
}
CALL {
    WITH c
    OPTIONAL MATCH (c)-[:TIENE_DETALLE]->(d:Detalle_Cotizacion_Proveedor)-[:COTIZA_HUERFANO]->(:Medicamento_Huerfano)
    RETURN count(d) AS orphan_det
}
CALL {
    WITH c
    OPTIONAL MATCH (c)-[ok:COTIZADO_A]->(:Medicamento_Oficial)
    RETURN count(ok) AS matched_legacy
}
CALL {
    WITH c
    OPTIONAL MATCH (c)-[orphan:COTIZA_HUERFANO]->(:Medicamento_Huerfano)
    RETURN count(orphan) AS orphan_legacy
}
WITH c,
         CASE WHEN total_det > 0 THEN matched_det ELSE matched_legacy END AS matched,
         CASE WHEN total_det > 0 THEN orphan_det ELSE orphan_legacy END AS huerfanos
WITH c.proveedor AS proveedor, matched, huerfanos
WITH proveedor,
     sum(matched) AS total_match,
     sum(huerfanos) AS total_huerfanos,
     sum(matched) + sum(huerfanos) AS total_items
RETURN proveedor,
       total_match,
       total_huerfanos,
       total_items,
       CASE
         WHEN total_items = 0 THEN 0.0
         ELSE round((toFloat(total_huerfanos) / toFloat(total_items)) * 100.0, 2)
       END AS porcentaje_huerfanos
ORDER BY porcentaje_huerfanos DESC, total_huerfanos DESC
"""


TOP_RIESGOS_CYPHER = """
MATCH (h:Medicamento_Huerfano)
WHERE h.ultima_fecha >= date($fecha_desde) AND h.ultima_fecha <= date($fecha_hasta)
OPTIONAL MATCH (:Detalle_Cotizacion_Proveedor)-[rd:COTIZA_HUERFANO]->(h)
WITH h, count(rd) AS freq_det
OPTIONAL MATCH (:Cotizacion_Proveedor)-[rl:COTIZA_HUERFANO]->(h)
WITH h, freq_det, count(rl) AS freq_legacy
RETURN h.cum_recibido AS cum_recibido,
       coalesce(h.texto_original, '') AS texto_original,
    CASE WHEN freq_det > 0 THEN freq_det ELSE freq_legacy END AS frecuencia
ORDER BY frecuencia DESC, cum_recibido ASC
LIMIT 10
"""


SLA_PENDIENTE_CYPHER = """
MATCH (h:Medicamento_Huerfano)
WHERE coalesce(h.estado_revision, 'Pendiente') = 'Pendiente'
OPTIONAL MATCH (:Detalle_Cotizacion_Proveedor)-[rd:COTIZA_HUERFANO]->(h)
WITH h, count(rd) AS rel_det
OPTIONAL MATCH (:Cotizacion_Proveedor)-[rl:COTIZA_HUERFANO]->(h)
WITH h, rel_det, count(rl) AS rel_legacy
RETURN count(DISTINCT h) AS nodos_pendientes,
             CASE
                 WHEN sum(rel_det) > 0 THEN sum(rel_det)
                 ELSE sum(rel_legacy)
             END AS relaciones_pendientes
"""


@dataclass(slots=True)
class AuditoriaMetricasService:
    neo4j_uri: str = NEO4J_URI
    neo4j_user: str = NEO4J_USER
    neo4j_password: str = NEO4J_PASSWORD
    neo4j_database: str = NEO4J_DATABASE

    def __post_init__(self) -> None:
        self._driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "AuditoriaMetricasService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _run_list(self, query: str, **params: Any) -> list[dict[str, Any]]:
        with self._driver.session(database=self.neo4j_database) as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def _run_one(self, query: str, **params: Any) -> dict[str, Any]:
        with self._driver.session(database=self.neo4j_database) as session:
            row = session.run(query, **params).single()
            return dict(row) if row else {}

    def calidad_proveedor(self, fecha_desde: date, fecha_hasta: date) -> list[dict[str, Any]]:
        return self._run_list(
            CALIDAD_PROVEEDOR_CYPHER,
            fecha_desde=fecha_desde.isoformat(),
            fecha_hasta=fecha_hasta.isoformat(),
        )

    def top_riesgos_huerfanos(self, fecha_desde: date, fecha_hasta: date) -> list[dict[str, Any]]:
        return self._run_list(
            TOP_RIESGOS_CYPHER,
            fecha_desde=fecha_desde.isoformat(),
            fecha_hasta=fecha_hasta.isoformat(),
        )

    def volumen_revision_pendiente(self) -> dict[str, Any]:
        data = self._run_one(SLA_PENDIENTE_CYPHER)
        return {
            "nodos_pendientes": int(data.get("nodos_pendientes", 0)),
            "relaciones_pendientes": int(data.get("relaciones_pendientes", 0)),
        }

    def dashboard_kpis(self, fecha_desde: date, fecha_hasta: date) -> dict[str, Any]:
        return {
            "rango": {
                "fecha_desde": fecha_desde.isoformat(),
                "fecha_hasta": fecha_hasta.isoformat(),
            },
            "calidad_proveedor": self.calidad_proveedor(fecha_desde, fecha_hasta),
            "top_riesgos": self.top_riesgos_huerfanos(fecha_desde, fecha_hasta),
            "sla_revision": self.volumen_revision_pendiente(),
        }
