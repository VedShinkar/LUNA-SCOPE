import pytest
import copy

from app.mission.decision_engine.mission_profiles import (
    MISSION_PROFILES,
    get_mission_profile,
    validate_weights,
    validate_mission_profile
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
# --------------------------------------------------
# Additional Mission Profile Validation Tests
# --------------------------------------------------


# Test 6: Missing weight key
def test_missing_weight_key_rejected():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    del profile["weights"]["terrain"]

    with pytest.raises(ValueError):
        validate_weights(profile)


# Test 7: Extra weight key
def test_extra_weight_key_rejected():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["weights"]["extra_weight"] = 0.1

    with pytest.raises(ValueError):
        validate_weights(profile)


# Test 8: Negative weight
def test_negative_weight_rejected():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["weights"]["solar_energy"] = -0.1

    with pytest.raises(ValueError):
        validate_weights(profile)


# Test 9: Boolean weight
def test_boolean_weight_rejected():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["weights"]["solar_energy"] = True

    with pytest.raises(ValueError):
        validate_weights(profile)


# Test 10: NaN and infinity weights
@pytest.mark.parametrize("invalid_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_weight_rejected(invalid_value):

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["weights"]["solar_energy"] = invalid_value

    with pytest.raises(ValueError):
        validate_weights(profile)


# Test 11: Missing requirement key
def test_missing_requirement_key_rejected():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    del profile["requirements"]["minimum_sunlight_hours"]

    with pytest.raises(ValueError):
        validate_mission_profile(profile)


# Test 12: Extra requirement key
def test_extra_requirement_key_rejected():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["requirements"]["extra_requirement"] = 10

    with pytest.raises(ValueError):
        validate_mission_profile(profile)


# Test 13: Boolean requirement
def test_boolean_requirement_rejected():

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["requirements"]["minimum_sunlight_hours"] = True

    with pytest.raises(ValueError):
        validate_mission_profile(profile)


# Test 14: Non-finite requirements
@pytest.mark.parametrize(
    "invalid_value",
    [float("nan"), float("inf"), float("-inf")]
)
def test_non_finite_requirement_rejected(invalid_value):

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["requirements"]["minimum_sunlight_hours"] = invalid_value

    with pytest.raises(ValueError):
        validate_mission_profile(profile)


# Test 15: Zero and negative thresholds
@pytest.mark.parametrize(
    "invalid_value",
    [0, -1]
)
def test_zero_and_negative_thresholds_rejected(invalid_value):

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["requirements"]["minimum_sunlight_hours"] = invalid_value

    with pytest.raises(ValueError):
        validate_mission_profile(profile)


# Test 16: Invalid slope range
@pytest.mark.parametrize(
    "invalid_value",
    [-1, 91]
)
def test_invalid_slope_range_rejected(invalid_value):

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["requirements"]["maximum_slope_deg"] = invalid_value

    with pytest.raises(ValueError):
        validate_mission_profile(profile)


# Test 17: Invalid terrain hazard range
@pytest.mark.parametrize(
    "invalid_value",
    [-0.1, 1.1]
)
def test_invalid_hazard_range_rejected(invalid_value):

    profile = copy.deepcopy(
        get_mission_profile("ROVER_EXPLORATION_V1")
    )

    profile["requirements"]["maximum_terrain_hazard_score"] = invalid_value

    with pytest.raises(ValueError):
        validate_mission_profile(profile)
def test_mission_profile_returns_independent_copy():

    profile = get_mission_profile("ROVER_EXPLORATION_V1")

    profile["weights"]["solar_energy"] = 0.99

    original_profile = get_mission_profile("ROVER_EXPLORATION_V1")

    assert original_profile["weights"]["solar_energy"] == 0.30