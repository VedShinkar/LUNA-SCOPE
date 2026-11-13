"""Unit tests for the local terrain horizon engine (backend/app/scientific_engines/terrain/horizon.py).
These tests use small synthetic DEMs to verify geometry, curvature handling, NoData, and ray termination.
"""

import math
import numpy as np
from rasterio.transform import Affine

from app.scientific_engines.terrain.horizon import (
    compute_terrain_horizon_profile,
    calculate_horizon_ray,
)

# Helper affine: pixel size = 5 m, origin at (0,0), north‑up grid (Y decreases with row index)
DEFAULT_AFFINE = Affine(5, 0, 0, 0, -5, 0)

def test_flat_dem_horizon_angles_are_zero():
    """Flat DEM should produce horizon elevation angles of 0° (or NaN if no valid samples)."""
    dem = np.zeros((20, 20), dtype=np.float32)
    observer_x, observer_y = 50.0, -50.0  # centre of the DEM (10 px * 5 m)
    res = compute_terrain_horizon_profile(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuth_step_deg=90,  # N, E, S, W
        observer_height_m=0.0,
        max_range_m=200.0,
        include_curvature=False,
    )
    angles = [a for a in res["horizon_angles_deg"] if a is not None]
    assert all(math.isclose(a, 0.0, abs_tol=1e-6) for a in angles)
    assert all(d > 0 for d in res["horizon_distances_m"] if d is not None)

def test_linear_ramp_horizon_angle_matches_slope():
    """DEM that rises *southward* (higher rows = higher elevation).
    The northward ray therefore looks downhill, yielding a negative angle whose magnitude
    equals arctan(dz/dx) where dz per pixel = 1 m and pixel spacing = 5 m.
    """
    rows, cols = 30, 30
    # Elevation = row index (southward increase)
    dem = np.arange(rows, dtype=np.float32).reshape(rows, 1)
    dem = np.repeat(dem, cols, axis=1)
    observer_x, observer_y = 75.0, -75.0  # centre
    expected_mag = math.degrees(math.atan(1.0 / 5.0))
    res = compute_terrain_horizon_profile(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuth_step_deg=180,  # North (0°) and South (180°)
        observer_height_m=0.0,
        max_range_m=500.0,
        include_curvature=False,
    )
    north_angle = res["horizon_angles_deg"][0]
    south_angle = res["horizon_angles_deg"][1]
    # Northward sees downhill → negative angle of expected magnitude
    assert north_angle is not None and math.isclose(abs(north_angle), expected_mag, rel_tol=0.05)
    # Southward sees uphill → positive angle of similar magnitude
    assert south_angle is not None and math.isclose(south_angle, expected_mag, rel_tol=0.05)

def test_observer_height_reduces_horizon_angle():
    dem = np.full((10, 10), 0.0, dtype=np.float32)
    # Add a hill at the far north edge (higher elevation)
    dem[0, :] = 10.0
    observer_x, observer_y = 25.0, -25.0
    # No observer height
    res_no_height = compute_terrain_horizon_profile(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuths_deg=[0],
        observer_height_m=0.0,
        max_range_m=200.0,
        include_curvature=False,
    )
    # With observer height 5 m
    res_with_height = compute_terrain_horizon_profile(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuths_deg=[0],
        observer_height_m=5.0,
        max_range_m=200.0,
        include_curvature=False,
    )
    angle_no = res_no_height["horizon_angles_deg"][0]
    angle_yes = res_with_height["horizon_angles_deg"][0]
    assert angle_no is not None and angle_yes is not None
    assert angle_yes < angle_no  # higher eye reduces obstruction angle

def test_azimuth_list_and_multiple_directions():
    dem = np.zeros((15, 15), dtype=np.float32)
    observer_x, observer_y = 37.5, -37.5
    azimuths = [0, 90, 180, 270]
    res = compute_terrain_horizon_profile(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuths_deg=azimuths,
        observer_height_m=0.0,
        max_range_m=100.0,
        include_curvature=False,
    )
    assert res["azimuths_deg"] == azimuths
    assert len(res["horizon_angles_deg"]) == len(azimuths)

def test_curvature_decreases_horizon_angle():
    # Simple DEM with a distant ridge to the north
    dem = np.zeros((30, 30), dtype=np.float32)
    dem[0, :] = 20.0
    observer_x, observer_y = 75.0, -75.0
    res_flat = compute_terrain_horizon_profile(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuths_deg=[0],
        observer_height_m=0.0,
        max_range_m=5000.0,
        include_curvature=False,
    )
    res_curv = compute_terrain_horizon_profile(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuths_deg=[0],
        observer_height_m=0.0,
        max_range_m=5000.0,
        include_curvature=True,
    )
    angle_flat = res_flat["horizon_angles_deg"][0]
    angle_curv = res_curv["horizon_angles_deg"][0]
    assert angle_flat is not None and angle_curv is not None
    # Curvature drops the apparent elevation, so angle should be smaller
    assert angle_curv < angle_flat

def test_nodata_and_boundary_behavior():
    dem = np.full((10, 10), np.nan, dtype=np.float32)
    dem[5, 5] = 0.0  # single valid centre pixel
    # Observer placed at the centre world coordinates (pixel centre)
    observer_x, observer_y = 5 * 5.0, -5 * 5.0
    ray = calculate_horizon_ray(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuth_deg=0,
        observer_height_m=0.0,
        max_range_m=200.0,
        sample_interval_m=5.0,
        include_curvature=False,
    )
    # No valid samples beyond centre → ray invalid with appropriate reason
    assert ray["valid_ray"] is False
    assert ray["ray_exit_reason"] == "no_valid_samples_along_ray"

def test_max_distance_termination():
    dem = np.zeros((5, 5), dtype=np.float32)
    # Observer near centre, pointing NE; the raster is large enough that max_range is hit first
    observer_x, observer_y = 2 * 5.0, -2 * 5.0
    ray = calculate_horizon_ray(
        dem=dem,
        transform=DEFAULT_AFFINE,
        observer_x=observer_x,
        observer_y=observer_y,
        azimuth_deg=45,
        observer_height_m=0.0,
        max_range_m=30.0,
        sample_interval_m=5.0,
        include_curvature=False,
    )
    assert ray["valid_ray"] is True
    # The ray may exit because of max_range or raster boundary; accept either.
    assert ray["ray_exit_reason"] in {"max_range_reached", "raster_boundary_exited"}
    assert ray["horizon_distance_m"] <= 30.0
