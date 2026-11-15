from types import SimpleNamespace

from fastapi.testclient import TestClient
import numpy as np
import pytest
from pydantic import TypeAdapter

from app.api.routes import mission_intelligence as routes
from app.main import app
from app.mission.decision_engine import engine
from app.scientific_engines.ephemeris.geometry import utc_datetime
from app.scientific_engines.ephemeris.kernels import KernelUnavailable, coverage
from app.scientific_engines.ephemeris.observer import ObserverUnavailable
from app.scientific_engines.terrain.explorer import site_elevation_path

BASE = "/terrain/explorer/mission-intelligence"
WINDOW = {"start_utc": "2026-01-01T00:00:00Z", "end_utc": "2026-01-01T02:30:00Z"}
SITES = ["Site04", "Site11", "Site23"]


@pytest.fixture
def live_science():
    try:
        coverage()
        for site in SITES:
            if not site_elevation_path(site).is_file():
                pytest.skip(f"Native DEM unavailable for {site}")
    except KernelUnavailable as exc:
        if str(exc).startswith("Missing or unreadable NAIF kernel"):
            pytest.skip(str(exc))
        raise


def test_assessment_matches_engine_and_existing_timeline_at_native_pixel(live_science):
    point = {"easting_m": -975, "northing_m": -6975}
    payload = {"site_id": "Site04", "point": point, **WINDOW,
               "profile": {"name":"Disc test", "earth_requirement":"any_disc"},
               "equipment":{"name":"Mask test", "minimum_antenna_elevation_deg":10}}
    with TestClient(app) as client:
        response = client.post(BASE+"/assessment", json=payload)
        assert response.status_code == 200, response.text
        result = response.json()
        timeline = client.post("/terrain/explorer/mission-timeline/site", json={
            "site_id":"Site04","point":point,**WINDOW, "refine_transitions":False,
            "profile":result["effective_profile"],
        })
        assert timeline.status_code == 200, timeline.text
    observer = result["observer"]
    assert observer == timeline.json()["observer"]
    assert (observer["source_pixel_row"], observer["source_pixel_column"]) == (1595, 1605)
    assert result["timeline"]["summary"] == timeline.json()["summary"]
    assert result["timeline"]["summary"]["favourable_windows"] == []
    expected = engine.assess_site(
        "SHACKLETON_RIM", utc_datetime(WINDOW["start_utc"]), utc_datetime(WINDOW["end_utc"]),
        antenna_min_elevation_deg=10, point=(observer["easting_m"], observer["northing_m"]),
        earth_criterion="any_disc", match_endpoint=True,
    )
    assert result["assessment"] == TypeAdapter(engine.SiteAssessment).dump_python(expected, mode="json")
    assert result["assessment"]["illumination"]["provenance"]["observer"] == observer
    assert result["assessment"]["communication"]["provenance"]["observer"] == observer
    assert result["contributions"] == {item.criterion:item.weighted_score for item in expected.criteria}


def test_three_sites_and_equipment_use_matched_time_and_no_incomplete_ranking(live_science):
    scenarios = [{"name":site, "site_id":site} for site in SITES]
    scenarios.append({"name":"Site23 raised mask","site_id":"Site23",
                      "equipment":{"name":"Raised mask","minimum_antenna_elevation_deg":90}})
    payload = {"scenarios":scenarios,"start_utc":"2026-01-01T00:00:00Z","end_utc":"2026-01-02T00:00:00Z"}
    with TestClient(app) as client:
        response = client.post(BASE+"/compare", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    rows = [entry["result"] for entry in result["scenarios"]]
    assert [row["observer"]["site_id"] for row in rows] == SITES+["Site23"]
    assert len({row["observer"]["source_dem_sha256"] for row in rows}) == 3
    assert all(row["timeline"]["start_utc"] == payload["start_utc"] and row["timeline"]["end_utc"] == payload["end_utc"] for row in rows)
    assert rows[1]["timeline"]["summary"]["duration_s"]["unresolved"] == 86400
    assert rows[1]["operational_screen"] == "unresolved"
    assert rows[2]["observer"] == rows[3]["observer"]
    assert rows[2]["assessment"]["criteria"] == rows[3]["assessment"]["criteria"]
    assert rows[3]["effective_profile"]["minimum_antenna_elevation_deg"] == 90
    assert rows[2]["timeline"]["summary"] != rows[3]["timeline"]["summary"]
    assert result["ranked_groups"] == []
    assert any("Antenna mask" in change for change in result["differences"][-1]["changes"])


def test_instant_copilot_and_new_point_do_not_invent_duration(live_science):
    payload = {"site_id":"Site04","utc":WINDOW["start_utc"],"action":"solar"}
    with TestClient(app) as client:
        first = client.post(BASE+"/copilot", json=payload)
        second = client.post(BASE+"/copilot", json={**payload,"utc":WINDOW["end_utc"],
                                                  "point":{"easting_m":-965,"northing_m":-6985}})
        missing = client.post(BASE+"/copilot", json={"site_id":"Site04","action":"timeline"})
    assert first.status_code == second.status_code == missing.status_code == 200, (first.text, second.text, missing.text)
    assert first.json()["observer"]["source_pixel_row"] != second.json()["observer"]["source_pixel_row"]
    assert first.json()["response"]["sample"]["solar_source_utc"] == WINDOW["start_utc"]
    assert second.json()["response"]["sample"]["solar_source_utc"] == WINDOW["end_utc"]
    assert second.json()["assessment"] is None
    assert missing.json()["missing_inputs"] == ["UTC start and end"]


@pytest.mark.parametrize("payload", [
    {"site_id":"Site99"},
    {"site_id":"Site04","weights":{"terrain_slope":0.5}},
    {"site_id":"Site04","thresholds":{"max_roughness_m":0}},
    {"site_id":"Site04","equipment":{"name":"Bad mask","minimum_antenna_elevation_deg":100}},
    {"site_id":"Site04","point":{"easting_m":0,"northing_m":0,"elevation_m":9000}},
    {"site_id":"Site04","start_utc":WINDOW["start_utc"]},
    {"site_id":"Site04","utc":"2026-01-01T00:00"},
    {"site_id":"Site04","utc":WINDOW["start_utc"],**WINDOW},
    {"site_id":"Site04","end_utc":WINDOW["start_utc"],"start_utc":WINDOW["end_utc"]},
])
def test_invalid_request_is_rejected(payload):
    with TestClient(app) as client:
        assert client.post(BASE+"/assessment", json=payload).status_code == 422


def test_availability_failure_and_nodata_are_explicit(monkeypatch):
    def unavailable(site):
        raise ObserverUnavailable("Native LOLA data unavailable.")

    monkeypatch.setattr(routes, "load_terrain", unavailable)
    with TestClient(app) as client:
        failure = client.post(BASE+"/assessment", json={"site_id":"Site11"})
        compared = client.post(BASE+"/compare", json={"scenarios":[{"name":site,"site_id":site} for site in SITES]})
        assert failure.status_code == 503
        assert compared.status_code == 200
        assert all(row["result"] is None and row["unavailable"] for row in compared.json()["scenarios"])
        assert compared.json()["ranked_groups"] == []
        terrain = SimpleNamespace(dem=np.array([[np.nan]]), point_cell=lambda point:(0,0),
                                  reference=SimpleNamespace(site_id="Site11"))
        monkeypatch.setattr(routes, "load_terrain", lambda site: terrain)
        nodata = client.post(BASE+"/assessment", json={"site_id":"Site11"})
        assert nodata.status_code == 422 and "no valid native elevation" in nodata.json()["detail"]


def test_duplicate_scenario_and_unsupported_copilot_action_rejected():
    with TestClient(app) as client:
        scenarios = [{"site_id":"Site04","name":"Case"},{"site_id":"Site11","name":"case"}]
        assert client.post(BASE+"/compare", json={"scenarios":scenarios}).status_code == 422
        assert client.post(BASE+"/copilot", json={"site_id":"Site04","action":"publish"}).status_code == 422
