from dataclasses import replace
from datetime import timedelta
import json
from math import atan2, cos, degrees, radians, sin
from pathlib import Path

import numpy as np
import pytest
import spiceypy

from app.scientific_engines.ephemeris.geometry import InvalidEpoch, epochs, geometry_at, utc_datetime
from app.scientific_engines.ephemeris.kernels import BODY_FRAME, LOCK, KernelUnavailable, coverage
from app.scientific_engines.ephemeris.observer import UnsupportedObserver, azimuth_elevation, local_basis, resolve_observer


@pytest.fixture(scope="module")
def live_coverage():
    try:
        return coverage()
    except KernelUnavailable as error:
        if str(error).startswith("Missing or unreadable NAIF kernel"):
            pytest.skip(str(error))
        raise


def test_local_basis_at_prime_meridian_and_east_longitude():
    np.testing.assert_allclose(local_basis(0, 0), [[0, 1, 0], [0, 0, 1], [1, 0, 0]], atol=1e-15)
    np.testing.assert_allclose(local_basis(0, 90), [[-1, 0, 0], [0, 0, 1], [0, 1, 0]], atol=1e-15)
    for lat, lon in [(-89.77, -171.87), (43, 135), (-90, 0)]:
        basis = local_basis(lat, lon)
        np.testing.assert_allclose(basis @ basis.T, np.eye(3), atol=1e-15)
        assert np.linalg.det(basis) == pytest.approx(1)


@pytest.mark.parametrize("vector,expected", [
    ((0, 1, 0), (0, 0)), ((1, 0, 0), (90, 0)), ((0, -1, 0), (180, 0)), ((-1, 0, 0), (270, 0)),
    ((0, 0, 1), (None, 90)), ((0, 0, -1), (None, -90)), ((1, 0, -1), (90, -45)),
])
def test_azimuth_elevation_axes(vector, expected):
    assert azimuth_elevation(vector) == expected


def test_utc_and_bounded_time_series():
    start = utc_datetime("2026-01-01T00:00:00+00:00")
    assert epochs(start, start + timedelta(seconds=121), 60)[-1] == start + timedelta(seconds=120)
    for value in ("2026-01-01T00:00:00", "2026-01-01T00:00:00+05:30", "2026-02-30T00:00:00Z", "2016-12-31T23:59:60Z"):
        with pytest.raises(InvalidEpoch):
            utc_datetime(value)
    with pytest.raises(InvalidEpoch, match="241"):
        epochs(start, start + timedelta(hours=5), 60)
    with pytest.raises(InvalidEpoch, match="range"):
        epochs(start, start - timedelta(seconds=1), 60)


@pytest.mark.parametrize("site,latitude,longitude", [
    ("Site04", -89.7668, -171.87), ("Site11", -88.6834, -67.9321), ("Site23", -85.9948, -0.23578),
])
def test_observer_centres_match_nasa_lunar_surface_data_book(site, latitude, longitude):
    value = resolve_observer(site)
    assert value.latitude_deg == pytest.approx(latitude, abs=0.00003)
    assert value.longitude_deg_east == pytest.approx(longitude, abs=0.0002)
    assert value.elevation_m > 0
    picked = resolve_observer(site, (value.easting_m + 150, value.northing_m))
    assert picked.placement == "terrain point" and picked.longitude_deg_east != value.longitude_deg_east
    assert picked.source_pixel_column == value.source_pixel_column + 30
    with pytest.raises(UnsupportedObserver):
        resolve_observer(site, (1e9, 1e9))


def test_spice_rotation_and_surface_parallax(live_coverage):
    observer = resolve_observer("Site04")
    time = utc_datetime("2026-01-01T00:00:00Z")
    result = geometry_at(observer, time)
    et = result["et_tdb_s"]
    radius_km = (1_737_400 + observer.elevation_m) / 1000
    with LOCK:
        # Independent SPICE frame evaluation path and spherical conversion.
        position = spiceypy.latrec(radius_km, radians(observer.longitude_deg_east), radians(observer.latitude_deg))
        state, _ = spiceypy.spkcpo("EARTH", et, BODY_FRAME, "OBSERVER", "CN+S", position, "MOON", BODY_FRAME)
    np.testing.assert_allclose(result["earth"]["body_fixed_unit_vector"], state[:3] / np.linalg.norm(state[:3]), atol=2e-13)
    raised = geometry_at(replace(observer, elevation_m=observer.elevation_m + 1000), time)
    assert abs(result["earth"]["elevation_deg"] - raised["earth"]["elevation_deg"]) > 0.1 / 3600


def test_kernel_coverage_boundaries(live_coverage):
    observer = resolve_observer("Site04")
    for key, sign in (("start_utc", -1), ("end_utc", 1)):
        boundary = utc_datetime(live_coverage[key])
        assert geometry_at(observer, boundary)["sun"]["distance_km"] > 0
        with pytest.raises(InvalidEpoch, match="coverage"):
            geometry_at(observer, boundary + timedelta(seconds=sign))


def test_against_independent_horizons_fixture(live_coverage):
    fixture = json.loads((Path(__file__).parent / "fixtures" / "celestial_horizons.json").read_text())
    assert len(fixture["comparisons"]) == 18
    for case in fixture["comparisons"]:
        observer = resolve_observer(case["site_id"])
        direction = geometry_at(observer, utc_datetime(case["utc"]))[case["body"]]
        azimuth, elevation = radians(case["azimuth_deg"]), radians(case["elevation_deg"])
        reference = [sin(azimuth) * cos(elevation), cos(azimuth) * cos(elevation), sin(elevation)]
        unit = direction["enu_unit_vector"]
        assert degrees(atan2(np.linalg.norm(np.cross(reference, unit)), np.dot(reference, unit))) * 3600 <= 2
        assert abs(((direction["azimuth_deg"] - case["azimuth_deg"] + 180) % 360 - 180) * 3600) <= 2
        assert abs(direction["elevation_deg"] - case["elevation_deg"]) * 3600 <= 2
        assert abs(direction["angular_diameter_deg"] * 3600 - case["diameter_arcsec"]) <= 0.01
