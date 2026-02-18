from __future__ import annotations

from typing import Optional

import strawberry
from sqlalchemy import select
from strawberry.fastapi import BaseContext
from strawberry.file_uploads import Upload
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.medicamento import CargaArchivo, CargaStatus, Medicamento
from app.worker.tasks import task_procesar_archivo


@strawberry.type
class MedicamentoNode:
    id: strawberry.ID
    nombre_limpio: str
    distancia: float


@strawberry.type
class CargaArchivoNode:
    id: strawberry.ID
    filename: str
    status: str


async def _buscar_medicamentos_mock(
    session: AsyncSession,
    texto: str,
    empresa: Optional[str],
) -> list[MedicamentoNode]:
    _ = empresa
    statement = select(Medicamento).where(Medicamento.nombre_limpio.ilike(f"%{texto}%")).limit(10)
    medicamentos = (await session.exec(statement)).all()
    return [
        MedicamentoNode(id=strawberry.ID(str(item.id)), nombre_limpio=item.nombre_limpio, distancia=0.0)
        for item in medicamentos
    ]


@strawberry.type
class Query:
    @strawberry.field
    async def buscar_medicamentos(
        self,
        info: BaseContext,
        texto: str,
        empresa: Optional[str] = None,
    ) -> list[MedicamentoNode]:
        _ = info
        async with AsyncSessionLocal() as session:
            return await _buscar_medicamentos_mock(session, texto=texto, empresa=empresa)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def subir_archivo(self, info: BaseContext, file: Upload) -> CargaArchivoNode:
        _ = info
        async with AsyncSessionLocal() as session:
            carga = CargaArchivo(filename=file.filename, status=CargaStatus.PENDING)
            session.add(carga)
            await session.commit()
            await session.refresh(carga)

        task_procesar_archivo.delay(str(carga.id), file.filename)
        status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
        return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)


schema = strawberry.Schema(query=Query, mutation=Mutation)
