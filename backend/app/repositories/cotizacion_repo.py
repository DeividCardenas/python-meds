"""
Repositorio de acceso a datos para cotizaciones de lote.

Centraliza las operaciones CRUD sobre la tabla cotizaciones_lote
(modelo CotizacionLote) en la base de datos de pricing.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from app.models.cotizacion import CotizacionLote


async def get_lote(
    session,
    lote_id: UUID,
) -> Optional[CotizacionLote]:
    """Retorna el lote de cotización por su PK, o None si no existe."""
    return await session.get(CotizacionLote, lote_id)


async def update_lote_status(
    session,
    lote_id: UUID,
    status: str,
    resumen: Optional[dict[str, Any]] = None,
    resultado: Optional[list[dict[str, Any]]] = None,
) -> Optional[CotizacionLote]:
    """
    Actualiza el status del lote y, opcionalmente, el resumen y el resultado JSONB.
    Hace commit y refresca el objeto.  Retorna el lote actualizado o None.
    """
    lote: Optional[CotizacionLote] = await session.get(CotizacionLote, lote_id)
    if lote is None:
        return None
    lote.status = status
    if resumen is not None:
        lote.resumen = resumen
    if resultado is not None:
        lote.resultado = resultado
    session.add(lote)
    await session.commit()
    await session.refresh(lote)
    return lote
