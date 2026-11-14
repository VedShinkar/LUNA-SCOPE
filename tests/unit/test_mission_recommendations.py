"""
Tests for LUNA-SCOPE Mission Recommendation Engine.
"""

import pytest

from app.mission.decision_engine import recommendations
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
def test_supplied_results_are_reused_without_recalculation(monkeypatch):

    def unexpected_feasibility_call(*args, **kwargs):
        raise AssertionError("Feasibility was recalculated!")

    def unexpected_scoring_call(*args, **kwargs):
        raise AssertionError("Scoring was recalculated!")

    monkeypatch.setattr(
        recommendations,
        "check_feasibility",
        unexpected_feasibility_call
    )

    monkeypatch.setattr(
        recommendations,
        "calculate_site_score",
        unexpected_scoring_call
    )

    feasibility_result = {
        "site_id": "SHACKLETON_RIM",
        "site_name": "Shackleton Rim",
        "feasibility": "FEASIBLE",
        "failed_constraints": [],
        "missing_inputs": [],
        "data_status": "SYNTHETIC_EXAMPLE"
    }

    scoring_result = {
        "overall_score": 100.0,
        "criterion_scores": {}
    }

    result = generate_recommendation(
        "SHACKLETON_RIM",
        PROFILE_ID,
        feasibility_result=feasibility_result,
        scoring_result=scoring_result
    )

    assert result["feasibility"] == "FEASIBLE"
    assert result["overall_score"] == 100.0