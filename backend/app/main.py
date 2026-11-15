from fastapi import FastAPI

from app.api.routes.celestial import router as celestial_router
from app.api.routes.communication import router as communication_router
from app.api.routes.illumination import router as illumination_router
from app.api.routes.mission_timeline import router as mission_timeline_router
from app.api.routes.mission_intelligence import router as mission_intelligence_router
from app.api.routes.terrain import router as terrain_router

app = FastAPI(
    title="LUNA-SCOPE API",
    description="Lunar mission analysis and decision-support services",
    version="0.1.0",
)

app.include_router(terrain_router)
app.include_router(celestial_router)
app.include_router(illumination_router)
app.include_router(communication_router)
app.include_router(mission_timeline_router)
app.include_router(mission_intelligence_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "project": "LUNA-SCOPE"}
