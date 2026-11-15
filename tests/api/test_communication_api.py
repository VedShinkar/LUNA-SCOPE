import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scientific_engines.ephemeris.kernels import KernelUnavailable, coverage

BASE = "/terrain/explorer/communication"
UTC = "2026-01-01T00:00:00Z"


@pytest.fixture
def client():
    try:
        coverage()
    except KernelUnavailable as exc:
        if str(exc).startswith("Missing or unreadable NAIF kernel"):
            pytest.skip(str(exc))
        raise
    with TestClient(app) as value:
        yield value


@pytest.mark.parametrize("site", ["Site04","Site11","Site23"])
def test_earth_point_and_region_use_native_site_and_phase31(client, site):
    response = client.post(BASE+"/point", json={"site_id":site,"utc":UTC})
    assert response.status_code == 200, response.text
    result = response.json()
    observer = result["observer"]
    assert observer["site_id"] == site and result["terrain"]["file"].startswith(site)
    assert result["terrain"]["resolution_m"] == [5,5]
    native_point = {key:observer[key] for key in ("easting_m","northing_m")}
    geometry = client.post("/terrain/explorer/celestial/geometry",json={"site_id":site,"utc":UTC,"point":native_point})
    earth = geometry.json()["samples"][0]["earth"]
    sample = result["samples"][0]
    assert sample["earth_azimuth_deg"] == pytest.approx(earth["azimuth_deg"],abs=1e-10)
    assert sample["earth_elevation_deg"] == pytest.approx(earth["elevation_deg"],abs=1e-10)
    assert sample["earth_angular_radius_deg"] == pytest.approx(earth["angular_diameter_deg"]/2,abs=1e-10)
    assert sample["native_horizon_deg"] is not None
    raised = client.post(BASE+"/point", json={"site_id":site,"utc":UTC,"antenna_min_elevation_deg":90}).json()["samples"][0]
    assert not raised["antenna_eligible"]
    assert raised["centre_state"] == sample["centre_state"] and raised["disc_state"] == sample["disc_state"]
    region = client.post(BASE+"/region",json={"site_id":site,"utc":UTC,"side":2}).json()
    assert len(region["cells"]) == 4 and region["counts"]["valid"] + region["counts"]["invalid"] == 4
    assert sum(region["counts"][f"centre_{state}"] for state in ("visible","obstructed","unresolved")) == region["counts"]["valid"]
    assert region["cells"][3]["centre_state"] == sample["centre_state"]


def test_metadata_series_and_invalid_inputs(client):
    info = client.get(BASE+"/metadata")
    assert info.status_code == 200 and len(info.json()["sites"]) == 3 and info.json()["coverage"]
    request = {"site_id":"Site04","start_utc":UTC,"end_utc":"2026-01-01T03:30:00Z","step_seconds":3600,"criterion":"full_disc"}
    response = client.post(BASE+"/series",json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["requested_sample_count"] == 5
    assert result["samples"][-1]["utc"] == request["end_utc"]
    assert sum(result["summary"]["duration_s"].values()) == 12600
    assert len({v["earth_elevation_deg"] for v in result["samples"]}) == len(result["samples"])
    assert client.post(BASE+"/series",json={**request,"step_seconds":60,"end_utc":"2026-01-02T00:00:00Z"}).status_code == 422
    assert client.post(BASE+"/series",json={**request,"end_utc":"2025-01-01T00:00:00Z"}).status_code == 422
    assert client.post(BASE+"/point",json={"site_id":"Site04","utc":UTC,"antenna_min_elevation_deg":91}).status_code == 422
    assert client.post(BASE+"/point",json={"site_id":"Site99","utc":UTC}).status_code == 404
    assert client.post(BASE+"/point",json={"site_id":"Site23","utc":UTC,"point":{"easting_m":1e9,"northing_m":1e9}}).status_code == 422
