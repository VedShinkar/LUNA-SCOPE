"""Solar-centre illumination on native LOLA terrain."""
from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.routes.celestial import TerrainPoint
from app.scientific_engines.ephemeris.geometry import MAX_STEP_S, MIN_STEP_S, utc_datetime
from app.scientific_engines.ephemeris.kernels import KernelUnavailable
from app.scientific_engines.ephemeris.observer import ObserverUnavailable
from app.scientific_engines.illumination.service import (
    MAX_REGION_EPOCHS, MAX_REGION_SIDE, epochs_with_end, observer_analysis, region_analysis,
)
from app.scientific_engines.terrain.catalog import UnknownSiteError

router = APIRouter(prefix="/terrain/explorer/illumination", tags=["Solar Illumination"])
workers = BoundedSemaphore(2)


class AnalysisRequest(BaseModel):
    site_id: str
    point: TerrainPoint | None = None

    def projected_point(self):
        return (self.point.easting_m, self.point.northing_m) if self.point else None


class PointRequest(AnalysisRequest):
    utc: str


class SeriesRequest(AnalysisRequest):
    start_utc: str
    end_utc: str
    step_seconds: int = Field(ge=MIN_STEP_S, le=MAX_STEP_S, strict=True)


class RegionRequest(AnalysisRequest):
    times_utc: list[str] = Field(min_length=1, max_length=MAX_REGION_EPOCHS)
    side: int = Field(default=12, ge=2, le=MAX_REGION_SIDE, strict=True)


def checked(run):
    if not workers.acquire(blocking=False):
        raise HTTPException(503, "Both illumination workers are busy. Retry after the current calculation finishes.")
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


@router.post("/point")
def compute_point(request: PointRequest):
    return checked(lambda: observer_analysis(request.site_id, request.projected_point(), [utc_datetime(request.utc)]))


@router.post("/series")
def compute_series(request: SeriesRequest):
    def run():
        times = epochs_with_end(utc_datetime(request.start_utc), utc_datetime(request.end_utc), request.step_seconds)
        return observer_analysis(request.site_id, request.projected_point(), times)
    return checked(run)


@router.post("/region")
def compute_region(request: RegionRequest):
    def run():
        times = [utc_datetime(value) for value in request.times_utc]
        if any(first >= second for first, second in zip(times, times[1:])):
            raise ValueError("Region times must be strictly increasing.")
        return region_analysis(request.site_id, request.projected_point(), request.side, times)
    return checked(run)
