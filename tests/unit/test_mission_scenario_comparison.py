"""
Tests for LUNA-SCOPE Scenario Comparison Engine.
"""

import pytest

from app.mission.decision_engine.scenario_comparison import compare_scenarios


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


def test_ranks_are_sequential():

    results = compare_scenarios(
        [
            "SHACKLETON_RIM",
            "MALAPERT_MASSIF",
            "DE_GERLACHE_RIM"
        ],
        PROFILE_ID
    )

    assert [result["rank"] for result in results] == [1, 2, 3]


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