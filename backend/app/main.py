from fastapi import FastAPI

from app.api.routes.mission import router as mission_router
from app.api.routes.terrain import router as terrain_router
from app.ai_copilot.routes import router as copilot_router


app = FastAPI(
    title="LUNA-SCOPE API",
    description="Lunar mission analysis and decision-support services",
    version="0.1.0",
)

# Existing scientific APIs
app.include_router(mission_router)
app.include_router(terrain_router)

# AI Mission Copilot API
app.include_router(copilot_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "project": "LUNA-SCOPE"
    }