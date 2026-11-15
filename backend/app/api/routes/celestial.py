"""Celestial geometry for validated LOLA surface observers."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.scientific_engines.ephemeris.geometry import (
    CONVENTIONS, MAX_SAMPLES, MAX_STEP_S, MIN_STEP_S, InvalidEpoch, covered_et, epochs, geometry_at, utc_datetime,
)
from app.scientific_engines.ephemeris.kernels import KernelUnavailable, coverage, inventory
from app.scientific_engines.ephemeris.observer import Observer, ObserverUnavailable, UnsupportedObserver, resolve_observer
from app.scientific_engines.terrain.catalog import UnknownSiteError, get_site_config, list_site_ids

router = APIRouter(prefix="/terrain/explorer/celestial", tags=["Celestial Geometry"])


class TerrainPoint(BaseModel):
    easting_m: float = Field(allow_inf_nan=False)
    northing_m: float = Field(allow_inf_nan=False)


class ObserverRequest(BaseModel):
    site_id: str
    point: TerrainPoint | None = None


class EpochRequest(ObserverRequest):
    utc: str


class SeriesRequest(ObserverRequest):
    start_utc: str
    end_utc: str
    step_seconds: int = Field(ge=MIN_STEP_S, le=MAX_STEP_S, strict=True)


class Direction(BaseModel):
    azimuth_deg: float | None
    elevation_deg: float
    body_fixed_unit_vector: tuple[float, float, float]
    enu_unit_vector: tuple[float, float, float]
    distance_km: float
    angular_diameter_deg: float
    light_time_s: float
    above_local_horizontal: bool


class Epoch(BaseModel):
    utc: str
    et_tdb_s: float
    sun: Direction
    earth: Direction


class Kernel(BaseModel):
    file: str
    url: str
    sha256: str


class Coverage(BaseModel):
    start_utc: str
    end_utc: str
    start_et_tdb_s: float
    end_et_tdb_s: float


class SiteObserver(BaseModel):
    site_id: str
    name: str
    observer: Observer | None
    error: str | None


class SeriesLimits(BaseModel):
    max_samples: int
    min_step_seconds: int
    max_step_seconds: int


class Metadata(BaseModel):
    sites: list[SiteObserver]
    coverage: Coverage | None
    error: str | None
    conventions: dict[str, str | bool]
    ephemeris: str
    kernels: list[Kernel]
    limits: SeriesLimits


class GeometryResult(BaseModel):
    status: Literal["computed"]
    observer: Observer
    quality_flags: list[str]
    conventions: dict[str, str | bool]
    ephemeris: str
    kernels: list[Kernel]
    samples: list[Epoch]


def calculate(request, times, range_end=None):
    try:
        point = (request.point.easting_m, request.point.northing_m) if request.point else None
        observer = resolve_observer(request.site_id, point)
        if range_end is not None:
            covered_et(range_end)
        samples = [geometry_at(observer, time) for time in times]
        flags = ["native_cell_height", "no_quantified_direction_uncertainty", "terrain_obstruction_not_evaluated"]
        if times[0].year < 1972:
            flags.append("pre_1972_time_uses_spice_utc_convention")
        if times[-1] > datetime.now(timezone.utc):
            flags.append("future_civil_leap_seconds_not_predicted")
        return {"status": "computed", "observer": observer, "quality_flags": flags,
                "conventions": CONVENTIONS, "ephemeris": "JPL DE440s", "kernels": inventory(), "samples": samples}
    except UnknownSiteError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (InvalidEpoch, UnsupportedObserver) as exc:
        raise HTTPException(422, str(exc)) from exc
    except (KernelUnavailable, ObserverUnavailable) as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/metadata", response_model=Metadata)
def metadata():
    sites = []
    for site_id in list_site_ids():
        config = get_site_config(site_id)
        site = {"site_id": site_id, "name": config.get("display_name", config["name"])}
        try:
            sites.append({**site, "observer": resolve_observer(site_id), "error": None})
        except (ObserverUnavailable, UnsupportedObserver) as exc:
            sites.append({**site, "observer": None, "error": str(exc)})
    try:
        interval, error = coverage(), None
    except KernelUnavailable as exc:
        interval, error = None, str(exc)
    return {"sites": sites, "coverage": interval, "error": error, "conventions": CONVENTIONS,
            "ephemeris": "JPL DE440s", "kernels": inventory(),
            "limits": {"max_samples": MAX_SAMPLES, "min_step_seconds": MIN_STEP_S, "max_step_seconds": MAX_STEP_S}}


@router.post("/geometry", response_model=GeometryResult)
def geometry(request: EpochRequest):
    try:
        times = [utc_datetime(request.utc)]
    except InvalidEpoch as exc:
        raise HTTPException(422, str(exc)) from exc
    return calculate(request, times)


@router.post("/series", response_model=GeometryResult)
def series(request: SeriesRequest):
    try:
        end = utc_datetime(request.end_utc)
        times = epochs(utc_datetime(request.start_utc), end, request.step_seconds)
    except InvalidEpoch as exc:
        raise HTTPException(422, str(exc)) from exc
    return calculate(request, times, range_end=end)
