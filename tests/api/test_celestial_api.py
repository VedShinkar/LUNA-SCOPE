from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.routes import celestial
from app.main import app
from app.scientific_engines.ephemeris.geometry import utc_datetime
from app.scientific_engines.ephemeris.kernels import KernelUnavailable, _load, coverage

BASE = "/terrain/explorer/celestial"
REQUEST = {"site_id": "Site04", "utc": "2026-01-01T00:00:00Z"}


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def require_kernels():
    try:
        return coverage()
    except KernelUnavailable as exc:
        if str(exc).startswith("Missing or unreadable NAIF kernel"):
            pytest.skip(str(exc))
        raise


def test_metadata_and_geometry_validate_all_observers(client):
    require_kernels()
    response = client.get(BASE + "/metadata")
    assert response.status_code == 200
    metadata = response.json()
    assert {site["site_id"] for site in metadata["sites"]} == {"Site04", "Site11", "Site23"}
    assert len(metadata["kernels"]) == 5 and metadata["coverage"]["start_utc"] < REQUEST["utc"]
    positions = set()
    for site in metadata["sites"]:
        response = client.post(BASE + "/geometry", json={**REQUEST, "site_id": site["site_id"]})
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "computed"
        assert result["observer"] == site["observer"]
        positions.add(result["samples"][0]["earth"]["azimuth_deg"])
    assert len(positions) == 3


def test_observer_point_and_series(client):
    require_kernels()
    default = client.post(BASE + "/geometry", json=REQUEST).json()
    observer = default["observer"]
    point = {"easting_m": observer["easting_m"] + 300, "northing_m": observer["northing_m"] + 100}
    response = client.post(BASE + "/series", json={
        "site_id": "Site04", "point": point, "start_utc": REQUEST["utc"],
        "end_utc": "2026-01-01T02:00:00Z", "step_seconds": 3600,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["observer"]["placement"] == "terrain point"
    assert result["observer"]["easting_m"] == point["easting_m"]
    assert result["samples"][0]["earth"]["azimuth_deg"] != default["samples"][0]["earth"]["azimuth_deg"]
    assert [sample["utc"] for sample in result["samples"]] == [f"2026-01-01T0{hour}:00:00Z" for hour in range(3)]
    assert len({sample["sun"]["azimuth_deg"] for sample in result["samples"]}) == 3


@pytest.mark.parametrize("update,code", [
    ({"site_id": "Site99"}, 404), ({"utc": "2026-01-01T00:00:00"}, 422),
    ({"utc": "2026-02-31T00:00:00Z"}, 422),
    ({"point": {"easting_m": 1e9, "northing_m": 1e9}}, 422),
])
def test_invalid_requests(client, update, code):
    response = client.post(BASE + "/geometry", json={**REQUEST, **update})
    assert response.status_code == code
    assert "samples" not in response.json()


def test_outside_coverage_and_oversized_series(client):
    interval = require_kernels()
    assert client.post(BASE + "/geometry", json={**REQUEST, "utc": "2300-01-01T00:00:00Z"}).status_code == 422
    last = utc_datetime(interval["end_utc"])
    series = {"site_id": "Site04", "start_utc": (last - timedelta(seconds=30)).isoformat(),
              "end_utc": (last + timedelta(seconds=1)).isoformat(), "step_seconds": 3600}
    assert client.post(BASE + "/series", json=series).status_code == 422
    series.update(start_utc=REQUEST["utc"], end_utc="2026-01-02T00:00:00Z", step_seconds=60)
    assert "241" in client.post(BASE + "/series", json=series).json()["detail"]


def test_missing_kernel_disables_calculation(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LUNA_SPICE_KERNEL_DIR", str(tmp_path))
    with pytest.raises(KernelUnavailable, match="naif0012.tls"):
        _load.__wrapped__()

    def unavailable(*args):
        return _load.__wrapped__()

    monkeypatch.setattr(celestial, "geometry_at", unavailable)
    monkeypatch.setattr(celestial, "coverage", unavailable)
    error = client.post(BASE + "/geometry", json=REQUEST)
    assert error.status_code == 503 and "naif0012.tls" in error.json()["detail"]
    meta = client.get(BASE + "/metadata").json()
    assert meta["coverage"] is None and "naif0012.tls" in meta["error"]
