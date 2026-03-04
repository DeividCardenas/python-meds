"""
Repositorio de acceso a datos para medicamentos.

Centraliza las queries sobre las tablas:
  - precios_medicamentos   (PrecioMedicamento  / SISMED)
  - precios_regulados_cnpmdm (PrecioReguladoCNPMDM)
  - medicamentos_cum       (Medicamento)
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func as safunc
from sqlmodel import select

from app.models.medicamento import Medicamento, PrecioMedicamento, PrecioReguladoCNPMDM


async def cargar_precios_sismed(
    session,
    id_cums: list[str],
) -> dict[str, PrecioMedicamento]:
    """
    Carga un registro de precios_medicamentos por id_cum (canal INS preferido,
    COM como fallback).  Retorna dict {id_cum: PrecioMedicamento}.
    """
    if not id_cums:
        return {}
    rows = (
        await session.exec(
            select(PrecioMedicamento).where(
                PrecioMedicamento.id_cum.in_(id_cums)  # type: ignore[attr-defined]
            )
        )
    ).all()
    # Preferir INS sobre COM; si no hay INS tomar COM
    best: dict[str, PrecioMedicamento] = {}
    for row in rows:
        existing = best.get(row.id_cum)
        if existing is None or (
            row.canal_mercado == "INS" and existing.canal_mercado != "INS"
        ):
            best[row.id_cum] = row
    return best


async def cargar_regulacion_cnpmdm(
    session,
    id_cums: list[str],
) -> dict[str, PrecioReguladoCNPMDM]:
    """
    Carga registros de precios_regulados_cnpmdm para los id_cums dados.
    Retorna dict {id_cum: PrecioReguladoCNPMDM}.
    Un medicamento está regulado si y solo si su id_cum aparece en esta tabla.
    """
    if not id_cums:
        return {}
    rows = (
        await session.exec(
            select(PrecioReguladoCNPMDM).where(
                PrecioReguladoCNPMDM.id_cum.in_(id_cums)  # type: ignore[attr-defined]
            )
        )
    ).all()
    return {row.id_cum: row for row in rows}


async def get_medicamentos_por_principio_activo(
    session,
    principio_activo: str,
    limite: int = 50,
) -> list[Medicamento]:
    """
    Devuelve todos los medicamentos que comparten el mismo principio_activo
    (comparación case-insensitive), ordenados por nombre_limpio.
    """
    pa_normalizado = principio_activo.strip().lower()
    if not pa_normalizado:
        return []
    stmt = (
        select(Medicamento)
        .where(safunc.lower(Medicamento.principio_activo) == pa_normalizado)
        .order_by(Medicamento.nombre_limpio)
        .limit(limite)
    )
    return (await session.exec(stmt)).all()
