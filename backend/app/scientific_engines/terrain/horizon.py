"""Local terrain horizon profile computation engine for lunar landing sites.

Phase 4 Horizon module:
- Traces rays radially from an observer location across a lunar DEM.
- Derives terrain obstruction / horizon elevation angles versus azimuth.
- Uses strict cartographic azimuth convention (degrees clockwise from grid North, +Y Northing).
- Accounts for optional lunar spherical body curvature (radius = 1,737,400 m).
- Explicitly handles NoData, grid boundaries, and insufficient raster coverage.
- Strictly separates geometric terrain obstruction from solar or celestial visibility.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from rasterio.transform import Affine

from app.scientific_engines.terrain.slope import extract_pixel_spacing_from_transform

LUNAR_RADIUS_M = 1737400.0  # IAU/IAG spherical lunar reference radius in metres
DEFAULT_OBSERVER_HEIGHT_M = 2.0  # Default observer mast / sensor height above terrain in metres
DEFAULT_SAMPLE_INTERVAL_M = 5.0  # Default ray stepping interval in metres (matches native DEM)
DEFAULT_MAX_RANGE_M = 5000.0     # Default radial horizon search distance in metres


def world_to_pixel(
    x: float,
    y: float,
    transform: Affine | Tuple[float, float, float, float, float, float],
) -> Tuple[float, float]:
    """Convert world projected coordinates (Easting, Northing) to continuous (col, row).

    Args:
        x: Easting in metres.
        y: Northing in metres.
        transform: Affine transform (a, b, c, d, e, f).

    Returns:
        (col, row) continuous float coordinates.
    """
    if isinstance(transform, Affine):
        t = transform
    else:
        t = Affine(*transform[:6])

    # Invert transform: (col, row) = ~t * (x, y)
    inv_t = ~t
    col, row = inv_t @ (x, y)
    return float(col), float(row)


def pixel_to_world(
    col: float,
    row: float,
    transform: Affine | Tuple[float, float, float, float, float, float],
) -> Tuple[float, float]:
    """Convert raster (col, row) coordinates to world projected (Easting, Northing).

    Args:
        col: Column coordinate.
        row: Row coordinate.
        transform: Affine transform.

    Returns:
        (x, y) world coordinates in metres.
    """
    if isinstance(transform, Affine):
        t = transform
    else:
        t = Affine(*transform[:6])

    x, y = t * (col, row)
    return float(x), float(y)


def sample_dem_bilinear(
    dem: np.ndarray,
    col: float,
    row: float,
) -> float:
    """Sample DEM at continuous (col, row) using bilinear interpolation.

    Returns:
        Interpolated elevation in metres, or NaN if out of bounds or on NoData.
    """
    h, w = dem.shape
    if col < 0.0 or col > (w - 1) or row < 0.0 or row > (h - 1):
        return float(np.nan)

    c0 = int(np.floor(col))
    r0 = int(np.floor(row))
    c1 = min(c0 + 1, w - 1)
    r1 = min(r0 + 1, h - 1)

    dc = col - c0
    dr = row - r0

    v00 = dem[r0, c0]
    v01 = dem[r0, c1]
    v10 = dem[r1, c0]
    v11 = dem[r1, c1]

    # If all four corner points are finite, compute bilinear
    if np.isfinite(v00) and np.isfinite(v01) and np.isfinite(v10) and np.isfinite(v11):
        top = v00 * (1.0 - dc) + v01 * dc
        bottom = v10 * (1.0 - dc) + v11 * dc
        return float(top * (1.0 - dr) + bottom * dr)

    # If near boundary or partial NaN, fallback to nearest valid neighbor
    nearest_val = dem[int(round(row)), int(round(col))]
    if np.isfinite(nearest_val):
        return float(nearest_val)

    return float(np.nan)


def calculate_horizon_ray(
    dem: np.ndarray,
    transform: Affine | Tuple[float, float, float, float, float, float],
    observer_x: float,
    observer_y: float,
    azimuth_deg: float,
    observer_height_m: float = DEFAULT_OBSERVER_HEIGHT_M,
    max_range_m: float = DEFAULT_MAX_RANGE_M,
    sample_interval_m: float = DEFAULT_SAMPLE_INTERVAL_M,
    include_curvature: bool = True,
    lunar_radius_m: float = LUNAR_RADIUS_M,
) -> Dict[str, Any]:
    """Trace a single radial ray from observer and determine horizon obstruction.

    Azimuth Convention:
        Degrees clockwise from grid North (+Y Northing axis):
        0 deg = North (+Y), 90 deg = East (+X), 180 deg = South (-Y), 270 deg = West (-X).

    Obstruction Calculation:
        At radial distance d along ray:
            x(d) = x_obs + d * sin(azimuth)
            y(d) = y_obs + d * cos(azimuth)
            z_target = dem(x(d), y(d))
            delta_z_curv = (d^2) / (2 * R_moon) if include_curvature else 0.0
            z_eff = z_target - delta_z_curv
            angle(d) = arctan((z_eff - (z_obs_ground + h_obs)) / d)
        The horizon elevation angle is max(angle(d)).

    Returns:
        Dictionary containing:
            - azimuth_deg
            - horizon_elevation_deg: maximum obstruction angle in degrees
            - horizon_distance_m: distance to the limiting obstruction point in metres
            - horizon_elevation_m: elevation of limiting obstacle point in metres
            - valid_ray: bool
            - samples_evaluated: int
            - ray_exit_reason: 'max_range_reached' | 'raster_boundary_exited' | 'nodata_encountered'
    """
    obs_col, obs_row = world_to_pixel(observer_x, observer_y, transform)
    h, w = dem.shape

    # Check observer location
    if obs_col < 0 or obs_col >= w or obs_row < 0 or obs_row >= h:
        return {
            "azimuth_deg": round(float(azimuth_deg), 2),
            "horizon_elevation_deg": float(np.nan),
            "horizon_distance_m": float(np.nan),
            "horizon_elevation_m": float(np.nan),
            "valid_ray": False,
            "samples_evaluated": 0,
            "ray_exit_reason": "observer_out_of_bounds",
        }

    z_obs_ground = sample_dem_bilinear(dem, obs_col, obs_row)
    if not np.isfinite(z_obs_ground):
        return {
            "azimuth_deg": round(float(azimuth_deg), 2),
            "horizon_elevation_deg": float(np.nan),
            "horizon_distance_m": float(np.nan),
            "horizon_elevation_m": float(np.nan),
            "valid_ray": False,
            "samples_evaluated": 0,
            "ray_exit_reason": "observer_in_nodata",
        }

    z_eye = z_obs_ground + max(0.0, float(observer_height_m))

    az_rad = np.radians(float(azimuth_deg))
    sin_az = np.sin(az_rad)
    cos_az = np.cos(az_rad)

    # Ray stepping distances
    distances = np.arange(sample_interval_m, max_range_m + sample_interval_m * 0.5, sample_interval_m)
    if len(distances) == 0:
        distances = np.array([sample_interval_m])

    max_angle_rad = -np.pi / 2.0  # -90 degrees
    horizon_dist = float(distances[0])
    horizon_elev = float(z_obs_ground)
    samples_count = 0
    exit_reason = "max_range_reached"

    for d in distances:
        rx = observer_x + d * sin_az
        ry = observer_y + d * cos_az

        c, r = world_to_pixel(rx, ry, transform)
        if c < 0.0 or c >= w or r < 0.0 or r >= h:
            exit_reason = "raster_boundary_exited"
            break

        z_pt = sample_dem_bilinear(dem, c, r)
        if not np.isfinite(z_pt):
            # Encountered NoData along ray
            continue

        samples_count += 1

        # Lunar spherical curvature drop
        if include_curvature and lunar_radius_m > 0.0:
            curv_drop = (d * d) / (2.0 * lunar_radius_m)
        else:
            curv_drop = 0.0

        z_eff = z_pt - curv_drop
        angle_rad = np.arctan2(z_eff - z_eye, d)

        if angle_rad > max_angle_rad:
            max_angle_rad = angle_rad
            horizon_dist = float(d)
            horizon_elev = float(z_pt)

    if samples_count == 0:
        return {
            "azimuth_deg": round(float(azimuth_deg), 2),
            "horizon_elevation_deg": float(np.nan),
            "horizon_distance_m": float(np.nan),
            "horizon_elevation_m": float(np.nan),
            "valid_ray": False,
            "samples_evaluated": 0,
            "ray_exit_reason": "no_valid_samples_along_ray",
        }

    return {
        "azimuth_deg": round(float(azimuth_deg), 2),
        "horizon_elevation_deg": round(float(np.degrees(max_angle_rad)), 4),
        "horizon_distance_m": round(horizon_dist, 2),
        "horizon_elevation_m": round(horizon_elev, 2),
        "valid_ray": True,
        "samples_evaluated": samples_count,
        "ray_exit_reason": exit_reason,
    }


def compute_terrain_horizon_profile(
    dem: np.ndarray,
    transform: Affine | Tuple[float, float, float, float, float, float],
    observer_x: float,
    observer_y: float,
    azimuth_step_deg: float = 1.0,
    azimuths_deg: Optional[List[float]] = None,
    observer_height_m: float = DEFAULT_OBSERVER_HEIGHT_M,
    max_range_m: float = DEFAULT_MAX_RANGE_M,
    sample_interval_m: float = DEFAULT_SAMPLE_INTERVAL_M,
    include_curvature: bool = True,
    lunar_radius_m: float = LUNAR_RADIUS_M,
) -> Dict[str, Any]:
    """Compute 360-degree radial local terrain-horizon profile.

    Args:
        dem: 2D elevation array in metres.
        transform: Affine transform.
        observer_x: Easting in metres (Lunar South-Polar Stereographic).
        observer_y: Northing in metres (Lunar South-Polar Stereographic).
        azimuth_step_deg: Angular sampling step in degrees (default 1.0 deg).
        azimuths_deg: Optional explicit list of azimuth angles to sample.
        observer_height_m: Instrument height above local ground in metres.
        max_range_m: Maximum radial tracing range in metres.
        sample_interval_m: Distance increment along each ray in metres.
        include_curvature: Account for lunar spherical curvature.
        lunar_radius_m: Lunar spherical radius in metres (1,737,400 m).

    Returns:
        Structured dictionary conforming to API contracts:
            - observer_coordinates: [x, y]
            - observer_ground_elevation_m: float
            - observer_eye_elevation_m: float
            - observer_height_m: float
            - azimuth_convention: documented standard
            - horizon_angles_deg: List[float]
            - horizon_distances_m: List[float]
            - horizon_obstacle_elevations_m: List[float]
            - azimuths_deg: List[float]
            - summary_statistics: min, max, mean, median horizon elevation angle
            - profile_points: List[dict]
            - scientific_limitations: list of caveats
    """
    if azimuths_deg is None:
        if azimuth_step_deg <= 0.0 or azimuth_step_deg > 360.0:
            raise ValueError(f"azimuth_step_deg must be in (0, 360], got {azimuth_step_deg}")
        azimuths_list = list(np.arange(0.0, 360.0, azimuth_step_deg))
    else:
        azimuths_list = [float(a) % 360.0 for a in azimuths_deg]

    obs_col, obs_row = world_to_pixel(observer_x, observer_y, transform)
    h, w = dem.shape

    if obs_col < 0 or obs_col >= w or obs_row < 0 or obs_row >= h:
        return {
            "status": "ERROR_OUT_OF_BOUNDS",
            "message": f"Observer coordinate ({observer_x}, {observer_y}) is outside the raster extent.",
            "observer_coordinates": [float(observer_x), float(observer_y)],
            "is_valid": False,
        }

    z_ground = sample_dem_bilinear(dem, obs_col, obs_row)
    if not np.isfinite(z_ground):
        return {
            "status": "ERROR_NODATA",
            "message": f"Observer coordinate ({observer_x}, {observer_y}) falls on a NoData cell.",
            "observer_coordinates": [float(observer_x), float(observer_y)],
            "is_valid": False,
        }

    profile_points: List[Dict[str, Any]] = []
    horizon_angles: List[float] = []
    horizon_distances: List[float] = []
    horizon_elevations: List[float] = []
    az_output: List[float] = []

    for az in azimuths_list:
        ray_res = calculate_horizon_ray(
            dem=dem,
            transform=transform,
            observer_x=observer_x,
            observer_y=observer_y,
            azimuth_deg=az,
            observer_height_m=observer_height_m,
            max_range_m=max_range_m,
            sample_interval_m=sample_interval_m,
            include_curvature=include_curvature,
            lunar_radius_m=lunar_radius_m,
        )
        profile_points.append(ray_res)
        az_output.append(round(float(az), 2))
        horizon_angles.append(ray_res["horizon_elevation_deg"])
        horizon_distances.append(ray_res["horizon_distance_m"])
        horizon_elevations.append(ray_res["horizon_elevation_m"])

    valid_angles = [a for a in horizon_angles if np.isfinite(a)]
    if len(valid_angles) > 0:
        summary_stats = {
            "min_elevation_angle_deg": round(float(np.min(valid_angles)), 4),
            "max_elevation_angle_deg": round(float(np.max(valid_angles)), 4),
            "mean_elevation_angle_deg": round(float(np.mean(valid_angles)), 4),
            "median_elevation_angle_deg": round(float(np.median(valid_angles)), 4),
            "valid_azimuth_count": len(valid_angles),
            "total_azimuth_count": len(azimuths_list),
        }
    else:
        summary_stats = {
            "min_elevation_angle_deg": None,
            "max_elevation_angle_deg": None,
            "mean_elevation_angle_deg": None,
            "median_elevation_angle_deg": None,
            "valid_azimuth_count": 0,
            "total_azimuth_count": len(azimuths_list),
        }

    return {
        "status": "SUCCESS",
        "is_valid": True,
        "site_id": "Site04",
        "observer_coordinates": {
            "easting_m": float(observer_x),
            "northing_m": float(observer_y),
            "coordinate_system": "Lunar South-Polar Stereographic",
            "reference_frame": "MOON_ME associated with DE421 ephemeris",
        },
        "observer_ground_elevation_m": round(float(z_ground), 3),
        "observer_height_m": float(observer_height_m),
        "observer_eye_elevation_m": round(float(z_ground + observer_height_m), 3),
        "azimuth_convention": (
            "Degrees clockwise from grid North (+Y Northing axis): "
            "0=North, 90=East, 180=South, 270=West. "
            "Elevation angle in degrees above local horizontal tangent plane."
        ),
        "max_range_m": float(max_range_m),
        "sample_interval_m": float(sample_interval_m),
        "spherical_curvature_corrected": bool(include_curvature),
        "lunar_radius_m": float(lunar_radius_m) if include_curvature else None,
        "azimuths_deg": az_output,
        "horizon_angles_deg": horizon_angles,
        "horizon_distances_m": horizon_distances,
        "horizon_obstacle_elevations_m": horizon_elevations,
        "summary_statistics": summary_stats,
        "profile_points": profile_points,
        "scientific_limitations": [
            "This interface computes geometric terrain obstruction angles from the 5m LOLA DEM.",
            "This is NOT a solar or Earth visibility calculation; ephemeris and celestial body angular diameter belongs to the celestial module.",
            "Obstructions beyond max_range_m or outside the DEM bounding box are truncated at raster boundaries.",
            "Sub-pixel micro-topography (< 5 m) and boulders are unresolved by the DEM.",
        ],
    }
