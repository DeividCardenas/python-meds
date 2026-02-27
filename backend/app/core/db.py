import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# ---------------------------------------------------------------------------
# Catalog DB  (medicamentos, medicamentos_cum, cargas_archivo, cum_sync_log,
#              precios_referencia)
# ---------------------------------------------------------------------------
CATALOG_URL = os.getenv(
    "DB_CATALOG_URL",
    os.getenv("DB_URL", "postgresql+asyncpg://genhospi_admin:genhospi2026@db:5432/genhospi_catalog"),
)

# ---------------------------------------------------------------------------
# Pricing DB  (proveedores, proveedor_aliases, proveedor_archivos,
#              staging_precios_proveedor)
# ---------------------------------------------------------------------------
PRICING_URL = os.getenv(
    "DB_PRICING_URL",
    "postgresql+asyncpg://genhospi_admin:genhospi2026@db:5432/genhospi_pricing",
)

# --- Catalog engine ----------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    CATALOG_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# --- Pricing engine ----------------------------------------------------------
pricing_engine: AsyncEngine = create_async_engine(
    PRICING_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)
AsyncPricingSessionLocal = async_sessionmaker(pricing_engine, class_=AsyncSession, expire_on_commit=False)


def create_task_session_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Short-lived engine for catalog operations in Celery tasks."""
    task_engine = create_async_engine(CATALOG_URL, echo=False, future=True)
    return task_engine, async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)


def create_pricing_task_session_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Short-lived engine for pricing operations in Celery tasks."""
    task_engine = create_async_engine(PRICING_URL, echo=False, future=True)
    return task_engine, async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_pricing_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncPricingSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
