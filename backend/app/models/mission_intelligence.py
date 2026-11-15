"""HTTP contracts for the existing mission decision and evidence services."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.mission.decision_engine.engine import DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS, SiteAssessment
from app.models.mission_timeline import MissionProfile, Summary
from app.scientific_engines.ephemeris.geometry import MAX_STEP_S, MIN_STEP_S, utc_datetime
from app.scientific_engines.ephemeris.observer import Observer
from app.scientific_engines.illumination.service import epochs_with_end

SiteId = Literal["Site04", "Site11", "Site23"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Weight = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Action = Literal["assessment", "terrain", "solar", "earth", "timeline", "compare_sites"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectedPoint(Input):
    easting_m: float = Field(allow_inf_nan=False)
    northing_m: float = Field(allow_inf_nan=False)

    def coordinates(self):
        return self.easting_m, self.northing_m


class Weights(Input):
    terrain_slope: Weight = DEFAULT_WEIGHTS.terrain_slope
    terrain_roughness: Weight = DEFAULT_WEIGHTS.terrain_roughness
    illumination_fraction: Weight = DEFAULT_WEIGHTS.illumination_fraction
    communication_fraction: Weight = DEFAULT_WEIGHTS.communication_fraction

    @model_validator(mode="after")
    def unit_sum(self):
        if abs(sum(self.model_dump().values()) - 1) > 1e-6:
            raise ValueError("Assessment weights must sum to 1.")
        return self


class Thresholds(Input):
    max_slope_deg: float = Field(default=DEFAULT_THRESHOLDS.max_slope_deg, gt=0, le=90)
    max_roughness_m: float = Field(default=DEFAULT_THRESHOLDS.max_roughness_m, gt=0, allow_inf_nan=False)


class Equipment(Input):
    name: Name
    minimum_antenna_elevation_deg: float = Field(ge=0, le=90, allow_inf_nan=False)


class TimeSelection(Input):
    utc: str | None = None
    start_utc: str | None = None
    end_utc: str | None = None
    step_seconds: int = Field(default=3600, ge=MIN_STEP_S, le=MAX_STEP_S, strict=True)

    def window(self):
        if self.start_utc is not None and self.end_utc is not None:
            return utc_datetime(self.start_utc), utc_datetime(self.end_utc)
        return None

    @model_validator(mode="after")
    def valid_schedule(self):
        if self.utc is not None:
            utc_datetime(self.utc)
        if self.utc is not None and (self.start_utc is not None or self.end_utc is not None):
            raise ValueError("Choose either an evaluation instant or a UTC range.")
        if (self.start_utc is None) != (self.end_utc is None):
            raise ValueError("A UTC range needs both endpoints.")
        if window := self.window():
            start, end = window
            if end <= start:
                raise ValueError("Use an increasing UTC range.")
            epochs_with_end(start, end, self.step_seconds)
        return self


class Scenario(Input):
    site_id: SiteId
    point: ProjectedPoint | None = None
    profile: MissionProfile = Field(default_factory=MissionProfile)
    equipment: Equipment | None = None

    def effective_profile(self):
        if self.equipment is None:
            return self.profile
        return self.profile.model_copy(update={
            "minimum_antenna_elevation_deg": self.equipment.minimum_antenna_elevation_deg,
        })


class AssessmentRequest(Scenario, TimeSelection):
    weights: Weights = Field(default_factory=Weights)
    thresholds: Thresholds = Field(default_factory=Thresholds)


class NamedScenario(Scenario):
    name: Name


class ComparisonRequest(TimeSelection):
    scenarios: list[NamedScenario] = Field(min_length=2, max_length=6)
    weights: Weights = Field(default_factory=Weights)
    thresholds: Thresholds = Field(default_factory=Thresholds)

    @model_validator(mode="after")
    def distinct_names(self):
        if len({item.name.casefold() for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("Scenario names must be unique.")
        return self


class TimelineEvidence(BaseModel):
    start_utc: str
    end_utc: str
    summary: Summary
    terrain: dict
    celestial: dict
    quality_flags: list[str]
    classification_rules: list[str]


class AssessmentResult(BaseModel):
    request: AssessmentRequest
    observer: Observer
    effective_profile: MissionProfile
    assessment: SiteAssessment
    contributions: dict[str, float | None]
    operational_screen: Literal["met", "not_met", "unresolved", "unavailable"]
    timeline: TimelineEvidence | None = None
    snapshot: dict | None = None
    limitations: list[str]


class ScenarioResult(BaseModel):
    name: str
    result: AssessmentResult | None = None
    unavailable: str | None = None


class ScenarioDifference(BaseModel):
    baseline: str
    scenario: str
    changes: list[str]
    score_delta: float | None = None


class ComparisonResult(BaseModel):
    scenarios: list[ScenarioResult]
    ranked_groups: list[list[str]]
    explanations: list[str]
    differences: list[ScenarioDifference]


class CopilotRequest(AssessmentRequest):
    action: Action


class CopilotResult(BaseModel):
    action: Action
    context: AssessmentRequest
    observer: Observer | None = None
    response: dict | None = None
    assessment: AssessmentResult | None = None
    comparison: ComparisonResult | None = None
    missing_inputs: list[str] = Field(default_factory=list)
