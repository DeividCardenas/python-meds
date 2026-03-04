"""
Repositorio de acceso a datos para filas de staging de precios de proveedor.

Centraliza las operaciones sobre la tabla staging_precios_proveedor
(modelo StagingPrecioProveedor) en la base de datos de pricing.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlmodel import select

from app.models.pricing import StagingPrecioProveedor


async def get_filas_by_archivo(
    session,
    archivo_id: UUID,
) -> list[StagingPrecioProveedor]:
    """
    Devuelve todas las filas de staging asociadas a un ProveedorArchivo,
    ordenadas por fila_numero ascendente.
    """
    return (
        await session.exec(
            select(StagingPrecioProveedor)
            .where(StagingPrecioProveedor.archivo_id == archivo_id)
            .order_by(StagingPrecioProveedor.fila_numero)
        )
    ).all()


async def aprobar_fila(
    session,
    staging_id: UUID,
    id_cum: str,
) -> Optional[StagingPrecioProveedor]:
    """
    Aprueba una fila de staging asignándole un CUM y cambiando su estado
    a 'APROBADO'.  Hace commit y refresca el objeto.
    Retorna la fila actualizada, o None si no existe.
    """
    fila: Optional[StagingPrecioProveedor] = await session.get(
        StagingPrecioProveedor, staging_id
    )
    if fila is None:
        return None
    fila.cum_code = id_cum.strip()
    fila.estado_homologacion = "APROBADO"
    session.add(fila)
    await session.commit()
    await session.refresh(fila)
    return fila
