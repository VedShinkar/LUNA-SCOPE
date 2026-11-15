"""Typed inputs and outputs for the integrated operational-window analysis."""
from typing import Literal

from pydantic import BaseModel, Field

from app.scientific_engines.ephemeris.observer import Observer

Condition = Literal["favourable", "unfavourable", "conditional", "unresolved", "invalid"]
Track = Literal["solar", "earth_centre", "earth_disc", "antenna", "mission"]


class MissionProfile(BaseModel):
    version: Literal["1"] = "1"
    name: str = Field(default="Demonstration", min_length=1, max_length=64)
    solar_required: bool = True
    earth_requirement: Literal["centre", "any_disc", "full_disc"] = "centre"
    prefer_full_disc: bool = False
    minimum_antenna_elevation_deg: float = Field(default=0, ge=0, le=90, allow_inf_nan=False)
    minimum_window_s: int = Field(default=3600, ge=0, le=90*86400, strict=True)


class Tracks(BaseModel):
    solar: Literal["illuminated", "shadowed", "unresolved", "invalid"]
    earth_centre: Literal["visible", "obstructed", "unresolved", "invalid"]
    earth_disc: Literal["fully_visible", "partially_visible", "fully_obscured", "unresolved", "invalid"]
    antenna: Literal["satisfied", "below_mask", "unresolved", "invalid"]
    mission: Condition


class Sample(BaseModel):
    utc: str
    solar_source_utc: str | None
    earth_source_utc: str | None
    tracks: Tracks
    solar_reason: str | None
    earth_reason: str | None
    disc_evidence: str | None
    flags: list[str]


class Interval(BaseModel):
    start_utc: str
    end_utc: str
    duration_s: float
    tracks: Tracks
    requires_sampling: bool


class Transition(BaseModel):
    track: Track
    start_utc: str
    end_utc: str
    from_state: str
    to_state: str


class FavourableWindow(BaseModel):
    start_utc: str
    end_utc: str
    duration_s: float
    meets_minimum: bool


class Summary(BaseModel):
    duration_s: dict[Condition, float]
    longest_favourable_s: float
    longest_unfavourable_s: float
    qualifying_favourable_s: float
    transition_count: int
    favourable_windows: list[FavourableWindow]


class Timeline(BaseModel):
    site_id: str
    observer: Observer
    start_utc: str
    end_utc: str
    step_seconds: int
    profile: MissionProfile
    samples: list[Sample]
    intervals: list[Interval]
    transitions: list[Transition]
    summary: Summary
    nominal_sample_count: int
    refinement_sample_count: int
    terrain: dict
    solar_engine: dict
    earth_engine: dict
    celestial: dict
    classification_rules: list[str]
    quality_flags: list[str]


class Comparison(BaseModel):
    start_utc: str
    end_utc: str
    step_seconds: int
    profile: MissionProfile
    timelines: list[Timeline]


class Inspection(BaseModel):
    site_id: str
    observer: Observer
    interval: Interval
    start_sample: Sample
    end_sample: Sample
    transition_brackets: list[Transition]
