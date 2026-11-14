"""FastAPI route handlers for Terrain Intelligence API."""
from __future__ import annotations

from math import isfinite
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from rasterio.errors import RasterioIOError

from app.models.terrain import (
    SiteSummaryResponse,
    TerrainHorizonRequest,
    TerrainHorizonResponse,
    TerrainPointQueryRequest,
    TerrainPointQueryResponse,
)
from app.scientific_engines.terrain.service import TerrainService
from app.scientific_engines.terrain.catalog import UnknownSiteError
from app.scientific_engines.terrain.explorer import load_explorer_grid
from app.scientific_engines.terrain.lunar_context import CACHE, PDS, RADIUS, SVS, elevation_profile, global_elevation, regional_grid, site04_context

router = APIRouter(prefix="/terrain", tags=["Terrain Intelligence"])


class LunarCoordinate(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class LunarProfileRequest(BaseModel):
    start: LunarCoordinate
    end: LunarCoordinate
    level: Literal["moon", "polar", "site04"]


@router.get("/explorer/context")
def get_lunar_context():
    try:
        site = site04_context()
    except (RasterioIOError, OSError):
        site = None
    return {
        "radius_m": RADIUS, "site04": site, "global_shape": [720, 1440],
        "global_resolution_deg": 0.25, "global_source_url": SVS, "polar_source_url": PDS,
        "imagery": (CACHE / "lroc_color_2k.jpg").is_file(),
    }


@router.get("/explorer/moon/albedo")
def get_lunar_albedo():
    path = CACHE / "lroc_color_2k.jpg"
    if not path.is_file():
        raise HTTPException(503, "Install the NASA lunar datasets to load the appearance map.")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/explorer/moon/elevation")
def get_lunar_elevation():
    try:
        return Response(global_elevation().tobytes(), media_type="application/octet-stream")
    except (RasterioIOError, OSError, ValueError) as error:
        raise HTTPException(503, "Install the NASA lunar datasets to load global LOLA elevation.") from error


@router.get("/explorer/polar")
def get_polar_grid(detail: Literal["overview", "approach"] = "overview"):
    try:
        return regional_grid(detail)
    except (RasterioIOError, OSError, ValueError) as error:
        raise HTTPException(503, "The PDS polar elevation grid is unavailable.") from error


@router.post("/explorer/profile")
def get_lunar_profile(request: LunarProfileRequest):
    try:
        return elevation_profile(
            (request.start.longitude, request.start.latitude),
            (request.end.longitude, request.end.latitude),
            request.level,
        )
    except (RasterioIOError, OSError, ValueError) as error:
        raise HTTPException(503, "The selected elevation source is unavailable.") from error


@router.get("/explorer/grid", summary="Get bounded Site04 mesh samples and aligned science layers")
def get_explorer_grid(
    max_dimension: int = Query(default=256, ge=2, le=384),
    easting_m: float | None = Query(default=None, allow_inf_nan=False),
    northing_m: float | None = Query(default=None, allow_inf_nan=False),
) -> Dict[str, Any]:
    if (easting_m is None) != (northing_m is None):
        raise HTTPException(422, "Supply both coordinates for a native inspection window.")
    centre = None if easting_m is None else (easting_m, northing_m)
    try:
        return load_explorer_grid(max_dimension, centre=centre)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RasterioIOError as error:
        raise HTTPException(status_code=503, detail="The processed Site04 grid could not be loaded.") from error


@router.get(
    "/site",
    summary="Get terrain metadata and analysis for a site or location",
    description=(
        "Conforms to docs/API_CONTRACTS.md GET /terrain/site. "
        "Returns site summary metadata, or point-level terrain analysis if easting_m and northing_m are supplied."
    ),
)
def get_terrain_site(
    site_id: str = Query(default="Site04", description="Landing site identifier"),
    easting_m: Optional[float] = Query(default=None, description="Projected Easting in metres"),
    northing_m: Optional[float] = Query(default=None, description="Projected Northing in metres"),
    include: Optional[List[str]] = Query(default=None, description="Optional include list (e.g. elevation, slope, roughness, horizon)"),
) -> Dict[str, Any]:
    """Retrieve site summary or localized terrain query according to API contracts."""
    service = _site_service(site_id)
    if (easting_m is None) != (northing_m is None):
        raise HTTPException(422, "Supply both easting_m and northing_m.")

    # If coordinates are provided, perform point query
    if easting_m is not None and northing_m is not None:
        point_data = service.query_point(easting_m=easting_m, northing_m=northing_m)
        if not point_data.get("is_valid", False):
            raise HTTPException(status_code=400, detail=point_data.get("error", "Invalid terrain query"))
        return point_data

    # Otherwise return site-level summary
    return service.get_site_summary()


@router.post(
    "/point",
    response_model=TerrainPointQueryResponse,
    summary="Query terrain attributes at projected lunar coordinates",
    description="Returns elevation, slope, aspect, multi-scale roughness, physical hazard, epistemic quality, and uncertainties.",
)
def query_terrain_point(req: TerrainPointQueryRequest) -> Dict[str, Any]:
    """Query terrain properties at given coordinates."""
    service = _site_service(req.site_id)
    res = service.query_point(easting_m=req.easting_m, northing_m=req.northing_m)
    return res


@router.post(
    "/horizon",
    response_model=TerrainHorizonResponse,
    summary="Calculate 360-degree local terrain-horizon obstruction profile",
    description="Traces rays along the DEM to calculate maximum obstacle elevation angle versus azimuth.",
)
def query_terrain_horizon(req: TerrainHorizonRequest) -> Dict[str, Any]:
    """Compute local terrain-horizon profile."""
    service = _site_service(req.site_id)
    res = service.query_horizon(
        observer_x=req.observer_x,
        observer_y=req.observer_y,
        azimuth_step_deg=req.azimuth_step_deg,
        azimuths_deg=req.azimuths_deg,
        observer_height_m=req.observer_height_m,
        max_range_m=req.max_range_m,
        sample_interval_m=req.sample_interval_m,
        include_curvature=req.include_curvature,
    )
    if not res.get("is_valid", False):
        raise HTTPException(status_code=400, detail=res.get("message", "Horizon calculation failed"))
    # The engine uses NaN for invalid rays. Preserve their positions as JSON null.
    for field in ("horizon_angles_deg", "horizon_distances_m", "horizon_obstacle_elevations_m"):
        res[field] = [value if isfinite(value) else None for value in res[field]]
    return res


@router.get(
    "/summary",
    response_model=SiteSummaryResponse,
    summary="Get full site summary, distributions, and provenance",
)
def get_site_summary_direct(site_id: str = Query(default="Site04")) -> Dict[str, Any]:
    """Direct site summary endpoint."""
    service = _site_service(site_id)
    return service.get_site_summary()


def _site_service(site_id: str) -> TerrainService:
    try:
        service = TerrainService.get_instance(site_id)
        service._ensure_loaded()
        return service
    except UnknownSiteError as error:
        raise HTTPException(404, str(error)) from error
    except (OSError, ValueError, RasterioIOError) as error:
        raise HTTPException(503, f"Terrain dataset unavailable for {site_id}: {error}") from error
