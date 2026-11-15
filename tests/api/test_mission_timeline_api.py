from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.scientific_engines import mission_service as service
from app.scientific_engines.ephemeris.kernels import KernelUnavailable, coverage

BASE = "/terrain/explorer/mission-timeline"
REQUEST = {"site_id":"Site04","start_utc":"2026-01-01T00:00:00Z","end_utc":"2026-01-01T02:30:00Z",
           "step_seconds":3600,"refine_transitions":False}


@pytest.fixture
def client():
    try:
        coverage()
    except KernelUnavailable as exc:
        if str(exc).startswith("Missing or unreadable NAIF kernel"):
            pytest.skip(str(exc))
        raise
    with TestClient(app) as instance:
        yield instance


def test_matched_comparison_observers_and_inspection(client):
    response = client.post(BASE+"/compare",json={**REQUEST,"points":{"Site04":{"easting_m":-975,"northing_m":-6975}}})
    assert response.status_code == 200, response.text
    result = response.json()
    timelines = result["timelines"]
    assert [row["site_id"] for row in timelines] == ["Site04","Site11","Site23"]
    assert len({row["observer"]["longitude_deg_east"] for row in timelines}) == 3
    assert len({row["terrain"]["source_dem_sha256"] for row in timelines}) == 3
    assert all(row["profile"] == result["profile"] for row in timelines)
    schedules = {tuple(sample["utc"] for sample in row["samples"]) for row in timelines}
    assert len(schedules) == 1
    for row in timelines:
        assert len(row["samples"]) == 4 and row["samples"][-1]["utc"] == REQUEST["end_utc"]
        assert all(sample["solar_source_utc"] == sample["earth_source_utc"] == sample["utc"] for sample in row["samples"])
        assert sum(row["summary"]["duration_s"].values()) == 9000
    check = client.post(BASE+"/inspect",json={**REQUEST,"inspect_utc":REQUEST["end_utc"]})
    assert check.status_code == 200
    assert check.json()["interval"]["duration_s"] == 1800


def test_profile_changes_do_not_change_physical_sample_tracks(client):
    first = client.post(BASE+"/site",json=REQUEST).json()
    next_result = client.post(BASE+"/site",json={**REQUEST,"profile":{"minimum_antenna_elevation_deg":90}}).json()
    assert first["observer"] == next_result["observer"]
    for a,b in zip(first["samples"],next_result["samples"],strict=True):
        assert a["utc"] == b["utc"]
        for key in ("solar","earth_centre","earth_disc"):
            assert a["tracks"][key] == b["tracks"][key]
        assert b["tracks"]["antenna"] == "below_mask"
    assert client.get(BASE+"/profile").json()["version"] == "1"
    assert client.post(BASE+"/profile",json={"minimum_antenna_elevation_deg":91}).status_code == 422
    assert client.post(BASE+"/site",json={**REQUEST,"end_utc":REQUEST["start_utc"]}).status_code == 422


def test_unavailable_upstream_fails_without_success_payload(client, monkeypatch):
    def unavailable(*args):
        raise KernelUnavailable("Test kernel unavailable")
    monkeypatch.setattr(service,"covered_et",unavailable)
    response = client.post(BASE+"/site",json={**REQUEST,"site_id":"Site11"})
    assert response.status_code == 503 and "samples" not in response.json()
