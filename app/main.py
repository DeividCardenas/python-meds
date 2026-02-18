from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.graphql.schema import schema


app = FastAPI(title="Meds-Search Backend")
app.include_router(GraphQLRouter(schema), prefix="/graphql")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
