from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from uuid import UUID

import strawberry
from strawberry.file_uploads import Upload
from sqlmodel import select

from app.core.db import AsyncSessionLocal
from app.models.medicamento import CargaArchivo, CargaStatus
from app.services.search import buscar_medicamentos_hibrido
from app.worker.tasks import task_procesar_archivo, task_procesar_invima


@strawberry.type
class MedicamentoNode:
    id: strawberry.ID
    nombre_limpio: str
    distancia: float
    id_cum: Optional[str]
    laboratorio: Optional[str]


@strawberry.type
class CargaArchivoNode:
    id: strawberry.ID
    filename: str
    status: str


async def _buscar_medicamentos(session, texto: str, empresa: Optional[str]) -> list[MedicamentoNode]:
    medicamentos = await buscar_medicamentos_hibrido(session, texto=texto, empresa=empresa)
    return [
        MedicamentoNode(
            id=strawberry.ID(str(medicamento_id)),
            nombre_limpio=nombre_limpio,
            distancia=float(distancia),
            id_cum=id_cum,
            laboratorio=laboratorio,
        )
        for medicamento_id, nombre_limpio, distancia, id_cum, laboratorio, _rank in medicamentos
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

    @strawberry.field
    async def get_status_carga(self, id: strawberry.ID) -> Optional[CargaArchivoNode]:
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


async def _registrar_carga(file: Upload, max_size_bytes: int | None = None) -> tuple[CargaArchivo, Path]:
    if max_size_bytes is not None:
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
    uploads_dir = Path("/app/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        carga = CargaArchivo(filename=filename, status=CargaStatus.PENDING)
        session.add(carga)
        await session.commit()
        await session.refresh(carga)

    stored_path = uploads_dir / f"{carga.id}_{filename}"
    file.file.seek(0)
    with stored_path.open("wb") as output_file:
        output_file.write(file.file.read())

    return carga, stored_path


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def subir_archivo(self, file: Upload) -> CargaArchivoNode:
        carga, stored_path = await _registrar_carga(file, max_size_bytes=10 * 1024 * 1024)
        task_procesar_archivo.delay(str(carga.id), str(stored_path))
        status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
        return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)

    @strawberry.mutation
    async def cargar_maestro_invima(self, file: Upload) -> CargaArchivoNode:
        carga, stored_path = await _registrar_carga(file)
        task_procesar_invima.delay(str(carga.id), str(stored_path))
        status = carga.status.value if isinstance(carga.status, CargaStatus) else str(carga.status)
        return CargaArchivoNode(id=strawberry.ID(str(carga.id)), filename=carga.filename, status=status)


schema = strawberry.Schema(query=Query, mutation=Mutation)
