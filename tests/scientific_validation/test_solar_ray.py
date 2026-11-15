import numpy as np
import pytest
from rasterio.transform import Affine
from rasterio.warp import transform

from app.scientific_engines.ephemeris.observer import Observer, local_basis
from app.scientific_engines.illumination.ray import GRAZE_DEG, cell_intervals, trace
from app.scientific_engines.illumination import service
from app.scientific_engines.illumination.service import Terrain
from app.scientific_engines.ephemeris.geometry import InvalidEpoch, utc_datetime
from app.scientific_engines.terrain.lunar_context import GEOD, LUNAR_GEOGRAPHIC, RADIUS


def setup(dem, rms=None):
    affine = Affine(5, 0, -22.5, 0, -5, 30022.5)
    reference = Observer("Synthetic", 0, 0, 0, 0, 0, 0, 0, "", "", "", "")
    grid = Terrain(np.asarray(dem, dtype=float), rms, affine, ~affine, reference, (5, 5), (), None)
    return grid, grid.cell_observer(4, 4)


def sun(elevation, azimuth=90):
    return {"azimuth_deg": azimuth, "elevation_deg": elevation, "angular_diameter_deg": 0.54,
            "enu_unit_vector": [1, 0, 0]}


def test_flat_terrain_clear_within_coverage_and_safe_steep_ray():
    terrain, obs = setup(np.zeros((9, 9)))
    with_extent = trace(terrain, obs, sun(2))
    assert with_extent["native_state"] == "clear" and with_extent["state"] == "unknown"
    assert with_extent["reason"] == "terrain_extent" and with_extent["traced_distance_m"] == pytest.approx(22.5, rel=0.001)
    above = trace(terrain, obs, sun(89.999))
    assert above["state"] == "illuminated" and above["reason"] == "clears_model_ceiling"
    assert above["solar_angular_radius_deg"] == 0.27
    assert trace(terrain, obs, sun(-0.1))["reason"] == "below_horizontal"
    assert trace(terrain, obs, sun(GRAZE_DEG / 2))["reason"] == "grazing"


def test_ridge_shadow_remains_detectable_after_a_nodata_gap():
    dem = np.zeros((9, 9))
    dem[4, 6] = np.nan
    dem[4, 7] = 5
    terrain, obs = setup(dem)
    ridge = trace(terrain, obs, sun(4))
    assert ridge["reason"] == "native_terrain_obstruction"
    assert ridge["nodata_along_ray"] == 1
    assert 12.49 < ridge["horizon_distance_m"] < 12.51
    assert trace(terrain, obs, sun(ridge["native_horizon_deg"]))["reason"] == "grazing"
    assert trace(terrain, obs, sun(35))["reason"] == "nodata_along_ray"


def test_rms_is_a_sensitivity_scenario_and_leaves_nominal_result_explicit():
    dem = np.zeros((9, 9))
    dem[4, 7] = 1
    terrain, obs = setup(dem, np.full((9, 9), 0.25))
    result = trace(terrain, obs, sun(5))
    assert result["rms_horizon_deg"][0] < 5 < result["rms_horizon_deg"][1]
    assert result["rms_sensitive"] and result["native_state"] == "clear"


def test_ray_cells_match_independent_geodesic_and_full_inverse_affine():
    # Test away from the prime meridian on a rotated affine grid.
    affine = Affine.translation(-39200, 21100) @ Affine.rotation(16) @ Affine.scale(5, -5)
    grid, _ = setup(np.zeros((9, 9)))
    from dataclasses import replace
    grid = replace(grid, transform=affine, inverse=~affine)
    obs = grid.cell_observer(4, 4)
    rows, cols, start, end, left = cell_intervals(~affine, grid.dem.shape,
        local_basis(obs.latitude_deg, obs.longitude_deg_east), 53, 100/RADIUS)
    assert left and (rows[0], cols[0]) == (4, 4)
    crs = f"+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R={RADIUS} +units=m +type=crs"
    for row, col, a, b in zip(rows, cols, start, end):
        lon, lat, _ = GEOD.fwd(obs.longitude_deg_east, obs.latitude_deg, 53, RADIUS*(a+b)/2)
        x, y = transform(LUNAR_GEOGRAPHIC, crs, [lon], [lat])
        assert tuple(np.floor(~affine @ (x[0], y[0]))) == (col, row)


def test_interval_durations_transitions_and_single_sample_gap():
    times = [utc_datetime(f"2026-01-01T0{i}:00:00Z") for i in range(7)]
    states = ["illuminated", "illuminated", "shadowed", "illuminated", "shadowed", "shadowed", "unknown"]
    values = [{"state": value} for value in states]
    result = service.summarize(times, values)
    assert result["duration_s"] == {"illuminated": 3600, "shadowed": 3600, "unknown": 14400}
    assert result["longest_clear_s"] == result["longest_shadow_s"] == 3600
    assert result["fraction_known_time_clear"] == 0.5
    assert len(result["transitions"]) == 3
    assert result["gap_count"] == 1
    assert result["gaps"][0]["duration_s"] == 0 and result["gaps"][0]["bracket_s"] == 7200
    for state in ("illuminated", "shadowed", "unknown"):
        constant = service.summarize(times, [{"state": state}] * len(times))
        assert constant["duration_s"][state] == 21600
        assert constant["transitions"] == []


def test_range_end_is_evaluated_and_invalid_ranges_are_rejected():
    start = utc_datetime("2025-12-31T23:00:00Z")
    end = utc_datetime("2026-01-01T00:15:00Z")
    values = service.epochs_with_end(start, end, 3600)
    assert len(values) == 3 and values[-1] == end
    assert values[1].year == 2026
    with pytest.raises(InvalidEpoch):
        service.epochs_with_end(end, start, 3600)


def test_region_no_data_counts_and_lit_percentage_use_native_valid_denominator(monkeypatch):
    dem = np.zeros((9, 9))
    dem[3, 3] = np.nan
    terrain, obs = setup(dem)
    monkeypatch.setattr(service, "load_terrain", lambda site: terrain)
    monkeypatch.setattr(service, "covered_et", lambda time: None)
    outcomes = {4: "illuminated", 3: "unknown", 5: "shadowed"}
    monkeypatch.setattr(service, "sample", lambda grid, observer, time: {
        "state": outcomes.get(observer.source_pixel_column, "shadowed"),
        "native_state": "clear" if observer.source_pixel_column == 3 else "shadowed", "rms_sensitive": False,
    })
    time = utc_datetime("2026-01-01T00:00:00Z")
    region = service.region_analysis("Synthetic", (obs.easting_m, obs.northing_m), 3, [time])
    frame = region["frames"][0]
    assert frame["counts"] == {"illuminated": 3, "shadowed": 3, "unknown": 2, "invalid": 1, "valid_cells": 8, "classified": 6}
    assert frame["lit_percent_of_valid_cells"] == 37.5
    assert frame["lit_percent_of_classified_cells"] == 50
    assert frame["native_clear"] == 2
    assert region["region"]["left"] == region["region"]["top"] == 3
    with pytest.raises(ValueError, match="Region limit"):
        service.region_analysis("Synthetic", None, 16, [time] * 4)
