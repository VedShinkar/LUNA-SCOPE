"""Mission timeline, profile validation, matched comparison, and inspection."""
from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.routes.celestial import TerrainPoint
from app.models.mission_timeline import Comparison, Inspection, MissionProfile, Timeline
from app.scientific_engines import mission_service as service
from app.scientific_engines.ephemeris.geometry import MAX_STEP_S, MIN_STEP_S, utc_datetime
from app.scientific_engines.ephemeris.kernels import KernelUnavailable
from app.scientific_engines.ephemeris.observer import ObserverUnavailable
from app.scientific_engines.terrain.catalog import UnknownSiteError, list_site_ids

router = APIRouter(prefix="/terrain/explorer/mission-timeline", tags=["Mission Timeline"])
workers = BoundedSemaphore(2)


class RangeRequest(BaseModel):
    start_utc: str
    end_utc: str
    step_seconds: int = Field(default=3600, ge=MIN_STEP_S, le=MAX_STEP_S, strict=True)
    profile: MissionProfile = Field(default_factory=MissionProfile)
    refine_transitions: bool = True


class SiteRequest(RangeRequest):
    site_id: str
    point: TerrainPoint | None = None

    def selection(self):
        return self.site_id, (self.point.easting_m,self.point.northing_m) if self.point else None


class ComparisonRequest(RangeRequest):
    points: dict[str,TerrainPoint] = Field(default_factory=dict, max_length=3)


class InspectionRequest(SiteRequest):
    inspect_utc: str


def run(request, sites):
    return service.timelines(sites,utc_datetime(request.start_utc),utc_datetime(request.end_utc),request.step_seconds,
                             request.profile,request.refine_transitions)


def checked(call):
    if not workers.acquire(blocking=False):
        raise HTTPException(503,"Mission timeline workers are busy. Retry after the current calculation finishes.")
    try:
        return call()
    except UnknownSiteError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (KernelUnavailable,ObserverUnavailable) as exc:
        raise HTTPException(503,str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    finally:
        workers.release()


@router.get("/profile", response_model=MissionProfile)
def demonstration_profile():
    return MissionProfile()


@router.post("/profile", response_model=MissionProfile)
def validate_profile(profile: MissionProfile):
    return profile


@router.post("/site", response_model=Timeline)
def site(request: SiteRequest):
    return checked(lambda: run(request,[request.selection()])[0])


@router.post("/refine", response_model=Timeline)
def refine(request: SiteRequest):
    refined = request.model_copy(update={"refine_transitions":True})
    return checked(lambda: run(refined,[refined.selection()])[0])


@router.post("/compare", response_model=Comparison)
def compare(request: ComparisonRequest):
    def calculate():
        sites = list_site_ids()
        if request.points.keys()-set(sites):
            raise ValueError("Comparison point keys must identify supported landing sites.")
        selections = [(site,(point.easting_m,point.northing_m) if (point := request.points.get(site)) else None) for site in sites]
        results = run(request,selections)
        return {"start_utc":results[0]["start_utc"],"end_utc":results[0]["end_utc"],"step_seconds":request.step_seconds,
                "profile":request.profile,"timelines":results}
    return checked(calculate)


@router.post("/inspect", response_model=Inspection)
def inspect(request: InspectionRequest):
    return checked(lambda: service.inspect(run(request,[request.selection()])[0],utc_datetime(request.inspect_utc)))
