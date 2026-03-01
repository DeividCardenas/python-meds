"""
seed_regulados_demo.py
======================
Carga datos de demostración para la tabla precios_regulados_cnpmdm.

Busca los CUM reales en el catálogo y los inserta como regulados con
precios máximos referenciales basados en la Circular CNPMDM vigente.

Uso (dentro del contenedor):
    docker exec python-meds-backend-1 python /app/src/seed_regulados_demo.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.models.medicamento import PrecioReguladoCNPMDM  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://genhospi_admin:genhospi2026@db:5432/genhospi_catalog",
)

# ---------------------------------------------------------------------------
# Principios activos regulados y precio máximo referencial (COP)
# Basado en la Circular Única CNPMDM, Ministerio de Salud Colombia
# Se busca por principioactivo para máxima cobertura del catálogo.
# ---------------------------------------------------------------------------
REGULADOS: list[tuple[str, float]] = [
    # Analgésicos / antipiréticos
    ("Acetaminofen",                                       350.0),
    ("Dipirona",                                           320.0),
    # Antibióticos
    ("Amoxicilina",                                        680.0),
    ("Acido clavulanico",                                  680.0),
    ("Ciprofloxacina",                                     720.0),
    ("Azitromicina",                                      1850.0),
    ("Claritromicina",                                    2100.0),
    ("Doxiciclina",                                        580.0),
    ("Clindamicina",                                       780.0),
    ("Trimetoprim",                                        380.0),
    # AINEs
    ("Ibuprofeno",                                         380.0),
    ("Diclofenaco",                                        380.0),
    ("Naproxeno",                                          420.0),
    ("Meloxicam",                                          680.0),
    ("Celecoxib",                                          880.0),
    ("Etoricoxib",                                        2200.0),
    ("Butilescopolamina",                                  380.0),
    # Antihipertensivos
    ("Losartan",                                           520.0),
    ("Enalapril",                                          380.0),
    ("Amlodipino",                                         390.0),
    ("Captopril",                                          350.0),
    ("Valsartan",                                          780.0),
    ("Telmisartan",                                        890.0),
    ("Irbesartan",                                         780.0),
    ("Olmesartan",                                         980.0),
    ("Ramipril",                                           480.0),
    ("Perindopril",                                        580.0),
    ("Bisoprolol",                                         490.0),
    ("Carvedilol",                                         480.0),
    ("Metoprolol",                                         380.0),
    ("Doxazosina",                                         680.0),
    ("Espironolactona",                                    390.0),
    ("Eplerenona",                                        1800.0),
    # Diuréticos
    ("Furosemida",                                         310.0),
    ("Hidroclorotiazida",                                  280.0),
    ("Indapamida",                                         380.0),
    # Antidiabéticos
    ("Metformina",                                         420.0),
    ("Glibenclamida",                                      280.0),
    ("Glimepirida",                                        680.0),
    ("Sitagliptina",                                      4200.0),
    ("Linagliptina",                                      4200.0),
    ("Saxagliptina",                                      4200.0),
    ("Dapagliflozina",                                    4800.0),
    ("Empagliflozina",                                    4800.0),
    ("Canagliflozina",                                    4800.0),
    ("Liraglutida",                                      88000.0),
    ("Semaglutida",                                     125000.0),
    ("Dulaglutida",                                      95000.0),
    # Insulinas
    ("Insulina humana",                                  38000.0),
    ("Insulina isofana",                                 38000.0),
    ("Insulina glargina",                               125000.0),
    ("Insulina asparta",                                 42000.0),
    ("Insulina lispro",                                  42000.0),
    ("Insulina detemir",                                 95000.0),
    # Hipolipemiantes
    ("Atorvastatina",                                      490.0),
    ("Rosuvastatina",                                      780.0),
    ("Simvastatina",                                       380.0),
    ("Ezetimibe",                                         2800.0),
    ("Fenofibrato",                                        780.0),
    ("Acido fenofibrico",                                  780.0),
    # Anticoagulantes
    ("Rivaroxaban",                                      12800.0),
    ("Apixaban",                                         12800.0),
    ("Dabigatran",                                        9800.0),
    ("Warfarina",                                          380.0),
    ("Enoxaparina",                                      12000.0),
    ("Clopidogrel",                                        890.0),
    # Anticonvulsivantes / neuro
    ("Gabapentina",                                        680.0),
    ("Pregabalina",                                       1800.0),
    ("Carbamazepina",                                      480.0),
    ("Lamotrigina",                                        680.0),
    ("Levetiracetam",                                     2800.0),
    ("Lacosamida",                                        6200.0),
    ("Fenitoina",                                          380.0),
    ("Acido valproico",                                   1100.0),
    ("Valproato",                                         1100.0),
    # Antidepresivos / ansiolíticos / psiquiátricos
    ("Escitalopram",                                       780.0),
    ("Fluoxetina",                                         480.0),
    ("Sertralina",                                         580.0),
    ("Paroxetina",                                         580.0),
    ("Venlafaxina",                                        980.0),
    ("Desvenlafaxina",                                    3800.0),
    ("Duloxetina",                                        2200.0),
    ("Amitriptilina",                                      320.0),
    ("Clonazepam",                                         280.0),
    ("Alprazolam",                                         250.0),
    ("Haloperidol",                                        380.0),
    # Tiroides
    ("Levotiroxina",                                       320.0),
    # Antiulcerosos / gastrointestinal
    ("Esomeprazol",                                        880.0),
    ("Omeprazol",                                          480.0),
    ("Lansoprazol",                                        780.0),
    ("Pantoprazol",                                        680.0),
    ("Domperidona",                                        380.0),
    ("Dimenhidrinato",                                     280.0),
    ("Loperamida",                                         320.0),
    ("Bisacodilo",                                         280.0),
    # Antihistamínicos
    ("Loratadina",                                         290.0),
    ("Cetirizina",                                         320.0),
    ("Levocetirizina",                                     380.0),
    ("Desloratadina",                                      490.0),
    ("Bilastina",                                          980.0),
    ("Fexofenadina",                                       680.0),
    # Antifúngicos
    ("Fluconazol",                                         980.0),
    ("Itraconazol",                                       1800.0),
    # Antivirales
    ("Aciclovir",                                          420.0),
    ("Valaciclovir",                                       980.0),
    # Gota / uricosúricos
    ("Alopurinol",                                         320.0),
    ("Colchicina",                                         480.0),
    ("Febuxostat",                                        3200.0),
    # Corticoides
    ("Dexametasona",                                       380.0),
    ("Hidrocortisona",                                     490.0),
    ("Budesonida",                                        8500.0),
    ("Prednisona",                                         320.0),
    ("Prednisolona",                                       380.0),
    # Broncodilatadores / respiratorio
    ("Ipratropio",                                        4800.0),
    ("Salbutamol",                                        3200.0),
    ("Salmeterol",                                        8500.0),
    ("Formoterol",                                        9800.0),
    # Calcio / vitaminas / hierro
    ("Calcio carbonato",                                   380.0),
    ("Colecalciferol",                                     480.0),
    ("Hierro polimaltosado",                               580.0),
    ("Acido folico",                                       220.0),
    # Cardiovascular / otros
    ("Ivabradina",                                        2800.0),
    ("Cilostazol",                                        1800.0),
    ("Betahistina",                                        380.0),
    ("Donepecilo",                                        2800.0),
    ("Hidroxicloroquina",                                 3200.0),
    ("Dutasterida",                                       2800.0),
    ("Tamsulosina",                                       2800.0),
    # Antidiabéticos adicionales
    ("Pioglitazona",                                      1800.0),
    ("Acarbosa",                                           680.0),
]


async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    logger.info("Conectando a %s ...", DATABASE_URL)

    total_insertados = 0
    total_fallidos = 0
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        for nombre_patron, precio_max in REGULADOS:
            result = await session.execute(
                text("""
                    SELECT id_cum, descripcioncomercial
                    FROM medicamentos_cum
                    WHERE principioactivo ILIKE :patron
                    LIMIT 100
                """),
                {"patron": f"%{nombre_patron}%"},
            )
            rows = result.fetchall()

            if not rows:
                logger.warning("Sin coincidencias: %s", nombre_patron)
                total_fallidos += 1
                continue

            for id_cum, descripcion in rows:
                if not id_cum:
                    continue
                stmt = (
                    pg_insert(PrecioReguladoCNPMDM)
                    .values(
                        id_cum=id_cum,
                        precio_maximo_venta=precio_max,
                        circular_origen="Circular CNPMDM Demo 2024",
                        ultima_actualizacion=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["id_cum"],
                        set_={
                            "precio_maximo_venta": precio_max,
                            "circular_origen": "Circular CNPMDM Demo 2024",
                            "ultima_actualizacion": now,
                        },
                    )
                )
                await session.execute(stmt)
                total_insertados += 1
                logger.info("  + %s  |  %-60s  |  $%.0f", id_cum, descripcion[:60], precio_max)

        await session.commit()

    await engine.dispose()
    logger.info(
        "=== Completado: %d CUMs regulados cargados, %d patrones sin match ===",
        total_insertados,
        total_fallidos,
    )


if __name__ == "__main__":
    asyncio.run(main())
