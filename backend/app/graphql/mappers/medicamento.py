from __future__ import annotations

from typing import Optional

import strawberry

from app.graphql.types.medicamento import MedicamentoNode
from app.models.medicamento import Medicamento as DBMedicamento
from app.repositories import medicamento_repo
from app.services.search import buscar_medicamentos_hibrido


def mapear_medicamento(db_med: DBMedicamento) -> MedicamentoNode:
    return MedicamentoNode(
        id=strawberry.ID(str(db_med.id)),
        id_cum=db_med.id_cum,
        nombre_comercial=db_med.nombre_comercial,
        marca_comercial=db_med.marca_comercial,
        nombre_limpio=db_med.nombre_limpio,
        dosis_cantidad=db_med.dosis_cantidad,
        dosis_unidad=db_med.dosis_unidad,
        forma_farmaceutica=db_med.forma_farmaceutica,
        via_administracion=db_med.via_administracion,
        presentacion=db_med.presentacion,
        tipo_liberacion=db_med.tipo_liberacion,
        volumen_solucion=db_med.volumen_solucion,
        principio_activo=db_med.principio_activo,
        laboratorio=db_med.laboratorio,
        registro_invima=db_med.registro_invima,
        estado_cum=db_med.estado_cum,
        activo=db_med.activo,
        distancia=0.0,
    )


async def _buscar_medicamentos(
    session,
    texto: str,
    empresa: Optional[str],
    solo_activos: bool = True,
    forma_farmaceutica: Optional[str] = None,
) -> list[MedicamentoNode]:
    medicamentos = await buscar_medicamentos_hibrido(
        session,
        texto=texto,
        empresa=empresa,
        solo_activos=solo_activos,
        forma_farmaceutica=forma_farmaceutica,
    )

    id_cums = [row[3] for row in medicamentos if row[3]]
    precios_map = await medicamento_repo.cargar_precios_sismed(session, id_cums)
    regulacion_map = await medicamento_repo.cargar_regulacion_cnpmdm(session, id_cums)

    return [
        MedicamentoNode(
            id=strawberry.ID(str(medicamento_id)),
            nombre_comercial=nombre_comercial,
            marca_comercial=marca_comercial,
            nombre_limpio=nombre_limpio,
            dosis_cantidad=float(dosis_cantidad) if dosis_cantidad is not None else None,
            dosis_unidad=dosis_unidad,
            distancia=float(distancia),
            id_cum=id_cum,
            laboratorio=laboratorio,
            forma_farmaceutica=forma_farmaceutica_val,
            via_administracion=via_administracion,
            presentacion=presentacion,
            tipo_liberacion=tipo_liberacion,
            volumen_solucion=float(volumen_solucion) if volumen_solucion is not None else None,
            registro_invima=registro_invima,
            principio_activo=principio_activo,
            precio_unitario=float(precios_map[id_cum].precio_sismed_minimo)
                if id_cum and id_cum in precios_map and precios_map[id_cum].precio_sismed_minimo is not None
                else None,
            precio_empaque=float(precios_map[id_cum].precio_sismed_maximo)
                if id_cum and id_cum in precios_map and precios_map[id_cum].precio_sismed_maximo is not None
                else None,
            es_regulado=bool(id_cum and id_cum in regulacion_map),
            precio_maximo_regulado=float(regulacion_map[id_cum].precio_maximo_venta)
                if id_cum and id_cum in regulacion_map and regulacion_map[id_cum].precio_maximo_venta is not None
                else None,
            activo=bool(activo),
            estado_cum=estado_cum,
        )
        for (
            medicamento_id,
            nombre_limpio,
            distancia,
            id_cum,
            nombre_comercial,
            marca_comercial,
            dosis_cantidad,
            dosis_unidad,
            laboratorio,
            forma_farmaceutica_val,
            via_administracion,
            presentacion,
            tipo_liberacion,
            volumen_solucion,
            registro_invima,
            principio_activo,
            activo,
            estado_cum,
            _rank,
        ) in medicamentos
    ]
