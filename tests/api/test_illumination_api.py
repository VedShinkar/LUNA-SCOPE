from math import isfinite

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scientific_engines.ephemeris.kernels import KernelUnavailable, coverage
from app.scientific_engines.illumination import service

BASE = "/terrain/explorer/illumination"
TIME = "2026-01-15T06:00:00Z"


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def kernels():
    try:
        coverage()
    except KernelUnavailable as exc:
        if str(exc).startswith("Missing or unreadable NAIF kernel"):
            pytest.skip(str(exc))
        raise


@pytest.mark.parametrize("site", ["Site04", "Site11", "Site23"])
def test_point_and_region_match_native_site_geometry(client, kernels, site):
    point = client.post(f"{BASE}/point", json={"site_id":site,"utc":TIME})
    assert point.status_code == 200
    data = point.json()
    assert data["terrain"]["file"].startswith(site) and data["terrain"]["resolution_m"] == [5, 5]
    assert data["terrain"]["rms_source_url"].endswith("toterr.tif")
    sample = data["samples"][0]
    assert isfinite(sample["solar_elevation_deg"]) and sample["utc"] == TIME
    angular = client.post("/terrain/explorer/celestial/geometry", json={
        "site_id":site, "utc":TIME, "point":{"easting_m":data["observer"]["easting_m"],"northing_m":data["observer"]["northing_m"]},
    }).json()["samples"][0]["sun"]
    assert sample["solar_azimuth_deg"] == pytest.approx(angular["azimuth_deg"], abs=1e-10)
    assert sample["solar_elevation_deg"] == pytest.approx(angular["elevation_deg"], abs=1e-10)
    if site in ("Site04", "Site11"):
        assert sample["centre_above_horizontal"] and sample["reason"] == "native_terrain_obstruction"
    region = client.post(f"{BASE}/region", json={"site_id":site,"times_utc":[TIME],"side":4}).json()
    frame = region["frames"][0]
    assert frame["counts"]["valid_cells"] + frame["counts"]["invalid"] == 16
    index = 4*(data["observer"]["source_pixel_row"]-region["region"]["top"]) + data["observer"]["source_pixel_column"]-region["region"]["left"]
    assert frame["states"][index] == sample["state"]


def test_series_uses_each_epoch_and_accounts_for_entire_requested_range(client, kernels):
    result = client.post(f"{BASE}/series", json={"site_id":"Site04","start_utc":TIME,
        "end_utc":"2026-01-15T07:30:00Z","step_seconds":3600})
    assert result.status_code == 200
    report = result.json()
    assert len(report["samples"]) == 3
    assert len({entry["solar_azimuth_deg"] for entry in report["samples"]}) == 3
    assert sum(report["summary"]["duration_s"].values()) == 5400


def test_region_bounds_and_unavailable_inputs(client, kernels, monkeypatch):
    assert client.post(f"{BASE}/point",json={"site_id":"Site99","utc":TIME}).status_code == 404
    assert client.post(f"{BASE}/point",json={"site_id":"Site04","utc":"2026-01-15T06:00:00"}).status_code == 422
    assert client.post(f"{BASE}/point",json={"site_id":"Site04","utc":TIME,"point":{"easting_m":1e8,"northing_m":1e8}}).status_code == 422
    assert client.post(f"{BASE}/region",json={"site_id":"Site04","times_utc":[TIME],"side":17}).status_code == 422
    assert client.post(f"{BASE}/region",json={"site_id":"Site04","times_utc":[TIME,TIME],"side":4}).status_code == 422
    def missing(*args):
        raise KernelUnavailable("Test kernel missing")
    monkeypatch.setattr(service, "covered_et", missing)
    result = client.post(f"{BASE}/point",json={"site_id":"Site04","utc":TIME})
    assert result.status_code == 503 and "samples" not in result.json()
