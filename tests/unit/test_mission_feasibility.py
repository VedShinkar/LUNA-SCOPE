"""
Tests for LUNA-SCOPE Mission Feasibility Checker.
"""

import copy
import math
import pytest

from app.mission.decision_engine import feasibility
from app.mission.decision_engine.mock_data import LUNAR_SITES


PROFILE_ID = "ROVER_EXPLORATION_V1"


# --------------------------------------------------
# Existing feasibility tests
# --------------------------------------------------

def test_shackleton_is_feasible():

    result = feasibility.check_feasibility(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "FEASIBLE"
    assert len(result["failed_constraints"]) == 0


def test_malapert_is_not_feasible():

    result = feasibility.check_feasibility(
        "MALAPERT_MASSIF",
        PROFILE_ID
    )

    assert result["feasibility"] == "NOT_FEASIBLE"
    assert len(result["failed_constraints"]) == 2


def test_de_gerlache_is_not_feasible():

    result = feasibility.check_feasibility(
        "DE_GERLACHE_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "NOT_FEASIBLE"
    assert len(result["failed_constraints"]) == 3


def test_invalid_site_is_rejected():

    with pytest.raises(ValueError):

        feasibility.check_feasibility(
            "INVALID_SITE",
            PROFILE_ID
        )


def test_invalid_profile_is_rejected():

    with pytest.raises(ValueError):

        feasibility.check_feasibility(
            "SHACKLETON_RIM",
            "INVALID_PROFILE"
        )


# --------------------------------------------------
# Physical measurement validation tests
# --------------------------------------------------

@pytest.mark.parametrize(
    "field,value",
    [
        ("sunlight_hours", -10),
        ("earth_visibility_hours", -20),
        ("solar_energy_wh", -500),
        ("slope_deg", -5),
        ("slope_deg", 91),
        ("terrain_hazard_score", -0.1),
        ("terrain_hazard_score", 1.5),
    ]
)
def test_invalid_physical_measurements_are_rejected(
    monkeypatch,
    field,
    value
):

    site = copy.deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site[field] = value

    monkeypatch.setattr(
        feasibility,
        "get_lunar_site",
        lambda site_id: site
    )

    with pytest.raises(ValueError):

        feasibility.check_feasibility(
            "SHACKLETON_RIM",
            PROFILE_ID
        )


# --------------------------------------------------
# Non-finite measurement tests
# --------------------------------------------------

@pytest.mark.parametrize(
    "field,value",
    [
        ("sunlight_hours", math.nan),
        ("earth_visibility_hours", math.inf),
        ("solar_energy_wh", -math.inf),
        ("slope_deg", math.nan),
        ("terrain_hazard_score", math.inf),
    ]
)
def test_non_finite_measurements_are_rejected(
    monkeypatch,
    field,
    value
):

    site = copy.deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site[field] = value

    monkeypatch.setattr(
        feasibility,
        "get_lunar_site",
        lambda site_id: site
    )

    with pytest.raises(ValueError):

        feasibility.check_feasibility(
            "SHACKLETON_RIM",
            PROFILE_ID
        )


# --------------------------------------------------
# Missing measurement tests
# --------------------------------------------------

def test_missing_measurement_returns_insufficient_data(
    monkeypatch
):

    site = copy.deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["sunlight_hours"] = None

    monkeypatch.setattr(
        feasibility,
        "get_lunar_site",
        lambda site_id: site
    )

    result = feasibility.check_feasibility(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "INSUFFICIENT_DATA"

    assert "minimum_sunlight_hours" in result["missing_inputs"]


@pytest.mark.parametrize(
    "field",
    [
        "sunlight_hours",
        "earth_visibility_hours",
        "solar_energy_wh",
        "slope_deg",
        "terrain_hazard_score"
    ]
)
def test_each_missing_measurement_is_reported(
    monkeypatch,
    field
):

    site = copy.deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site[field] = None

    monkeypatch.setattr(
        feasibility,
        "get_lunar_site",
        lambda site_id: site
    )

    result = feasibility.check_feasibility(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "INSUFFICIENT_DATA"
    assert result["missing_inputs"]


# --------------------------------------------------
# Non-numeric measurement tests
# --------------------------------------------------

@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        True
    ]
)
def test_non_numeric_measurements_are_rejected(
    monkeypatch,
    value
):

    site = copy.deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["sunlight_hours"] = value

    monkeypatch.setattr(
        feasibility,
        "get_lunar_site",
        lambda site_id: site
    )

    with pytest.raises(ValueError):

        feasibility.check_feasibility(
            "SHACKLETON_RIM",
            PROFILE_ID
        )
# --------------------------------------------------
# Mixed missing-data and failed-constraint tests
# --------------------------------------------------

def test_known_constraint_failure_takes_priority_over_missing_data(
    monkeypatch
):
    site = copy.deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    profile = feasibility.get_mission_profile(PROFILE_ID)

    # Make the slope exceed the mission's permitted maximum.
    maximum_slope = profile["requirements"]["maximum_slope_deg"]
    site["slope_deg"] = maximum_slope + 1

    # Remove sunlight data.
    site["sunlight_hours"] = None

    monkeypatch.setattr(
        feasibility,
        "get_lunar_site",
        lambda site_id: site
    )

    result = feasibility.check_feasibility(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    # A confirmed mandatory failure takes priority.
    assert result["feasibility"] == "NOT_FEASIBLE"

    # The failed slope constraint must still be reported.
    assert any(
        item["requirement"] == "maximum_slope_deg"
        for item in result["failed_constraints"]
    )

    # Missing sunlight data must also be preserved.
    assert "minimum_sunlight_hours" in result["missing_inputs"]