from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from strawberry.fastapi import GraphQLRouter
from uuid import UUID

from app.graphql.schema import schema


app = FastAPI(title="Meds-Search Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(GraphQLRouter(schema, multipart_uploads_enabled=True), prefix="/graphql")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/cotizacion/{lote_id}/exportar")
async def exportar_cotizacion(
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
    if lote.status != "COMPLETED":
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
