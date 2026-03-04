"""
seed_precios_proveedor_demo.py
==============================
Puebla la tabla ``precios_proveedor`` con datos de demostración para que
los cruces del pipeline de cotización retornen precios reales.

Estrategia
----------
1. Lee todos los ``id_cum`` activos de genhospi_catalog.medicamentos.
2. En genhospi_pricing crea 3 proveedores demo si no existen.
3. Para cada CUM inserta entre 1 y 3 precios (un proveedor distinto cada uno)
   con valores realistas en COP según la forma farmacéutica del medicamento.
4. Inserta directamente en ``precios_proveedor`` (bypassea el flujo de
   staging/revisión ya que la data es demo conocida).

Uso dentro del contenedor:
    docker exec python-meds-backend-1 \\
        python /app/src/seed_precios_proveedor_demo.py

Desde el host:
    docker compose exec backend python /app/src/seed_precios_proveedor_demo.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Connection URLs ────────────────────────────────────────────────────────
# SECURITY: no se aceptan fallbacks con credenciales — definir en el entorno o .env
CATALOG_URL = os.environ["DATABASE_URL"]
PRICING_URL = os.environ["PRICING_DATABASE_URL"]

# ─── Random seed para reproducibilidad ─────────────────────────────────────
random.seed(42)

# ─── Proveedores demo a crear ───────────────────────────────────────────────
DEMO_PROVIDERS = [
    {
        "id":     "11111111-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
        "nombre": "MEGALABS COLOMBIA S.A.S.",
        "codigo": "MEGALABS_DEMO",
    },
    {
        "id":     "22222222-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
        "nombre": "LA SANTE LABORATORIOS S.A.",
        "codigo": "LASANTE_DEMO",
    },
    {
        "id":     "33333333-cccc-4ccc-cccc-cccccccccccc",
        "nombre": "DISTRIBUIDORA NACIONAL FARMACEUTICA S.A.",
        "codigo": "DISNAFAR_DEMO",
    },
]

# Un archivo de carga fijo por proveedor para simplificar
DEMO_ARCHIVO_IDS = {
    "MEGALABS_DEMO":  "aaaa0001-0000-4000-a000-000000000001",
    "LASANTE_DEMO":   "bbbb0002-0000-4000-b000-000000000002",
    "DISNAFAR_DEMO":  "cccc0003-0000-4000-c000-000000000003",
}

# ─── Rangos de precio por forma farmacéutica (COP) ─────────────────────────
# (precio_min, precio_max) → unidad de dispensación
_PRECIO_RANGES: dict[str, tuple[int, int]] = {
    "tableta":            (250,   1_800),
    "capsula":            (280,   2_200),
    "solucion oral":      (4_500, 18_000),
    "solucion inyectable":(2_800, 45_000),
    "suspension oral":    (5_000, 22_000),
    "jarabe":             (7_000, 28_000),
    "crema":              (4_000, 25_000),
    "unguento":           (3_500, 22_000),
    "gel":                (4_000, 20_000),
    "polvo":              (3_000, 15_000),
    "parche":             (8_000, 55_000),
    "inhalador":         (25_000,180_000),
    "colirio":            (6_000, 30_000),
    "ovulo":              (3_500, 12_000),
    "supositorio":        (2_800, 10_000),
}
_PRECIO_DEFAULT = (500, 5_000)

# IVA estándar en Colombia: 0% o 19%
_IVA_OPTIONS = [Decimal("0.0000"), Decimal("0.1900")]


def _precio_para_forma(forma_farmaceutica: str | None) -> tuple[Decimal, Decimal]:
    """
    Devuelve (precio_unidad, precio_presentacion) en COP para la forma dada.
    precio_presentacion ≈ precio_unidad * unidades_en_caja
    """
    forma_lower = (forma_farmaceutica or "").lower()
    precio_min, precio_max = _PRECIO_DEFAULT
    for keyword, rango in _PRECIO_RANGES.items():
        if keyword in forma_lower:
            precio_min, precio_max = rango
            break

    # Variación aleatoria entre min y max
    unidad = Decimal(str(random.randint(precio_min, precio_max)))

    # Unidades en caja: 10, 20, 30, 60, 100 según la forma
    if "inyectable" in forma_lower or "iv" in forma_lower:
        caja = random.choice([5, 10, 25, 50])
    elif "tableta" in forma_lower or "capsula" in forma_lower:
        caja = random.choice([10, 20, 30, 60, 100])
    else:
        caja = random.choice([1, 6, 12])

    presentacion = unidad * caja
    return unidad, presentacion


def _variante_precio(base_unidad: Decimal, factor: float) -> tuple[Decimal, Decimal]:
    """Ajusta el precio base por un factor para simular diferencias entre proveedores."""
    nuevo = Decimal(str(round(float(base_unidad) * factor, 2)))
    presentacion = nuevo * 30  # presentación genérica
    return nuevo, presentacion


# ─── Main ─────────────────────────────────────────────────────────────────

async def _ensure_provider(conn, proveedor: dict) -> None:
    """Inserta el proveedor si no existe (idempotente por codigo)."""
    exist = await conn.execute(
        text("SELECT id FROM proveedores WHERE codigo = :c"),
        {"c": proveedor["codigo"]},
    )
    if exist.fetchone():
        return
    await conn.execute(
        text(
            "INSERT INTO proveedores (id, nombre, codigo) "
            "VALUES (:id, :nombre, :codigo)"
        ),
        {
            "id":     proveedor["id"],
            "nombre": proveedor["nombre"],
            "codigo": proveedor["codigo"],
        },
    )
    logger.info("Proveedor creado: %s", proveedor["nombre"])


async def _ensure_archivo(conn, archivo_id: str, proveedor_id: str, filename: str) -> None:
    """Inserta registro de archivo si no existe (idempotente por id)."""
    exist = await conn.execute(
        text("SELECT id FROM proveedor_archivos WHERE id = :i"),
        {"i": archivo_id},
    )
    if exist.fetchone():
        return
    await conn.execute(
        text(
            "INSERT INTO proveedor_archivos "
            "(id, proveedor_id, filename, status, fecha_carga) "
            "VALUES (:id, :prov_id, :fn, 'PROCESSED', :ts)"
        ),
        {
            "id":      archivo_id,
            "prov_id": proveedor_id,
            "fn":      filename,
            "ts":      datetime.now(timezone.utc),
        },
    )


async def main() -> None:
    # ── Conectar a ambas bases ───────────────────────────────────────────────
    catalog_engine = create_async_engine(CATALOG_URL, pool_size=2)
    pricing_engine = create_async_engine(PRICING_URL, pool_size=2)

    # ── 1. Leer medicamentos del catálogo ────────────────────────────────────
    logger.info("Leyendo medicamentos activos del catálogo…")
    async with catalog_engine.connect() as cat_conn:
        result = await cat_conn.execute(
            text(
                "SELECT id_cum, forma_farmaceutica "
                "FROM medicamentos "
                "WHERE activo = true AND id_cum IS NOT NULL "
                "ORDER BY id_cum"
            )
        )
        medicamentos = result.fetchall()

    total_meds = len(medicamentos)
    logger.info("  %d CUM activos encontrados", total_meds)

    # ── 2. Poblar pricing DB ─────────────────────────────────────────────────
    async with pricing_engine.begin() as pr_conn:
        # 2a. Proveedores
        for prov in DEMO_PROVIDERS:
            await _ensure_provider(pr_conn, prov)

        # 2b. Archivos de carga (uno por proveedor)
        for prov in DEMO_PROVIDERS:
            archivo_id  = DEMO_ARCHIVO_IDS[prov["codigo"]]
            await _ensure_archivo(
                pr_conn, archivo_id, prov["id"],
                f"demo_{prov['codigo'].lower()}_2026.csv",
            )

        # 2c. Contar cuántos precios ya existen con proveedores demo
        existing_result = await pr_conn.execute(
            text(
                "SELECT COUNT(*) FROM precios_proveedor pp "
                "JOIN proveedores p ON p.id = pp.proveedor_id "
                "WHERE p.codigo LIKE '%_DEMO'"
            )
        )
        existing_count = existing_result.scalar() or 0
        logger.info("  %d precios demo ya existen", existing_count)

        if existing_count >= total_meds:
            logger.info("Los precios demo ya están poblados. Nada que hacer.")
            return

        # 2d. Para cada CUM, insertar precios de 1-3 proveedores
        # Determinar qué CUMs ya tienen precio demo
        existing_cum_result = await pr_conn.execute(
            text(
                "SELECT DISTINCT pp.cum_code FROM precios_proveedor pp "
                "JOIN proveedores p ON p.id = pp.proveedor_id "
                "WHERE p.codigo LIKE '%_DEMO'"
            )
        )
        existing_cums = {row[0] for row in existing_cum_result.fetchall()}

        insert_count = 0
        batch: list[dict] = []

        VIGENTE_DESDE = date(2025, 1, 1)

        for med_row in medicamentos:
            cum_id   = med_row[0]
            forma    = med_row[1]

            if cum_id in existing_cums:
                continue

            # Precio base del proveedor 1 (MEGALABS)
            pu1, pp1 = _precio_para_forma(forma)
            iva = random.choice(_IVA_OPTIONS)

            # Decide cuántos proveedores ofrecen este CUM
            n_proveedores = random.choices([1, 2, 3], weights=[30, 45, 25])[0]

            providers_to_use = random.sample(DEMO_PROVIDERS, n_proveedores)

            for idx, prov in enumerate(providers_to_use):
                archivo_id = DEMO_ARCHIVO_IDS[prov["codigo"]]
                factor = (1.0, 1.05, 0.97)[idx % 3]
                if idx == 0:
                    pu, pp = pu1, pp1
                else:
                    pu, pp = _variante_precio(pu1, factor)

                batch.append({
                    "id":                       str(uuid4()),
                    "staging_id":               str(uuid4()),
                    "archivo_id":               archivo_id,
                    "proveedor_id":             prov["id"],
                    "cum_code":                 cum_id,
                    "precio_unitario":          None,
                    "precio_unidad":            float(pu),
                    "precio_presentacion":      float(pp),
                    "porcentaje_iva":           float(iva),
                    "vigente_desde":            VIGENTE_DESDE,
                    "vigente_hasta":            None,
                    "fecha_vigencia_indefinida": True,
                    "confianza_score":          1.0,
                    "fecha_publicacion":        datetime.now(timezone.utc),
                })
                insert_count += 1

            # Flush en lotes de 500
            if len(batch) >= 500:
                await _flush_batch(pr_conn, batch)
                logger.info("  Insertados %d registros…", insert_count)
                batch = []

        if batch:
            await _flush_batch(pr_conn, batch)

    logger.info("✓ Seed completo — %d registros de precios demo insertados", insert_count)
    await catalog_engine.dispose()
    await pricing_engine.dispose()


async def _flush_batch(conn, batch: list[dict]) -> None:
    if not batch:
        return
    await conn.execute(
        text(
            "INSERT INTO precios_proveedor "
            "(id, staging_id, archivo_id, proveedor_id, cum_code, "
            " precio_unitario, precio_unidad, precio_presentacion, "
            " porcentaje_iva, vigente_desde, vigente_hasta, "
            " fecha_vigencia_indefinida, confianza_score, fecha_publicacion) "
            "VALUES "
            "(:id, :staging_id, :archivo_id, :proveedor_id, :cum_code, "
            " :precio_unitario, :precio_unidad, :precio_presentacion, "
            " :porcentaje_iva, :vigente_desde, :vigente_hasta, "
            " :fecha_vigencia_indefinida, :confianza_score, :fecha_publicacion) "
            "ON CONFLICT (staging_id) DO NOTHING"
        ),
        batch,
    )


if __name__ == "__main__":
    asyncio.run(main())
