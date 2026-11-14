
"""
LUNA-SCOPE Mission Intelligence API Routes.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.mission.decision_engine.assessment import assess_mission
from app.mission.decision_engine.scenario_comparison import compare_scenarios


router = APIRouter(
    prefix="/api/v1/mission",
    tags=["Mission Intelligence"]
)


# Maximum number of sites allowed in one comparison request.
MAX_COMPARISON_SITES = 10


# Request model for mission assessment.
class MissionAssessmentRequest(BaseModel):

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    site_id: str = Field(
        min_length=1,
        max_length=100
    )

    mission_profile_id: str = Field(
        min_length=1,
        max_length=100
    )


# Request model for scenario comparison.
class MissionComparisonRequest(BaseModel):

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    site_ids: list[str] = Field(
        min_length=1,
        max_length=MAX_COMPARISON_SITES
    )

    mission_profile_id: str = Field(
        min_length=1,
        max_length=100
    )

    @field_validator("site_ids")
    @classmethod
    def validate_site_ids(cls, site_ids):

        cleaned_ids = []

        for site_id in site_ids:

            if not isinstance(site_id, str):
                raise ValueError(
                    "Every site ID must be a string."
                )

            cleaned_id = site_id.strip()

            if not cleaned_id:
                raise ValueError(
                    "Site IDs cannot be empty or whitespace."
                )

            if len(cleaned_id) > 100:
                raise ValueError(
                    "Site IDs cannot exceed 100 characters."
                )

            cleaned_ids.append(cleaned_id)

        if len(cleaned_ids) != len(set(cleaned_ids)):
            raise ValueError(
                "Duplicate site IDs are not allowed."
            )

        return cleaned_ids


# Assess a lunar location.
@router.post("/assess")
def mission_assessment(request: MissionAssessmentRequest):

    try:

        result = assess_mission(
            site_id=request.site_id,
            profile_id=request.mission_profile_id
        )

        return result

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# Compare multiple lunar locations.
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
