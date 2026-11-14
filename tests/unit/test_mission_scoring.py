"""
Tests for LUNA-SCOPE Mission Scoring Engine.
"""

import pytest

from app.mission.decision_engine.scoring_engine import calculate_site_score
import copy

from app.mission.decision_engine import scoring_engine
from app.mission.decision_engine import mission_profiles

PROFILE_ID = "ROVER_EXPLORATION_V1"


def test_shackleton_score():

    result = calculate_site_score(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["overall_score"] == 100.0


def test_malapert_score():

    result = calculate_site_score(
        "MALAPERT_MASSIF",
        PROFILE_ID
    )

    assert result["overall_score"] == 98.39


def test_de_gerlache_score():

    result = calculate_site_score(
        "DE_GERLACHE_RIM",
        PROFILE_ID
    )

    assert result["overall_score"] == 90.83


def test_score_is_between_zero_and_hundred():

    result = calculate_site_score(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert 0 <= result["overall_score"] <= 100


def test_invalid_site_is_rejected():

    with pytest.raises(ValueError):

        calculate_site_score(
            "INVALID_SITE",
            PROFILE_ID
        )


def test_invalid_profile_is_rejected():

    with pytest.raises(ValueError):

        calculate_site_score(
            "SHACKLETON_RIM",
            "INVALID_PROFILE"
        )
@pytest.mark.parametrize(
    "requirement",
    [
        "minimum_sunlight_hours",
        "minimum_earth_visibility_hours",
        "minimum_solar_energy_wh",
        "maximum_slope_deg",
        "maximum_terrain_hazard_score"
    ]
        )
def test_zero_threshold_is_rejected_by_scoring_engine(
    monkeypatch,
    requirement
):

    invalid_profile = copy.deepcopy(
        mission_profiles.MISSION_PROFILES[PROFILE_ID]
    )

    invalid_profile["requirements"][requirement] = 0

    monkeypatch.setitem(
        mission_profiles.MISSION_PROFILES,
        PROFILE_ID,
        invalid_profile
   )
    with pytest.raises(ValueError):

        scoring_engine.calculate_site_score(
            "SHACKLETON_RIM",
            PROFILE_ID
        )