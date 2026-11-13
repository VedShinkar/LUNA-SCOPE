"""Aspect (downslope azimuth) calculation and orientation verification.

Phase 2 Aspect module:
- Derives terrain aspect from elevation derivatives (dz/dx, dz/dy).
- Strict, documented cartographic azimuth convention:
  * Measured in degrees clockwise from grid North (+Y Northing axis).
  * 0 deg = North, 90 deg = East, 180 deg = South, 270 deg = West.
- Explicitly handles flat terrain (assigning documented sentinel FLAT_ASPECT = -1.0).
- Preserves NoData / NaNs.
- Provides synthetic planar surface generators for orientation verification.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
from rasterio.transform import Affine

from app.scientific_engines.terrain.slope import (
    SlopeMethod,
    _compute_map_gradients,
)

FLAT_ASPECT_SENTINEL = -1.0
DEFAULT_FLAT_SLOPE_THRESHOLD_DEG = 0.01  # Slopes below ~0.01 deg considered flat


def calculate_aspect(
    dem: np.ndarray,
    transform: Affine | Tuple[float, float, float, float, float, float],
    method: SlopeMethod = "zevenbergen_thorne",
    flat_threshold_deg: float = DEFAULT_FLAT_SLOPE_THRESHOLD_DEG,
) -> np.ndarray:
    """Calculate aspect (steepest downslope azimuth) in degrees.

    Azimuth Convention:
        Degrees clockwise from grid North (+Y Northing axis):
        - North:      0 deg (or 360 deg)
        - North-East: 45 deg
        - East:       90 deg
        - South-East: 135 deg
        - South:      180 deg
        - South-West: 225 deg
        - West:       270 deg
        - North-West: 315 deg

    Mathematical Formulation:
        Let downslope vector components be:
            u = -dz/dx  (Eastward component of steepest descent)
            v = -dz/dy  (Northward component of steepest descent)
        The clockwise angle from North (+Y) is:
            azimuth_rad = arctan2(u, v)
            aspect_deg = (degrees(azimuth_rad) + 360) % 360

    Flat Terrain Handling:
        Cells with slope < flat_threshold_deg have no well-defined downslope direction.
        These cells are assigned FLAT_ASPECT_SENTINEL = -1.0.

    NoData Handling:
        Cells with NaN elevation or NaN gradient are preserved as NaN.

    Args:
        dem: 2D array of elevations in metres.
        transform: Affine transform mapping raster coordinates to map coordinates.
        method: "zevenbergen_thorne" or "horn".
        flat_threshold_deg: Slope magnitude below which terrain is classified flat.

    Returns:
        2D array of aspect in degrees [0, 360), with -1.0 for flat cells and NaN for NoData.
    """
    dz_dx, dz_dy = _compute_map_gradients(dem, transform, method, edge_mode="gradient")

    grad_mag = np.hypot(dz_dx, dz_dy)
    slope_deg = np.degrees(np.arctan(grad_mag))

    # Downslope vector components
    u = -dz_dx  # Eastward downslope
    v = -dz_dy  # Northward downslope

    # Angle clockwise from North (+Y)
    aspect_rad = np.arctan2(u, v)
    aspect_deg = (np.degrees(aspect_rad) + 360.0) % 360.0

    # Normalize 360.0 to 0.0, including values rounded up during the cast.
    aspect_deg = aspect_deg.astype(np.float32)
    aspect_deg = np.where(aspect_deg >= 360.0, 0.0, aspect_deg)

    # Apply flat mask
    flat_mask = np.isfinite(slope_deg) & (slope_deg < flat_threshold_deg)
    aspect_deg = np.where(flat_mask, FLAT_ASPECT_SENTINEL, aspect_deg)

    # Preserve NaNs
    nan_mask = ~np.isfinite(dz_dx) | ~np.isfinite(dz_dy)
    aspect_deg = np.where(nan_mask, np.nan, aspect_deg)

    return aspect_deg


def summarize_aspect(
    aspect: np.ndarray,
    flat_sentinel: float = FLAT_ASPECT_SENTINEL,
) -> Dict[str, Any]:
    """Calculate descriptive statistics and cardinal distribution of aspect.

    Breaks down aspect into eight 45-degree cardinal/intercardinal sectors,
    alongside flat and NoData counts.
    """
    total = int(aspect.size)
    nan_count = int(np.isnan(aspect).sum())
    flat_count = int((aspect == flat_sentinel).sum())
    sloped_count = total - nan_count - flat_count

    sloped_mask = np.isfinite(aspect) & (aspect != flat_sentinel)

    sectors = {
        "North (337.5-22.5 deg)": 0,
        "North-East (22.5-67.5 deg)": 0,
        "East (67.5-112.5 deg)": 0,
        "South-East (112.5-157.5 deg)": 0,
        "South (157.5-202.5 deg)": 0,
        "South-West (202.5-247.5 deg)": 0,
        "West (247.5-292.5 deg)": 0,
        "North-West (292.5-337.5 deg)": 0,
    }

    if sloped_count > 0:
        a_vals = aspect[sloped_mask]
        sectors["North (337.5-22.5 deg)"] = int(((a_vals >= 337.5) | (a_vals < 22.5)).sum())
        sectors["North-East (22.5-67.5 deg)"] = int(((a_vals >= 22.5) & (a_vals < 67.5)).sum())
        sectors["East (67.5-112.5 deg)"] = int(((a_vals >= 67.5) & (a_vals < 112.5)).sum())
        sectors["South-East (112.5-157.5 deg)"] = int(((a_vals >= 112.5) & (a_vals < 157.5)).sum())
        sectors["South (157.5-202.5 deg)"] = int(((a_vals >= 157.5) & (a_vals < 202.5)).sum())
        sectors["South-West (202.5-247.5 deg)"] = int(((a_vals >= 202.5) & (a_vals < 247.5)).sum())
        sectors["West (247.5-292.5 deg)"] = int(((a_vals >= 247.5) & (a_vals < 292.5)).sum())
        sectors["North-West (292.5-337.5 deg)"] = int(((a_vals >= 292.5) & (a_vals < 337.5)).sum())

    sector_percentages = {
        k: round(float(v / sloped_count * 100.0), 2) if sloped_count > 0 else 0.0
        for k, v in sectors.items()
    }

    return {
        "total_pixels": total,
        "sloped_pixels": sloped_count,
        "flat_pixels": flat_count,
        "flat_percentage": round(float(flat_count / total * 100.0), 4),
        "nodata_pixels": nan_count,
        "azimuth_convention": (
            "Degrees clockwise from grid North (+Y Northing axis): "
            "0=N, 90=E, 180=S, 270=W. Flat terrain coded as -1.0."
        ),
        "cardinal_distribution_counts": sectors,
        "cardinal_distribution_percentages": sector_percentages,
    }


def create_synthetic_planar_dem(
    shape: Tuple[int, int] = (100, 100),
    dx: float = 5.0,
    dy: float = 5.0,
    slope_deg: float = 10.0,
    aspect_deg: float = 0.0,
    base_elevation: float = 1000.0,
) -> np.ndarray:
    """Generate an analytical tilted planar DEM for aspect/slope verification.

    Args:
        shape: (rows, cols)
        dx, dy: Pixel sizes in metres.
        slope_deg: Surface slope in degrees.
        aspect_deg: Desired aspect (downslope azimuth in degrees clockwise from North).
        base_elevation: Elevation at array origin.

    Returns:
        2D synthetic planar DEM array.
    """
    rows, cols = shape
    j_coords = np.arange(cols) * dx  # X coords (Easting)
    i_coords = np.arange(rows) * dy  # Y coords from top down: actual Y = y_max - i * dy

    # Matrix coordinates: X = x, Y = (rows - 1 - i) * dy (North-up)
    X, I = np.meshgrid(j_coords, np.arange(rows))
    Y = (rows - 1 - I) * dy

    # Downslope vector in direction aspect_deg:
    # aspect_deg = 0 (North) -> terrain descends towards +Y, so dz/dy < 0
    # aspect_deg = 90 (East) -> terrain descends towards +X, so dz/dx < 0
    rad_slope = np.radians(slope_deg)
    tan_slope = np.tan(rad_slope)

    # Unit downslope vector: u = sin(aspect), v = cos(aspect)
    # Upslope gradient is -downslope: dz/dx = -tan_slope * sin(aspect), dz/dy = -tan_slope * cos(aspect)
    aspect_rad = np.radians(aspect_deg)
    dz_dx = -tan_slope * np.sin(aspect_rad)
    dz_dy = -tan_slope * np.cos(aspect_rad)

    Z = base_elevation + dz_dx * X + dz_dy * Y
    return Z.astype(np.float32)
