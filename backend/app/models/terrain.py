"""Pydantic data models and schemas for Terrain Intelligence API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CoordinatesModel(BaseModel):
    easting_m: float = Field(..., description="Projected Easting in metres (Lunar South-Polar Stereographic)")
    northing_m: float = Field(..., description="Projected Northing in metres (Lunar South-Polar Stereographic)")
    coordinate_system: str = Field(default="Lunar South-Polar Stereographic")
    reference_frame: str = Field(default="MOON_ME associated with DE421 ephemeris")
    units: str = Field(default="metre")


class RoughnessSummaryModel(BaseModel):
    roughness_15m_m: Optional[float] = Field(None, description="Local elevation std dev at 15m scale (metres)")
    roughness_35m_m: Optional[float] = Field(None, description="Local elevation std dev at 35m scale (metres)")
    roughness_75m_m: Optional[float] = Field(None, description="Local elevation std dev at 75m scale (metres)")
    scale_classification: str = Field(default="provisional_analytical_scales")
    metric: str = Field(default="unbiased_sample_elevation_standard_deviation_ddof1")


class HazardClassificationModel(BaseModel):
    physical_hazard_class: str = Field(..., description="UNKNOWN, LOW, MODERATE, HIGH")
    physical_hazard_code: int = Field(..., description="0=UNKNOWN, 1=LOW, 2=MODERATE, 3=HIGH")
    epistemic_quality_class: str = Field(..., description="UNKNOWN, LOW, MODERATE, HIGH concern")
    epistemic_quality_code: int = Field(...)
    combined_screening_class: str = Field(..., description="UNKNOWN, LOW, MODERATE, HIGH")
    combined_screening_code: int = Field(...)
    policy: str = Field(default="Option B: Decoupled Decisional Screening")


class UncertaintyAndObservationModel(BaseModel):
    lola_observation_count: Optional[int] = Field(None, description="Direct LOLA laser shot count (ldec)")
    elevation_uncertainty_m_rms: Optional[float] = Field(None, description="Total vertical uncertainty RMS (toterr)")
    slope_uncertainty_deg_rms: Optional[float] = Field(None, description="Slope calculation uncertainty RMS (slperr)")
    is_interpolated: bool = Field(..., description="True if ldec == 0")
    is_direct_observation: bool = Field(..., description="True if ldec > 0")


class TerrainPointQueryRequest(BaseModel):
    easting_m: float = Field(..., description="Projected Easting coordinate in metres")
    northing_m: float = Field(..., description="Projected Northing coordinate in metres")


class TerrainPointQueryResponse(BaseModel):
    site_id: str
    coordinates: CoordinatesModel
    within_bounds: bool
    is_valid: bool
    error: Optional[str] = None
    raster_indices: Optional[Dict[str, int]] = None
    elevation_m: Optional[float] = None
    slope_deg: Optional[float] = None
    aspect_deg: Optional[float] = None
    aspect_description: Optional[str] = None
    roughness: Optional[RoughnessSummaryModel] = None
    hazard_classification: Optional[HazardClassificationModel] = None
    uncertainty_and_observation: Optional[UncertaintyAndObservationModel] = None
    provenance: Optional[Dict[str, Any]] = None


class TerrainHorizonRequest(BaseModel):
    observer_x: float = Field(..., description="Observer projected Easting coordinate in metres")
    observer_y: float = Field(..., description="Observer projected Northing coordinate in metres")
    azimuth_step_deg: float = Field(default=1.0, ge=0.1, le=360.0, description="Angular sampling interval in degrees")
    azimuths_deg: Optional[List[float]] = Field(default=None, description="Optional explicit list of azimuth angles (degrees clockwise from North)")
    observer_height_m: float = Field(default=2.0, ge=0.0, description="Observer sensor / instrument height above local ground in metres")
    max_range_m: float = Field(default=5000.0, gt=0.0, description="Maximum radial tracing distance in metres")
    sample_interval_m: float = Field(default=5.0, gt=0.0, description="Sampling distance increment along ray in metres")
    include_curvature: bool = Field(default=True, description="Account for lunar spherical curvature (R=1,737,400m)")


class TerrainHorizonResponse(BaseModel):
    status: str
    is_valid: bool
    message: Optional[str] = None
    site_id: Optional[str] = None
    observer_coordinates: Optional[Dict[str, Any]] = None
    observer_ground_elevation_m: Optional[float] = None
    observer_height_m: Optional[float] = None
    observer_eye_elevation_m: Optional[float] = None
    azimuth_convention: Optional[str] = None
    max_range_m: Optional[float] = None
    sample_interval_m: Optional[float] = None
    spherical_curvature_corrected: Optional[bool] = None
    lunar_radius_m: Optional[float] = None
    azimuths_deg: Optional[List[float]] = None
    horizon_angles_deg: Optional[List[float]] = None
    horizon_distances_m: Optional[List[float]] = None
    horizon_obstacle_elevations_m: Optional[List[float]] = None
    summary_statistics: Optional[Dict[str, Any]] = None
    scientific_limitations: Optional[List[str]] = None


class SiteSummaryResponse(BaseModel):
    site_id: str
    site_name: str
    region: str
    coordinate_system: Dict[str, Any]
    spatial_grid: Dict[str, Any]
    elevation_summary: Optional[Dict[str, Any]] = None
    slope_summary: Optional[Dict[str, Any]] = None
    roughness_summary: Optional[Dict[str, Any]] = None
    epistemic_quality_and_observation: Optional[Dict[str, Any]] = None
    hazard_screening_summary: Optional[Dict[str, Any]] = None
    data_provenance: Dict[str, Any]
    scientific_limitations: List[str]
