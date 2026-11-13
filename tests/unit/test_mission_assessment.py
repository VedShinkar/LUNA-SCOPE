"""
Tests for LUNA-SCOPE Mission Assessment.
"""

import pytest

from app.mission.decision_engine.assessment import assess_mission


PROFILE_ID = "ROVER_EXPLORATION_V1"


def test_shackleton_assessment():

    result = assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "FEASIBLE"
    assert result["site_name"] == "Shackleton Rim"


def test_assessment_contains_score():

    result = assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["score"]["overall"] == 100.0
    assert result["score"]["scale"] == "0_to_100"


def test_assessment_contains_recommendation():

    result = assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["recommendation"] is not None


def test_assessment_contains_data_quality():

    result = assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["assessment_status"] == "SYNTHETIC_EXAMPLE"


def test_assessment_contains_raw_inputs():

    result = assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["raw_inputs"]["site_name"] == "Shackleton Rim"


def test_invalid_site_is_rejected():

    with pytest.raises(ValueError):

        assess_mission(
            "INVALID_SITE",
            PROFILE_ID
        )


def test_invalid_profile_is_rejected():

    with pytest.raises(ValueError):

        assess_mission(
            "SHACKLETON_RIM",
            "INVALID_PROFILE"
        )