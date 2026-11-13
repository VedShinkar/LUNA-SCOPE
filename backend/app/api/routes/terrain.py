"""FastAPI route handlers for Terrain Intelligence API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.models.terrain import (
    SiteSummaryResponse,
    TerrainHorizonRequest,
    TerrainHorizonResponse,
    TerrainPointQueryRequest,
    TerrainPointQueryResponse,
)
from app.scientific_engines.terrain.service import TerrainService

router = APIRouter(prefix="/terrain", tags=["Terrain Intelligence"])


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
    if site_id != "Site04":
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not implemented. Only 'Site04' is supported.")

    service = TerrainService.get_instance()

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
    service = TerrainService.get_instance()
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
    service = TerrainService.get_instance()
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
    return res


@router.get(
    "/summary",
    response_model=SiteSummaryResponse,
    summary="Get full site summary, distributions, and provenance",
)
def get_site_summary_direct(site_id: str = Query(default="Site04")) -> Dict[str, Any]:
    """Direct site summary endpoint."""
    if site_id != "Site04":
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not implemented.")
    service = TerrainService.get_instance()
    return service.get_site_summary()
