"""Servicio de importación legado de listas de precios de proveedores.

Contiene la lógica de dominio del pipeline de importación original
(pre-refactoring) que lee un CSV/Excel de un proveedor, valida las filas,
y las persiste en las tablas ``medicamentos`` y ``precios_referencia``.

Separado de ``app.worker.tasks`` para que la lógica de negocio sea testeable
de forma independiente sin necesidad de arrancar un worker Celery.

Nota sobre duplicados
---------------------
``_normalize_decimal``, ``_normalize_bool`` y ``_read_dataframe`` son
funcionalmente distintas de sus homólogas en ``pricing_service.py``:

- ``_normalize_decimal`` devuelve ``float``; ``_parse_decimal`` devuelve ``Decimal``.
- ``_normalize_bool`` no existe en pricing_service ni en normalizer.
- ``_read_dataframe`` aquí no pasa ``infer_schema_length=0``, al contrario del
  equivalente en pricing_service que sí lo requiere para mantener todo como str.

Por eso se mantienen como copias propias de este módulo.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import polars as pl
from sqlalchemy import insert
from sqlmodel import select

from app.models.enums import CargaStatus
from app.models.medicamento import Medicamento, PrecioReferencia
from app.services.invima_service import procesar_maestro_invima
from app.worker.utils import _actualizar_estado

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de dominio
# ---------------------------------------------------------------------------

MIN_NAME_LENGTH = 3
REJECTED_NAME_TERMS = ("PENDIENTE", "INSUMO", "VARIOS")
COMPANY_COLUMNS = ("Empresa", "empresa", "Laboratorio", "laboratorio", "Fuente", "fuente")
PRICE_COLUMNS = ("Precio", "precio")
FU_COLUMNS = ("FU", "fu")
VPC_COLUMNS = ("VPC", "vpc")
NAME_COLUMNS = ("nombre_limpio", "Producto", "producto", "Nombre", "nombre")
REPORT_DIR = Path(os.getenv("REJECTION_REPORT_DIR", "/app/output"))


# ---------------------------------------------------------------------------
# Helpers de dominio
# ---------------------------------------------------------------------------


def _pick_existing_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    """Devuelve el primer candidato que exista en *columns*, o ``None``."""
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _normalize_decimal(value: Any) -> float | None:
    """Convierte un valor crudo (str, int, float) a float, tolerando comas y
    puntos como separadores de miles/decimales.

    Devuelve ``None`` si el valor está vacío o no es parseable.
    """
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


def _normalize_bool(value: Any) -> bool:
    """Convierte valores textuales de verdad (SI/YES/TRUE/1) a ``bool``."""
    if value is None:
        return False
    normalized = str(value).strip().upper()
    return normalized in {"SI", "SÍ", "YES", "TRUE", "1"}


def _es_nombre_valido(nombre: str) -> bool:
    """Valida que un nombre de medicamento tenga longitud mínima y no sea un
    término genérico rechazado (PENDIENTE, INSUMO, VARIOS).
    """
    nombre_limpio = nombre.strip()
    if len(nombre_limpio) < MIN_NAME_LENGTH:
        return False
    nombre_upper = nombre_limpio.upper()
    return not any(term in nombre_upper for term in REJECTED_NAME_TERMS)


def _read_dataframe(file_path: str) -> pl.DataFrame:
    """Lee un archivo CSV/TSV/Excel y devuelve un ``pl.DataFrame``.

    No aplica ``infer_schema_length=0`` (a diferencia de pricing_service)
    porque el pipeline legado necesita inferencia de tipos para operar
    correctamente sobre columnas numéricas.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pl.read_excel(path)
    if suffix in {".tsv", ".txt"}:
        return pl.read_csv(path, separator="\t")
    return pl.read_csv(path)


# ---------------------------------------------------------------------------
# Pipeline legado principal
# ---------------------------------------------------------------------------


async def procesar_archivo_legacy(
    carga_id: str,
    file_path: str,
    session_factory: Any,
) -> dict[str, Any]:
    """Pipeline legado de importación de listas de precios de proveedor.

    Lee el archivo en *file_path*, valida y persiste en ``medicamentos`` /
    ``precios_referencia``, y actualiza el estado de ``CargaArchivo``.

    Parámetros
    ----------
    carga_id:
        UUID (str) del registro ``CargaArchivo`` que se está procesando.
    file_path:
        Ruta al archivo CSV/TSV/Excel subido por el usuario.
    session_factory:
        Factoría de sesiones async para la DB de catálogo. El caller es
        responsable del ciclo de vida del engine subyacente.

    Devuelve un dict con totales ``{carga_id, status, total_filas,
    insertados, rechazados}``.
    """
    carga_uuid = UUID(carga_id)
    try:
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.PROCESSING)

        if not Path(file_path).exists():
            raise FileNotFoundError(f"No existe el archivo a procesar: {file_path}")

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
                nombre_limpio = item["nombre_limpio"]
                if nombre_limpio not in medicamento_ids:
                    medicamento_ids[nombre_limpio] = uuid4()

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

            async with session_factory() as session:
                existing_medicamentos = (
                    await session.exec(
                        select(Medicamento.id, Medicamento.nombre_limpio).where(
                            Medicamento.nombre_limpio.in_(list(medicamento_ids))
                        )
                    )
                ).all()
                existing_ids = {nombre_limpio: med_id for med_id, nombre_limpio in existing_medicamentos}
                for nombre_limpio, med_id in existing_ids.items():
                    medicamento_ids[nombre_limpio] = med_id

                medicamentos_payload = [
                    {"id": med_id, "nombre_limpio": name}
                    for name, med_id in medicamento_ids.items()
                    if name not in existing_ids
                ]

                if medicamentos_payload:
                    await session.execute(insert(Medicamento), medicamentos_payload)
                await session.execute(insert(PrecioReferencia), precios_payload)
                await session.commit()

        report_path = None
        if rejected_rows:
            REPORT_DIR.mkdir(parents=True, exist_ok=True)
            report_path = str(REPORT_DIR / f"reporte_rechazos_{carga_id}.csv")
            pl.DataFrame(rejected_rows).write_csv(report_path)

        errores_log: dict[str, Any] = {
            "total_filas": len(dataframe),
            "insertados": len(valid_rows),
            "rechazados": len(rejected_rows),
        }
        if report_path:
            errores_log["reporte_rechazos"] = report_path

        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.COMPLETED, errores_log=errores_log)
        return {"carga_id": carga_id, "status": CargaStatus.COMPLETED.value, **errores_log}

    except Exception as exc:  # noqa: BLE001
        logger.exception("Error procesando carga %s desde archivo %s", carga_id, file_path)
        await _actualizar_estado(
            session_factory,
            carga_uuid,
            CargaStatus.FAILED,
            errores_log={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise


# ---------------------------------------------------------------------------
# Pipeline INVIMA
# ---------------------------------------------------------------------------


async def procesar_invima(
    carga_id: str,
    file_path: str,
    session_factory: Any,
) -> dict[str, Any]:
    """Procesa un archivo maestro INVIMA delegando en ``procesar_maestro_invima``.

    Parámetros
    ----------
    carga_id:
        UUID (str) del registro ``CargaArchivo`` que se está procesando.
    file_path:
        Ruta al archivo maestro INVIMA subido.
    session_factory:
        Factoría de sesiones async para la DB de catálogo. El caller es
        responsable del ciclo de vida del engine subyacente.
    """
    carga_uuid = UUID(carga_id)
    try:
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.PROCESSING)

        if not Path(file_path).exists():
            raise FileNotFoundError(f"No existe el archivo maestro INVIMA: {file_path}")

        errores_log = await procesar_maestro_invima(file_path, session_factory=session_factory)
        await _actualizar_estado(session_factory, carga_uuid, CargaStatus.COMPLETED, errores_log=errores_log)
        return {"carga_id": carga_id, "status": CargaStatus.COMPLETED.value, **errores_log}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error procesando maestro INVIMA %s desde archivo %s", carga_id, file_path)
        await _actualizar_estado(
            session_factory,
            carga_uuid,
            CargaStatus.FAILED,
            errores_log={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise
