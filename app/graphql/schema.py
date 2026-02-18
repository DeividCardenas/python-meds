from __future__ import annotations

import re
from typing import Optional

import strawberry
from sqlalchemy import bindparam, func, select
from strawberry.file_uploads import Upload
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.medicamento import CargaArchivo, CargaStatus, Medicamento, PrecioReferencia
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
    statement = select(Medicamento).where(Medicamento.nombre_limpio.ilike(func.concat("%", bindparam("texto"), "%")))
    statement = statement.params(texto=texto)
    if empresa:
        statement = (
            statement.join(PrecioReferencia, PrecioReferencia.medicamento_id == Medicamento.id)
            .where(PrecioReferencia.empresa == bindparam("empresa"))
            .params(empresa=empresa)
            .distinct()
        )
    statement = statement.limit(10)
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
        texto: str,
        empresa: Optional[str] = None,
    ) -> list[MedicamentoNode]:
        async with AsyncSessionLocal() as session:
            return await _buscar_medicamentos_mock(session, texto=texto, empresa=empresa)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def subir_archivo(self, file: Upload) -> CargaArchivoNode:
        max_size_bytes = 10 * 1024 * 1024
        current_offset = file.file.tell()
        file.file.seek(0, 2)
        if file.file.tell() > max_size_bytes:
            file.file.seek(current_offset)
            raise ValueError("El archivo excede el tamaño máximo permitido (10MB).")
        file.file.seek(current_offset)

        incoming_name = (file.filename or "").replace("\0", "").strip()
        base_name = incoming_name.split("/")[-1].split("\\")[-1]
        if base_name in {"", ".", ".."}:
            base_name = "upload.bin"

        stem, dot, extension = base_name.rpartition(".")
        if not dot:
            stem, extension = base_name, ""

        safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem) or "upload"
        safe_extension = re.sub(r"[^a-zA-Z0-9]", "", extension)
        filename = f"{safe_stem}.{safe_extension}" if safe_extension else safe_stem
        async with AsyncSessionLocal() as session:
            carga = CargaArchivo(filename=filename, status=CargaStatus.PENDING)
            session.add(carga)
            await session.commit()
            await session.refresh(carga)

        task_procesar_archivo.delay(str(carga.id), filename)
        status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
        return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)


schema = strawberry.Schema(query=Query, mutation=Mutation)
