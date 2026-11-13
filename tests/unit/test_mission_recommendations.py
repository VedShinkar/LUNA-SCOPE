"""
Tests for LUNA-SCOPE Mission Recommendation Engine.
"""

import pytest

from app.mission.decision_engine.recommendations import generate_recommendation


PROFILE_ID = "ROVER_EXPLORATION_V1"


def test_shackleton_recommendation():

    result = generate_recommendation(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "FEASIBLE"
    assert result["overall_score"] == 100.0


def test_malapert_recommendation():

    result = generate_recommendation(
        "MALAPERT_MASSIF",
        PROFILE_ID
    )

    assert result["feasibility"] == "NOT_FEASIBLE"
    assert len(result["risk_factors"]) >= 2


def test_de_gerlache_recommendation():

    result = generate_recommendation(
        "DE_GERLACHE_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "NOT_FEASIBLE"
    assert len(result["risk_factors"]) >= 3


def test_synthetic_data_warning():

    result = generate_recommendation(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert "Synthetic test data" in result["risk_factors"]


def test_invalid_site_is_rejected():

    with pytest.raises(ValueError):

        generate_recommendation(
            "INVALID_SITE",
            PROFILE_ID
        )


def test_invalid_profile_is_rejected():

    with pytest.raises(ValueError):

        generate_recommendation(
            "SHACKLETON_RIM",
            "INVALID_PROFILE"
        )