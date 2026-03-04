"""Servicio centralizado para recepcionar y guardar archivos subidos vía Upload.

Proporciona tres funciones especializadas según el tipo de entidad que se crea
en base de datos, más funciones auxiliares de sanitización y verificación de
tamaño reutilizables.

Tipos de upload soportados
--------------------------
* ``registrar_carga_catalogo``  → ``CargaArchivo``   (DB catálogo)
* ``registrar_carga_proveedor`` → ``ProveedorArchivo`` (DB pricing)
* ``registrar_carga_cotizacion``→ ``CotizacionLote``  (DB pricing)
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Callable

from strawberry.file_uploads import Upload

from app.models.cotizacion import CotizacionLote
from app.models.enums import CargaStatus, CotizacionStatus
from app.models.medicamento import CargaArchivo
from app.models.pricing import ProveedorArchivo

# Directorio compartido donde se almacenan todos los uploads
UPLOADS_DIR = Path("/app/uploads")

# Límite predeterminado de tamaño (10 MB) para catálogos y archivos de proveedor
DEFAULT_MAX_SIZE: int = 10 * 1024 * 1024

# SECURITY: únicas extensiones aceptadas para uploads de datos
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"csv", "xlsx", "xls"})


# ---------------------------------------------------------------------------
# Funciones auxiliares internas
# ---------------------------------------------------------------------------


def _verificar_tamano(file: Upload, max_size_bytes: int) -> None:
    """Lanza ``ValueError`` si el archivo supera *max_size_bytes*.

    Restaura la posición del cursor al valor original tras la verificación.
    """
    current_offset = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current_offset)
    if size > max_size_bytes:
        raise ValueError("El archivo excede el tamaño máximo permitido (10MB).")


def _verificar_extension(filename: str) -> None:
    """Lanza ``ValueError`` si la extensión del archivo no está en la whitelist.

    Previene que archivos ejecutables o de script renombrados como .csv
    sean aceptados por el sistema.

    Args:
        filename: Nombre de archivo ya sanitizado.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Tipo de archivo no permitido: '.{ext}'. "
            f"Solo se aceptan: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )


def _guardar_en_disco(file: Upload, stored_path: Path) -> None:
    """Escribe el contenido íntegro del upload en *stored_path*."""
    file.file.seek(0)
    with stored_path.open("wb") as output_file:
        output_file.write(file.file.read())


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def sanitizar_nombre_archivo(
    filename_raw: str,
    default_base: str = "upload.bin",
) -> str:
    """Limpia y sanitiza el nombre de archivo recibido del upload.

    Previene path traversal, elimina caracteres no seguros y devuelve un
    nombre de archivo apto para almacenamiento en disco.

    Args:
        filename_raw: Nombre de archivo tal como lo reporta el cliente.
        default_base: Nombre de archivo completo a usar cuando el nombre
            resultante esté vacío o sea peligroso (e.g. ``"upload.bin"``,
            ``"lista.csv"``).

    Returns:
        Nombre de archivo sanitizado listo para uso en disco.
    """
    # SECURITY: normalizar Unicode antes de procesar para prevenir variantes
    # de barra de ruta Unicode (\u2215, \uFF0F) que eluden split literal
    incoming_name = unicodedata.normalize("NFKC", (filename_raw or "")).replace("\0", "").strip()
    base_name = incoming_name.split("/")[-1].split("\\")[-1]
    if not base_name or base_name in {".", ".."}:
        base_name = default_base

    stem, dot, extension = base_name.rpartition(".")
    if not dot:
        stem, extension = base_name, ""

    # Stem de reserva derivado de default_base para mantener coherencia semántica
    default_stem = default_base.split(".")[0] if "." in default_base else default_base
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem) or default_stem
    safe_extension = re.sub(r"[^a-zA-Z0-9]", "", extension)

    return f"{safe_stem}.{safe_extension}" if safe_extension else safe_stem


async def registrar_carga_catalogo(
    file: Upload,
    session_factory: Callable,
    max_size_bytes: int | None = DEFAULT_MAX_SIZE,
) -> tuple[CargaArchivo, Path]:
    """Guarda un archivo de catálogo y crea el registro ``CargaArchivo``.

    Args:
        file: Objeto ``Upload`` de Strawberry.
        session_factory: Factoría de sesión asíncrona para la DB de catálogo
            (típicamente ``AsyncSessionLocal``).
        max_size_bytes: Límite de tamaño en bytes; ``None`` para omitir la
            comprobación (e.g. en uploads de maestro INVIMA).

    Returns:
        Tupla ``(CargaArchivo, ruta_en_disco)``.
    """
    if max_size_bytes is not None:
        _verificar_tamano(file, max_size_bytes)

    filename = sanitizar_nombre_archivo(file.filename or "")
    _verificar_extension(filename)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    async with session_factory() as session:
        carga = CargaArchivo(filename=filename, status=CargaStatus.PENDING)
        session.add(carga)
        await session.commit()
        await session.refresh(carga)

    stored_path = UPLOADS_DIR / f"{carga.id}_{filename}"
    _guardar_en_disco(file, stored_path)

    return carga, stored_path


async def registrar_carga_proveedor(
    file: Upload,
    session_factory: Callable,
    max_size_bytes: int | None = DEFAULT_MAX_SIZE,
) -> tuple[ProveedorArchivo, Path]:
    """Guarda un archivo de proveedor y crea el registro ``ProveedorArchivo``.

    Args:
        file: Objeto ``Upload`` de Strawberry.
        session_factory: Factoría de sesión asíncrona para la DB de pricing
            (típicamente ``AsyncPricingSessionLocal``).
        max_size_bytes: Límite de tamaño en bytes; ``None`` para omitir la
            comprobación.

    Returns:
        Tupla ``(ProveedorArchivo, ruta_en_disco)``.
    """
    if max_size_bytes is not None:
        _verificar_tamano(file, max_size_bytes)

    filename = sanitizar_nombre_archivo(file.filename or "")
    _verificar_extension(filename)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    async with session_factory() as session:
        archivo = ProveedorArchivo(filename=filename, status=CargaStatus.PENDING)
        session.add(archivo)
        await session.commit()
        await session.refresh(archivo)

    stored_path = UPLOADS_DIR / f"{archivo.id}_{filename}"
    _guardar_en_disco(file, stored_path)

    return archivo, stored_path


async def registrar_carga_cotizacion(
    file: Upload,
    session_factory: Callable,
    hospital_id: str = "GLOBAL",
) -> tuple[CotizacionLote, Path]:
    """Guarda un archivo de cotización hospital y crea el registro ``CotizacionLote``.

    No aplica verificación de tamaño ya que los listados hospitalarios pueden
    superar los límites típicos de catálogos de proveedores.

    Args:
        file: Objeto ``Upload`` de Strawberry.
        session_factory: Factoría de sesión asíncrona para la DB de pricing
            (típicamente ``AsyncPricingSessionLocal``).
        hospital_id: Identificador del hospital; ``"GLOBAL"`` por defecto.

    Returns:
        Tupla ``(CotizacionLote, ruta_en_disco)``.
    """
    filename = sanitizar_nombre_archivo(file.filename or "", default_base="lista.csv")
    _verificar_extension(filename)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    async with session_factory() as session:
        lote = CotizacionLote(
            hospital_id=hospital_id,
            filename=filename,
            status=CotizacionStatus.PROCESSING,
        )
        session.add(lote)
        await session.commit()
        await session.refresh(lote)

    stored_path = UPLOADS_DIR / f"{lote.id}_{filename}"
    _guardar_en_disco(file, stored_path)

    return lote, stored_path
