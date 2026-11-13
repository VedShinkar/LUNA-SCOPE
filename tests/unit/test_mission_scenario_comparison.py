"""
Tests for LUNA-SCOPE Scenario Comparison Engine.
"""

import pytest

from app.mission.decision_engine.scenario_comparison import compare_scenarios
from app.mission.decision_engine import scenario_comparison as comparison_module


PROFILE_ID = "ROVER_EXPLORATION_V1"


def test_scenarios_are_ranked():

    results = compare_scenarios(
        [
            "SHACKLETON_RIM",
            "MALAPERT_MASSIF",
            "DE_GERLACHE_RIM"
        ],
        PROFILE_ID
    )

    assert results[0]["site_id"] == "SHACKLETON_RIM"
    assert results[0]["rank"] == 1


def test_feasible_location_ranks_first():

    results = compare_scenarios(
        [
            "MALAPERT_MASSIF",
            "DE_GERLACHE_RIM",
            "SHACKLETON_RIM"
        ],
        PROFILE_ID
    )

    assert results[0]["feasibility"] == "FEASIBLE"


def test_all_locations_are_compared():

    results = compare_scenarios(
        [
            "SHACKLETON_RIM",
            "MALAPERT_MASSIF",
            "DE_GERLACHE_RIM"
        ],
        PROFILE_ID
    )

    assert len(results) == 3


def test_only_feasible_locations_receive_ranks():

    results = compare_scenarios(
        [
            "SHACKLETON_RIM",
            "MALAPERT_MASSIF",
            "DE_GERLACHE_RIM"
        ],
        PROFILE_ID
    )

    feasible_results = [
        result for result in results
        if result["feasibility"] == "FEASIBLE"
    ]

    not_feasible_results = [
        result for result in results
        if result["feasibility"] == "NOT_FEASIBLE"
    ]

    assert len(feasible_results) == 1
    assert feasible_results[0]["rank"] == 1

    assert len(not_feasible_results) == 2

    for result in not_feasible_results:
        assert result["rank"] is None

def test_invalid_site_is_rejected():

    with pytest.raises(ValueError):

        compare_scenarios(
            ["INVALID_SITE"],
            PROFILE_ID
        )


def test_invalid_profile_is_rejected():

    with pytest.raises(ValueError):

        compare_scenarios(
            ["SHACKLETON_RIM"],
            "INVALID_PROFILE"
        )

def test_mixed_feasibility_statuses(monkeypatch):

    fake_results = {
        "SITE_A": {
            "site_id": "SITE_A",
            "site_name": "Site A",
            "feasibility": "INSUFFICIENT_DATA",
            "overall_score": None,
            "risk_factors": []
        },
        "SITE_B": {
            "site_id": "SITE_B",
            "site_name": "Site B",
            "feasibility": "NOT_FEASIBLE",
            "overall_score": 95,
            "risk_factors": []
        },
        "SITE_C": {
            "site_id": "SITE_C",
            "site_name": "Site C",
            "feasibility": "FEASIBLE",
            "overall_score": 80,
            "risk_factors": []
        }
    }

    monkeypatch.setattr(
        comparison_module,
        "generate_recommendation",
        lambda site_id, profile_id: fake_results[site_id].copy()
    )

    results = compare_scenarios(
        ["SITE_A", "SITE_B", "SITE_C"],
        PROFILE_ID
    )

    assert results[0]["feasibility"] == "FEASIBLE"
    assert results[1]["feasibility"] == "NOT_FEASIBLE"
    assert results[2]["feasibility"] == "INSUFFICIENT_DATA"

    assert results[0]["rank"] == 1
    assert results[1]["rank"] is None
    assert results[2]["rank"] is None


def test_all_sites_with_insufficient_data(monkeypatch):

    def fake_recommendation(site_id, profile_id):

        return {
            "site_id": site_id,
            "site_name": site_id,
            "feasibility": "INSUFFICIENT_DATA",
            "overall_score": None,
            "risk_factors": []
        }

    monkeypatch.setattr(
        comparison_module,
        "generate_recommendation",
        fake_recommendation
    )

    results = compare_scenarios(
        ["SITE_A", "SITE_B", "SITE_C"],
        PROFILE_ID
    )

    assert len(results) == 3

    for result in results:
        assert result["feasibility"] == "INSUFFICIENT_DATA"
        assert result["rank"] is None


def test_tied_feasible_scores_receive_same_rank(monkeypatch):

    fake_results = {
        "SITE_A": {
            "site_id": "SITE_A",
            "site_name": "Site A",
            "feasibility": "FEASIBLE",
            "overall_score": 90,
            "risk_factors": []
        },
        "SITE_B": {
            "site_id": "SITE_B",
            "site_name": "Site B",
            "feasibility": "FEASIBLE",
            "overall_score": 90,
            "risk_factors": []
        }
    }

    monkeypatch.setattr(
        comparison_module,
        "generate_recommendation",
        lambda site_id, profile_id: fake_results[site_id].copy()
    )

    results = compare_scenarios(
        ["SITE_A", "SITE_B"],
        PROFILE_ID
    )

    assert results[0]["overall_score"] == results[1]["overall_score"]

    assert results[0]["rank"] == 1
    assert results[1]["rank"] == 1
def test_duplicate_site_ids_are_rejected():

    with pytest.raises(ValueError, match="Duplicate site IDs"):

        compare_scenarios(
            [
                "SHACKLETON_RIM",
                "MALAPERT_MASSIF",
                "SHACKLETON_RIM"
            ],
            PROFILE_ID
        )