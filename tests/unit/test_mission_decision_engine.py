import pytest
import copy

from app.mission.decision_engine.mission_profiles import (
    MISSION_PROFILES,
    get_mission_profile,
    validate_weights
)


# TEST 1: Check whether the mission profile exists
def test_mission_profile_exists():

    profile = get_mission_profile("ROVER_EXPLORATION_V1")

    assert profile is not None
    assert profile["mission_name"] == "Lunar Rover Exploration"


# TEST 2: Check mission requirements
def test_mission_requirements():

    profile = get_mission_profile("ROVER_EXPLORATION_V1")

    requirements = profile["requirements"]

    assert requirements["minimum_sunlight_hours"] == 100
    assert requirements["minimum_earth_visibility_hours"] == 120
    assert requirements["minimum_solar_energy_wh"] == 700


# TEST 3: Check whether scoring weights add up to 1.0
def test_scoring_weights_are_valid():

    profile = get_mission_profile("ROVER_EXPLORATION_V1")

    assert validate_weights(profile) is True


# TEST 4: Check invalid mission profile
def test_invalid_mission_profile():

    with pytest.raises(ValueError):

        get_mission_profile("UNKNOWN_MISSION")


# TEST 5: Check invalid scoring weights
def test_invalid_scoring_weights():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["weights"]["solar_energy"] = 0.8

    with pytest.raises(ValueError):

        validate_weights(profile)