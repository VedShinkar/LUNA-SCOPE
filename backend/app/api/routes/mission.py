"""
LUNA-SCOPE Mission Intelligence API Routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.mission.decision_engine.assessment import assess_mission
from app.mission.decision_engine.scenario_comparison import compare_scenarios


router = APIRouter(
    prefix="/api/v1/mission",
    tags=["Mission Intelligence"]
)


# Request model for mission assessment
class MissionAssessmentRequest(BaseModel):

    site_id: str

    mission_profile_id: str

    scenario_id: str | None = None

    equipment_profile_id: str | None = None


# Request model for scenario comparison
class MissionComparisonRequest(BaseModel):

    site_ids: list[str] = Field(min_length=1)

    mission_profile_id: str


# Assess a lunar location
@router.post("/assess")
def mission_assessment(request: MissionAssessmentRequest):

    try:

        result = assess_mission(
            site_id=request.site_id,
            profile_id=request.mission_profile_id,
            scenario_id=request.scenario_id,
            equipment_profile_id=request.equipment_profile_id
        )

        return result

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# Compare multiple lunar locations
@router.post("/compare")
def mission_comparison(request: MissionComparisonRequest):

    try:

        result = compare_scenarios(
            site_ids=request.site_ids,
            profile_id=request.mission_profile_id
        )

        return {
            "mission_profile_id": request.mission_profile_id,
            "results": result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )