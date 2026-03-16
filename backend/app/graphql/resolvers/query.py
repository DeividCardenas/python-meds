from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import strawberry
from sqlmodel import select

from app.core.db import AsyncSessionLocal, AsyncPricingSessionLocal
from app.models.enums import CargaStatus
from app.models.medicamento import CargaArchivo
from app.models.pricing import PrecioProveedor, Proveedor as ProveedorModel
from app.services.pricing_service import buscar_sugerencias_cum
from app.repositories import medicamento_repo, cotizacion_repo, staging_repo
from app.graphql.types.medicamento import MedicamentoNode, CargaArchivoNode, SugerenciaCUMNode
from app.graphql.types.pricing import StagingFilaNode
from app.graphql.types.cotizacion import CotizacionLoteNode
from app.graphql.mappers.medicamento import _buscar_medicamentos
from app.graphql.mappers.cotizacion import _lote_to_node


@strawberry.type
class Query:
    @strawberry.field
    async def buscar_medicamentos(
        self,
        texto: str,
        empresa: Optional[str] = None,
        solo_activos: bool = True,
        forma_farmaceutica: Optional[str] = None,
    ) -> list[MedicamentoNode]:
        async with AsyncSessionLocal() as session:
            return await _buscar_medicamentos(
                session,
                texto=texto,
                empresa=empresa,
                solo_activos=solo_activos,
                forma_farmaceutica=forma_farmaceutica,
            )

    @strawberry.field
    async def get_status_carga(self, id: strawberry.ID) -> Optional[CargaArchivoNode]:
        """
        Retorna el estado de un archivo de carga identificado por su UUID.

        Contratos de respuesta:
          - ID válido y encontrado → ``CargaArchivoNode`` con los campos ``id``, ``filename``, ``status``.
          - ID válido pero inexistente → ``null``  (no lista vacía, no error).
          - ID con formato no-UUID    → ``null``  (la excepción se absorbe en silencio).

        Nota para el cliente: el campo puede ser ``null``; evaluar con
        ``if (result !== null)`` en lugar de ``result.length``.
        """
        try:
            carga_id = UUID(str(id))
        except ValueError:
            return None
        async with AsyncSessionLocal() as session:
            carga = (
                await session.exec(select(CargaArchivo).where(CargaArchivo.id == carga_id))
            ).first()
            if carga is None:
                return None
            status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
            return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)

    @strawberry.field
    async def comparativa_precios(self, principio_activo: str) -> list[MedicamentoNode]:
        """Return all medications sharing the same principio_activo for price comparison."""
        async with AsyncSessionLocal() as session:
            medicamentos = await medicamento_repo.get_medicamentos_por_principio_activo(
                session, principio_activo
            )
            if not medicamentos:
                return []
            id_cums = [m.id_cum for m in medicamentos if m.id_cum]
            precios_map = await medicamento_repo.cargar_precios_sismed(session, id_cums)
            regulacion_map = await medicamento_repo.cargar_regulacion_cnpmdm(session, id_cums)

        # Cargar mejor precio de proveedor por cum_code desde la BD de precios
        best_proveedor: dict[str, tuple[float, str]] = {}
        if id_cums:
            async with AsyncPricingSessionLocal() as pricing_session:
                price_rows = (
                    await pricing_session.exec(
                        select(PrecioProveedor)
                        .where(PrecioProveedor.cum_code.in_(id_cums))  # type: ignore[attr-defined]
                        .where(PrecioProveedor.precio_unitario.isnot(None))  # type: ignore[attr-defined]
                        .order_by(PrecioProveedor.precio_unitario.asc())  # type: ignore[attr-defined]
                    )
                ).all()
                # Primer registro por cum_code = precio más bajo
                best_por_cum: dict[str, PrecioProveedor] = {}
                for p in price_rows:
                    if p.cum_code not in best_por_cum:
                        best_por_cum[p.cum_code] = p
                # Resolver nombres de proveedores en un solo query
                proveedor_ids = [p.proveedor_id for p in best_por_cum.values() if p.proveedor_id]
                proveedor_names: dict[str, str] = {}
                if proveedor_ids:
                    prov_rows = (
                        await pricing_session.exec(
                            select(ProveedorModel).where(
                                ProveedorModel.id.in_(proveedor_ids)  # type: ignore[attr-defined]
                            )
                        )
                    ).all()
                    proveedor_names = {str(p.id): p.nombre for p in prov_rows}
                for cum_code, price_row in best_por_cum.items():
                    precio = float(price_row.precio_unitario)  # type: ignore[arg-type]
                    nombre = (
                        proveedor_names.get(str(price_row.proveedor_id), "")
                        if price_row.proveedor_id
                        else ""
                    )
                    best_proveedor[cum_code] = (precio, nombre)

        return [
            MedicamentoNode(
                id=strawberry.ID(str(m.id)),
                nombre_comercial=m.nombre_comercial,
                marca_comercial=m.marca_comercial,
                nombre_limpio=m.nombre_limpio,
                dosis_cantidad=m.dosis_cantidad,
                dosis_unidad=m.dosis_unidad,
                distancia=0.0,
                id_cum=m.id_cum,
                laboratorio=m.laboratorio,
                forma_farmaceutica=m.forma_farmaceutica,
                via_administracion=m.via_administracion,
                presentacion=m.presentacion,
                tipo_liberacion=m.tipo_liberacion,
                volumen_solucion=m.volumen_solucion,
                registro_invima=m.registro_invima,
                principio_activo=m.principio_activo,
                precio_unitario=float(precios_map[m.id_cum].precio_sismed_minimo)
                    if m.id_cum and m.id_cum in precios_map and precios_map[m.id_cum].precio_sismed_minimo is not None
                    else None,
                precio_empaque=float(precios_map[m.id_cum].precio_sismed_maximo)
                    if m.id_cum and m.id_cum in precios_map and precios_map[m.id_cum].precio_sismed_maximo is not None
                    else None,
                es_regulado=bool(m.id_cum and m.id_cum in regulacion_map),
                precio_maximo_regulado=float(regulacion_map[m.id_cum].precio_maximo_venta)
                    if m.id_cum and m.id_cum in regulacion_map and regulacion_map[m.id_cum].precio_maximo_venta is not None
                    else None,
                mejor_precio_proveedor=best_proveedor[m.id_cum][0] if m.id_cum and m.id_cum in best_proveedor else None,
                mejor_proveedor_nombre=best_proveedor[m.id_cum][1] if m.id_cum and m.id_cum in best_proveedor else None,
            )
            for m in medicamentos
        ]

    @strawberry.field
    async def sugerencias_cum(self, texto: str) -> list[SugerenciaCUMNode]:
        """Return up to 3 CUM code suggestions for a free-text description."""
        async with AsyncSessionLocal() as session:
            sugerencias = await buscar_sugerencias_cum(session, texto, limite=3)
        return [
            SugerenciaCUMNode(
                id_cum=s["id_cum"],
                nombre=s["nombre"],
                score=s["score"],
                principio_activo=s.get("principio_activo"),
                laboratorio=s.get("laboratorio"),
            )
            for s in sugerencias
        ]

    @strawberry.field
    async def get_staging_filas(self, archivo_id: strawberry.ID) -> list[StagingFilaNode]:
        """Return all staging rows for a given supplier file upload."""
        try:
            archivo_uuid = UUID(str(archivo_id))
        except ValueError:
            return []
        async with AsyncPricingSessionLocal() as session:
            filas = await staging_repo.get_filas_by_archivo(session, archivo_uuid)
        return [
            StagingFilaNode(
                id=strawberry.ID(str(fila.id)),
                fila_numero=fila.fila_numero,
                cum_code=fila.cum_code,
                precio_unitario=float(fila.precio_unitario) if fila.precio_unitario is not None else None,
                precio_unidad=float(fila.precio_unidad) if fila.precio_unidad is not None else None,
                precio_presentacion=float(fila.precio_presentacion) if fila.precio_presentacion is not None else None,
                porcentaje_iva=float(fila.porcentaje_iva) if fila.porcentaje_iva is not None else None,
                descripcion_raw=fila.descripcion_raw,
                estado_homologacion=fila.estado_homologacion,
                sugerencias_cum=json.dumps(fila.sugerencias_cum) if fila.sugerencias_cum else None,
                datos_raw=json.dumps(fila.datos_raw),
                fecha_vigencia_indefinida=bool(fila.fecha_vigencia_indefinida),
                confianza_score=float(fila.confianza_score) if fila.confianza_score is not None else None,
            )
            for fila in filas
        ]

    @strawberry.field
    async def get_cotizacion(self, id: strawberry.ID) -> Optional[CotizacionLoteNode]:
        """Return the status and results of a bulk-quotation job."""
        try:
            lote_uuid = UUID(str(id))
        except ValueError:
            return None
        async with AsyncPricingSessionLocal() as session:
            lote = await cotizacion_repo.get_lote(session, lote_uuid)
        if lote is None:
            return None
        # Look up regulation data for all matched cum_ids
        regulacion_map: dict = {}
        if lote.resultado:
            cum_ids = [f.get("cum_id") for f in lote.resultado if f.get("cum_id")]
            if cum_ids:
                async with AsyncSessionLocal() as session:
                    regulacion_map = await medicamento_repo.cargar_regulacion_cnpmdm(session, cum_ids)
        return _lote_to_node(lote, regulacion_map)
