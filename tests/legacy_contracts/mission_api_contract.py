"""
Integration tests for LUNA-SCOPE Mission Intelligence API.
"""

import pytest
import copy
from fastapi.testclient import TestClient

from app.main import app
from app.mission.decision_engine import assessment as assessment_module
from app.mission.decision_engine import feasibility as feasibility_module
from app.mission.decision_engine.mock_data import LUNAR_SITES


client = TestClient(app)

PROFILE_ID = "ROVER_EXPLORATION_V1"


# --------------------------------------------------
# Mission Assessment API Tests
# --------------------------------------------------

def test_assess_valid_site():

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "SHACKLETON_RIM",
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["site_id"] == "SHACKLETON_RIM"
    assert data["feasibility"] == "FEASIBLE"
    assert "score" in data
    assert "recommendation" in data
    assert "data_quality" in data


def test_assess_unknown_site():

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "UNKNOWN_SITE",
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 400


def test_assess_unknown_profile():

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "SHACKLETON_RIM",
            "mission_profile_id": "UNKNOWN_PROFILE"
        }
    )

    assert response.status_code == 400


def test_assess_missing_required_fields():

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "SHACKLETON_RIM"
        }
    )

    assert response.status_code == 422


def test_assess_empty_request():

    response = client.post(
        "/api/v1/mission/assess",
        json={}
    )

    assert response.status_code == 422


# --------------------------------------------------
# Mission Comparison API Tests
# --------------------------------------------------

def test_compare_valid_sites():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": [
                "SHACKLETON_RIM",
                "MALAPERT_MASSIF",
                "DE_GERLACHE_RIM"
            ],
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["mission_profile_id"] == PROFILE_ID
    assert "results" in data
    assert len(data["results"]) == 3


def test_compare_empty_site_list():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": [],
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 422


def test_compare_unknown_site():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": ["UNKNOWN_SITE"],
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 400


def test_compare_unknown_profile():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": ["SHACKLETON_RIM"],
            "mission_profile_id": "UNKNOWN_PROFILE"
        }
    )

    assert response.status_code == 400


def test_compare_missing_profile():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": ["SHACKLETON_RIM"]
        }
    )

    assert response.status_code == 422
# --------------------------------------------------
# Additional API Request Validation Tests
# --------------------------------------------------

def test_assess_whitespace_site_id():

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "   ",
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 422


def test_assess_whitespace_profile_id():

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "SHACKLETON_RIM",
            "mission_profile_id": "   "
        }
    )

    assert response.status_code == 422


def test_assess_rejects_unsupported_scenario_id():

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "SHACKLETON_RIM",
            "mission_profile_id": PROFILE_ID,
            "scenario_id": "UNSUPPORTED_SCENARIO"
        }
    )

    assert response.status_code == 422


def test_compare_whitespace_site_id():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": ["   "],
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 422


def test_compare_duplicate_site_ids():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": [
                "SHACKLETON_RIM",
                "SHACKLETON_RIM"
            ],
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 422


def test_compare_more_than_ten_sites():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": [
                "SHACKLETON_RIM",
                "MALAPERT_MASSIF",
                "DE_GERLACHE_RIM",
                "SHACKLETON_RIM_4",
                "SHACKLETON_RIM_5",
                "SHACKLETON_RIM_6",
                "SHACKLETON_RIM_7",
                "SHACKLETON_RIM_8",
                "SHACKLETON_RIM_9",
                "SHACKLETON_RIM_10",
                "SHACKLETON_RIM_11"
            ],
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 422


def test_compare_rejects_unsupported_scenario_id():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": ["SHACKLETON_RIM"],
            "mission_profile_id": PROFILE_ID,
            "scenario_id": "UNSUPPORTED_SCENARIO"
        }
    )

    assert response.status_code == 422
def test_compare_whitespace_site_id():

    response = client.post(
        "/api/v1/mission/compare",
        json={
            "site_ids": ["   "],
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 422
# --------------------------------------------------
# Mixed missing-data and failed-constraint API test
# --------------------------------------------------

def test_assess_reports_failure_and_missing_inputs(
    monkeypatch
):
    site = copy.deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    profile = feasibility_module.get_mission_profile(PROFILE_ID)

    # Create a confirmed slope failure.
    maximum_slope = profile["requirements"]["maximum_slope_deg"]
    site["slope_deg"] = maximum_slope + 1

    # Remove sunlight information.
    site["sunlight_hours"] = None

    # Supply the modified site to the real assessment pipeline.
    monkeypatch.setattr(
        feasibility_module,
        "get_lunar_site",
        lambda site_id: site
    )

    monkeypatch.setattr(
        assessment_module,
        "get_lunar_site",
        lambda site_id: site
    )

    # Stub unrelated scoring and recommendation calculations.
    monkeypatch.setattr(
        assessment_module,
        "calculate_site_score",
        lambda *args, **kwargs: {
            "overall_score": 50,
            "criterion_scores": {}
        }
    )

    monkeypatch.setattr(
        assessment_module,
        "generate_recommendation",
        lambda *args, **kwargs: {
            "risk_factors": [],
            "recommendation": "NOT_FEASIBLE"
        }
    )

    response = client.post(
        "/api/v1/mission/assess",
        json={
            "site_id": "SHACKLETON_RIM",
            "mission_profile_id": PROFILE_ID
        }
    )

    assert response.status_code == 200

    data = response.json()

    # Confirmed failure must take priority.
    assert data["feasibility"] == "NOT_FEASIBLE"

    # Failed slope must remain visible.
    assert any(
        item["requirement"] == "maximum_slope_deg"
        for item in data["failed_constraints"]
    )

    # Missing sunlight must also remain visible.
    assert (
        "minimum_sunlight_hours"
        in data["data_quality"]["missing_inputs"]
    )