"""Earth visibility and independent antenna elevation eligibility."""
from threading import BoundedSemaphore
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.routes.celestial import Kernel, Metadata, metadata as celestial_metadata
from app.api.routes.illumination import AnalysisRequest
from app.scientific_engines.communication import service
from app.scientific_engines.ephemeris.geometry import MAX_STEP_S, MIN_STEP_S, utc_datetime
from app.scientific_engines.ephemeris.kernels import KernelUnavailable
from app.scientific_engines.ephemeris.observer import Observer, ObserverUnavailable
from app.scientific_engines.illumination.service import epochs_with_end
from app.scientific_engines.terrain.catalog import UnknownSiteError

router = APIRouter(prefix="/terrain/explorer/communication", tags=["Earth Communication Visibility"])
workers = BoundedSemaphore(2)
Criterion = Literal["centre", "any_disc", "full_disc", "centre_with_mask"]
State = Literal["visible", "obstructed", "unresolved"]
Disc = Literal["fully_obscured", "partially_visible", "fully_visible", "unresolved"]
Affine = tuple[float, float, float, float, float, float]


class Request(AnalysisRequest):
    antenna_min_elevation_deg: float = Field(default=0, ge=0, le=90, allow_inf_nan=False)
    criterion: Criterion = "centre"


class PointRequest(Request):
    utc: str


class SeriesRequest(Request):
    start_utc: str
    end_utc: str
    step_seconds: int = Field(ge=MIN_STEP_S, le=MAX_STEP_S, strict=True)
    refine_transitions: bool = True


class RegionRequest(PointRequest):
    side: int = Field(default=8, ge=2, le=service.MAX_SIDE, strict=True)


class Clearance(BaseModel):
    centre: float | None
    upper_limb: float | None
    lower_limb: float | None


class VisibilitySample(BaseModel):
    utc: str
    earth_azimuth_deg: float | None
    earth_elevation_deg: float
    earth_angular_radius_deg: float
    earth_enu_unit_vector: tuple[float, float, float]
    upper_limb_elevation_deg: float
    lower_limb_elevation_deg: float
    centre_above_horizontal: bool
    centre_state: State
    centre_native_clear: bool
    centre_reason: str
    antenna_eligible: bool
    criterion_state: State
    native_horizon_deg: float | None
    horizon_distance_m: float | None
    traced_distance_m: float
    centre_nodata_cells: int
    clearance_deg: Clearance
    rms_horizon_deg: tuple[float,float] | None
    rms_sensitive: bool | None
    disc_state: Disc
    disc_evidence: str
    disc_probe_counts: dict[State, int]
    native_clear_probes: int
    native_obstructed_probes: int
    probes_crossing_nodata: int


class TerrainSource(BaseModel):
    file: str
    source_url: str
    source_dem_sha256: str
    resolution_m: tuple[float,float]
    bounds_m: tuple[float,float,float,float]
    datum: str
    frame: str
    affine: Affine
    shape: tuple[int,int]
    rms_source_url: str | None


class CelestialSource(BaseModel):
    source: str
    conventions: dict[str,str | bool]
    kernels: list[Kernel]


class Method(BaseModel):
    name: str
    grazing_tolerance_deg: float
    radial_ceiling_m: float
    maximum_trace_distance_m: float
    rim_rays: int
    rms: str


class Provenance(BaseModel):
    site_id: str
    terrain: TerrainSource
    celestial: CelestialSource
    antenna_min_elevation_deg: float
    criterion: Criterion
    method: Method
    quality_flags: list[str]


class Interval(BaseModel):
    state: State
    start_utc: str
    end_utc: str
    duration_s: float


class Transition(BaseModel):
    start_utc: str
    end_utc: str
    from_state: State
    to_state: State


class Summary(BaseModel):
    duration_s: dict[State,float]
    longest_visible_s: float
    longest_interruption_s: float
    fraction_classified_time_visible: float | None
    transitions: list[Transition]
    intervals: list[Interval]


class ObserverResult(Provenance):
    observer: Observer
    requested_point_m: tuple[float,float] | None
    samples: list[VisibilitySample]
    summary: Summary
    requested_sample_count: int
    refinement_sample_count: int


class Region(BaseModel):
    left: int
    top: int
    width: int
    height: int
    affine: Affine
    requested_point_m: tuple[float,float] | None
    observers: list[Observer | None]


class RegionResult(Provenance):
    utc: str
    region: Region
    cells: list[VisibilitySample | None]
    counts: dict[str,int]
    percent_of_valid: dict[str,float | None]


class CommunicationMetadata(Metadata):
    visibility_criteria: list[Criterion]
    antenna_mask_limits_deg: tuple[int,int]
    max_region_side: int
    max_refinement_samples: int
    refinement_target_s: int


def checked(run):
    if not workers.acquire(blocking=False):
        raise HTTPException(503, "Both Earth visibility workers are busy. Retry after the current calculation.")
    try:
        return run()
    except UnknownSiteError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ObserverUnavailable, KernelUnavailable) as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        workers.release()


@router.get("/metadata", response_model=CommunicationMetadata)
def metadata():
    return {**celestial_metadata(), "visibility_criteria":service.CRITERIA, "antenna_mask_limits_deg":(0,90),
            "max_region_side":service.MAX_SIDE, "max_refinement_samples":service.REFINEMENT_BUDGET,
            "refinement_target_s":service.REFINEMENT_TARGET_S}


@router.post("/point", response_model=ObserverResult)
def point(request: PointRequest):
    return checked(lambda: service.observer_analysis(request.site_id, request.projected_point(),
        [utc_datetime(request.utc)], request.antenna_min_elevation_deg, request.criterion))


@router.post("/series", response_model=ObserverResult)
def series(request: SeriesRequest):
    def run():
        times = epochs_with_end(utc_datetime(request.start_utc), utc_datetime(request.end_utc), request.step_seconds)
        return service.observer_analysis(request.site_id, request.projected_point(), times, request.antenna_min_elevation_deg,
                                         request.criterion, request.refine_transitions)
    return checked(run)


@router.post("/region", response_model=RegionResult)
def region(request: RegionRequest):
    return checked(lambda: service.region_analysis(request.site_id, request.projected_point(), utc_datetime(request.utc),
                                                   request.side, request.antenna_min_elevation_deg, request.criterion))
