"""
Integration tests for LUNA-SCOPE Mission Intelligence API.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


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