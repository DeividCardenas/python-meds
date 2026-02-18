from __future__ import annotations

import re
from typing import Optional

import strawberry
from strawberry.file_uploads import Upload

from app.core.db import AsyncSessionLocal
from app.models.medicamento import CargaArchivo, CargaStatus
from app.services.search import buscar_medicamentos_hibrido
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


async def _buscar_medicamentos(session, texto: str, empresa: Optional[str]) -> list[MedicamentoNode]:
    medicamentos = await buscar_medicamentos_hibrido(session, texto=texto, empresa=empresa)
    return [
        MedicamentoNode(id=strawberry.ID(str(item[0])), nombre_limpio=item[1], distancia=float(item[2]))
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
            return await _buscar_medicamentos(session, texto=texto, empresa=empresa)


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
