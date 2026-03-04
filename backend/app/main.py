import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from strawberry.fastapi import GraphQLRouter
from uuid import UUID
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.graphql.schema import schema
from app.models.enums import CotizacionStatus

# ---------------------------------------------------------------------------
# Rate limiter — 120 req/min por IP por defecto; 20 req/min en el endpoint
# de exportación para mitigar scraping masivo de datos de cotización.
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

# ---------------------------------------------------------------------------
# CORS — parametrizable vía variable de entorno CORS_ORIGINS.
# Separar múltiples orígenes con coma (ej: "https://app.com,https://admin.com").
# ---------------------------------------------------------------------------
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
CORS_ORIGINS = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]

app = FastAPI(title="Meds-Search Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(GraphQLRouter(schema, multipart_uploads_enabled=True), prefix="/graphql")


@app.get("/health")
@limiter.exempt
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/cotizacion/{lote_id}/exportar")
@limiter.limit("20/minute")
async def exportar_cotizacion(
    request: Request,
    lote_id: str,
    formato: str = "csv",
) -> Response:
    """
    Download the result of a completed bulk-quotation job as CSV or Excel.

    Parameters
    ----------
    lote_id : UUID of the CotizacionLote record.
    formato : "csv" (default) or "excel".
    """
    from app.models.cotizacion import CotizacionLote
    from app.services.bulk_quote_service import exportar_resultado
    from app.core.db import AsyncPricingSessionLocal

    try:
        lote_uuid = UUID(lote_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="lote_id inválido")

    async with AsyncPricingSessionLocal() as session:
        lote: CotizacionLote | None = await session.get(CotizacionLote, lote_uuid)

    if lote is None:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if lote.status != CotizacionStatus.COMPLETED:
        raise HTTPException(status_code=409, detail=f"Cotización en estado '{lote.status}', aún no disponible")
    if not lote.resultado:
        raise HTTPException(status_code=409, detail="Sin resultados disponibles")

    fmt = formato.lower()
    data = exportar_resultado(lote.resultado, formato=fmt)

    if fmt == "excel":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension  = "xlsx"
    else:
        media_type = "text/csv; charset=utf-8"
        extension  = "csv"

    filename = f"cotizacion_{lote_id[:8]}.{extension}"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
