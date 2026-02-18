import asyncio
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import polars as pl

from celery import Celery
from sqlalchemy import insert

from app.core.db import AsyncSessionLocal
from app.models.medicamento import CargaArchivo, CargaStatus, Medicamento, PrecioReferencia


celery_app = Celery(
    "meds_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
)


MIN_NAME_LENGTH = 3
REJECTED_NAME_TERMS = ("PENDIENTE", "INSUMO", "VARIOS")
COMPANY_COLUMNS = ("Empresa", "empresa", "Laboratorio", "laboratorio", "Fuente", "fuente")
PRICE_COLUMNS = ("Precio", "precio")
FU_COLUMNS = ("FU", "fu")
VPC_COLUMNS = ("VPC", "vpc")
NAME_COLUMNS = ("nombre_limpio", "Producto", "producto", "Nombre", "nombre")
REPORT_DIR = Path(os.getenv("REJECTION_REPORT_DIR", "/app/output"))


def _pick_existing_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _normalize_decimal(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _es_nombre_valido(nombre: str) -> bool:
    nombre_limpio = nombre.strip()
    if len(nombre_limpio) < MIN_NAME_LENGTH:
        return False
    nombre_upper = nombre_limpio.upper()
    return not any(term in nombre_upper for term in REJECTED_NAME_TERMS)


def _read_dataframe(file_path: str) -> pl.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pl.read_excel(path)
    return pl.read_csv(path)


async def _actualizar_estado(
    carga_uuid: UUID,
    status: CargaStatus,
    errores_log: dict[str, Any] | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        carga = await session.get(CargaArchivo, carga_uuid)
        if carga is None:
            return
        carga.status = status
        carga.errores_log = errores_log
        session.add(carga)
        await session.commit()


async def _procesar_archivo(carga_id: str, file_path: str) -> dict[str, Any]:
    carga_uuid = UUID(carga_id)
    await _actualizar_estado(carga_uuid, CargaStatus.PROCESSING)

    try:
        dataframe = _read_dataframe(file_path)
        columns = dataframe.columns
        name_column = _pick_existing_column(columns, NAME_COLUMNS)
        company_column = _pick_existing_column(columns, COMPANY_COLUMNS)
        price_column = _pick_existing_column(columns, PRICE_COLUMNS)
        fu_column = _pick_existing_column(columns, FU_COLUMNS)
        vpc_column = _pick_existing_column(columns, VPC_COLUMNS)

        if name_column is None:
            raise ValueError("No se encontró columna de nombre de medicamento.")
        if company_column is None:
            raise ValueError("No se encontró columna de empresa.")

        rejected_rows: list[dict[str, Any]] = []
        valid_rows: list[dict[str, Any]] = []
        for row in dataframe.to_dicts():
            nombre_raw = row.get(name_column)
            empresa_raw = row.get(company_column)
            nombre = "" if nombre_raw is None else str(nombre_raw).strip()
            empresa = "" if empresa_raw is None else str(empresa_raw).strip()
            precio = _normalize_decimal(row.get(price_column)) if price_column else None
            fu = _normalize_decimal(row.get(fu_column)) if fu_column else None
            vpc = _normalize_decimal(row.get(vpc_column)) if vpc_column else None

            rejection_reasons: list[str] = []
            if not _es_nombre_valido(nombre):
                rejection_reasons.append("Nombre Inválido")
            if precio is None or precio <= 0:
                rejection_reasons.append("Precio Cero o Nulo")
            if not empresa:
                rejection_reasons.append("Empresa Vacía")

            if rejection_reasons:
                rejected_rows.append({**row, "motivo_rechazo": "; ".join(rejection_reasons)})
                continue

            valid_rows.append(
                {
                    "nombre_limpio": nombre,
                    "empresa": empresa,
                    "precio": precio,
                    "fu": fu,
                    "vpc": vpc,
                }
            )

        if valid_rows:
            medicamento_ids: dict[str, UUID] = {}
            for item in valid_rows:
                medicamento_ids.setdefault(item["nombre_limpio"], uuid4())

            medicamentos_payload = [{"id": med_id, "nombre_limpio": name} for name, med_id in medicamento_ids.items()]
            precios_payload = [
                {
                    "id": uuid4(),
                    "medicamento_id": medicamento_ids[item["nombre_limpio"]],
                    "empresa": item["empresa"],
                    "precio": item["precio"],
                    "fu": item["fu"],
                    "vpc": item["vpc"],
                }
                for item in valid_rows
            ]

            async with AsyncSessionLocal() as session:
                await session.execute(insert(Medicamento), medicamentos_payload)
                await session.execute(insert(PrecioReferencia), precios_payload)
                await session.commit()

        report_path = None
        if rejected_rows:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            report_path = str(REPORT_DIR / f"reporte_rechazos_{carga_id}.csv")
            pl.DataFrame(rejected_rows).write_csv(report_path)

        errores_log = {
            "total_filas": len(dataframe),
            "insertados": len(valid_rows),
            "rechazados": len(rejected_rows),
        }
        if report_path:
            errores_log["reporte_rechazos"] = report_path

        await _actualizar_estado(carga_uuid, CargaStatus.COMPLETED, errores_log=errores_log)
        return {"carga_id": carga_id, "status": CargaStatus.COMPLETED.value, **errores_log}
    except Exception as exc:  # noqa: BLE001
        await _actualizar_estado(
            carga_uuid,
            CargaStatus.FAILED,
            errores_log={"error": str(exc)},
        )
        raise


@celery_app.task(name="task_procesar_archivo")
def task_procesar_archivo(carga_id: str, file_path: str) -> dict[str, Any]:
    return asyncio.run(_procesar_archivo(carga_id, file_path))
