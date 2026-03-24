from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import bindparam, text
from sqlmodel import select

from app.models.pricing import PrecioProveedor, StagingPrecioProveedor


PRICING_ENFORCE_INTEGRITY_CHECKS = os.getenv("PRICING_ENFORCE_INTEGRITY_CHECKS", "true").lower() == "true"


@dataclass(slots=True)
class PricingIntegrityReport:
    total_rows: int
    violations: dict[str, int]
    samples: dict[str, list[dict[str, Any]]]

    @property
    def blocking_violations(self) -> int:
        return sum(self.violations.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "violations": self.violations,
            "blocking_violations": self.blocking_violations,
            "samples": self.samples,
        }


def _sample_row(row: Any, motivo: str) -> dict[str, Any]:
    return {
        "motivo": motivo,
        "staging_id": str(getattr(row, "id", "")),
        "cum_code": str(getattr(row, "cum_code", "") or ""),
        "medicamento_id": str(getattr(row, "medicamento_id", "") or ""),
        "vigente_desde": str(getattr(row, "vigente_desde", "") or ""),
        "vigente_hasta": str(getattr(row, "vigente_hasta", "") or ""),
    }


async def validar_integridad_publicacion_staging(
    filas: list[StagingPrecioProveedor],
    catalog_session_factory: Any | None,
) -> PricingIntegrityReport:
    """
    Valida filas APROBADAS de staging contra reglas de integridad de negocio.

    Reglas bloqueantes:
    - cum_code obligatorio.
    - El CUM debe existir en catálogo (si hay acceso al catálogo).
    - Si medicamento_id está presente, debe corresponder al CUM del catálogo.
    - Al menos un precio numérico positivo entre unitario/unidad/presentación.
    - vigente_desde no puede ser mayor que vigente_hasta.
    """
    violations: dict[str, int] = {
        "cum_code_vacio": 0,
        "cum_no_existe_catalogo": 0,
        "medicamento_id_no_coincide_con_cum": 0,
        "sin_precio_positivo": 0,
        "rango_vigencia_invalido": 0,
    }
    samples: dict[str, list[dict[str, Any]]] = {k: [] for k in violations}

    cum_to_med: dict[str, Any] = {}
    medid_to_cum: dict[str, str] = {}

    if catalog_session_factory is not None:
        cums = sorted({(f.cum_code or "").strip() for f in filas if (f.cum_code or "").strip()})
        if cums:
            async with catalog_session_factory() as cat_session:
                stmt = text(
                    """
                    SELECT id, id_cum
                    FROM medicamentos
                    WHERE id_cum IN :cums
                    """
                ).bindparams(bindparam("cums", expanding=True))
                rows = (await cat_session.execute(stmt, {"cums": cums})).fetchall()
                cum_to_med = {str(r.id_cum): r.id for r in rows if r.id_cum}
                medid_to_cum = {str(r.id): str(r.id_cum) for r in rows if r.id and r.id_cum}

    for fila in filas:
        cum = (fila.cum_code or "").strip()
        precio_unitario = float(fila.precio_unitario or 0)
        precio_unidad = float(fila.precio_unidad or 0)
        precio_presentacion = float(fila.precio_presentacion or 0)

        if not cum:
            violations["cum_code_vacio"] += 1
            if len(samples["cum_code_vacio"]) < 10:
                samples["cum_code_vacio"].append(_sample_row(fila, "cum_code_vacio"))
            continue

        if catalog_session_factory is not None and cum_to_med and cum not in cum_to_med:
            violations["cum_no_existe_catalogo"] += 1
            if len(samples["cum_no_existe_catalogo"]) < 10:
                samples["cum_no_existe_catalogo"].append(_sample_row(fila, "cum_no_existe_catalogo"))

        if fila.medicamento_id is not None and catalog_session_factory is not None:
            expected_cum = medid_to_cum.get(str(fila.medicamento_id))
            if expected_cum is not None and expected_cum != cum:
                violations["medicamento_id_no_coincide_con_cum"] += 1
                if len(samples["medicamento_id_no_coincide_con_cum"]) < 10:
                    samples["medicamento_id_no_coincide_con_cum"].append(
                        _sample_row(fila, "medicamento_id_no_coincide_con_cum")
                    )

        if max(precio_unitario, precio_unidad, precio_presentacion) <= 0:
            violations["sin_precio_positivo"] += 1
            if len(samples["sin_precio_positivo"]) < 10:
                samples["sin_precio_positivo"].append(_sample_row(fila, "sin_precio_positivo"))

        if fila.vigente_desde is not None and fila.vigente_hasta is not None and fila.vigente_desde > fila.vigente_hasta:
            violations["rango_vigencia_invalido"] += 1
            if len(samples["rango_vigencia_invalido"]) < 10:
                samples["rango_vigencia_invalido"].append(_sample_row(fila, "rango_vigencia_invalido"))

    return PricingIntegrityReport(total_rows=len(filas), violations=violations, samples=samples)


async def auditar_integridad_precios_publicados(
    pricing_session_factory: Any,
    catalog_session_factory: Any | None,
    *,
    max_rows: int = 50000,
) -> dict[str, Any]:
    """
    Auditoría periódica de integridad para precios ya publicados.

    Se centra en reglas no costosas para detectar deriva operativa.
    """
    async with pricing_session_factory() as p_session:
        stmt = select(PrecioProveedor).limit(max_rows)
        filas = (await p_session.exec(stmt)).all()

    report: dict[str, Any] = {
        "audit_scope_rows": len(filas),
        "checked_at": date.today().isoformat(),
        "violations": {
            "cum_code_vacio": 0,
            "sin_precio_positivo": 0,
            "rango_vigencia_invalido": 0,
            "cum_no_existe_catalogo": 0,
        },
    }

    cums = sorted({(f.cum_code or "").strip() for f in filas if (f.cum_code or "").strip()})
    valid_cums: set[str] = set()

    if cums and catalog_session_factory is not None:
        async with catalog_session_factory() as c_session:
            stmt = text(
                """
                SELECT id_cum
                FROM medicamentos
                WHERE id_cum IN :cums
                """
            ).bindparams(bindparam("cums", expanding=True))
            rows = (await c_session.execute(stmt, {"cums": cums})).fetchall()
            valid_cums = {str(r.id_cum) for r in rows if r.id_cum}

    for fila in filas:
        cum = (fila.cum_code or "").strip()
        precio_unitario = float(fila.precio_unitario or 0)
        precio_unidad = float(fila.precio_unidad or 0)
        precio_presentacion = float(fila.precio_presentacion or 0)

        if not cum:
            report["violations"]["cum_code_vacio"] += 1
        if max(precio_unitario, precio_unidad, precio_presentacion) <= 0:
            report["violations"]["sin_precio_positivo"] += 1
        if fila.vigente_desde is not None and fila.vigente_hasta is not None and fila.vigente_desde > fila.vigente_hasta:
            report["violations"]["rango_vigencia_invalido"] += 1
        if catalog_session_factory is not None and valid_cums and cum and cum not in valid_cums:
            report["violations"]["cum_no_existe_catalogo"] += 1

    report["blocking_violations"] = sum(report["violations"].values())
    return report
