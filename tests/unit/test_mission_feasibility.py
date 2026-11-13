"""
Tests for LUNA-SCOPE Mission Feasibility Checker.
"""

import pytest

from app.mission.decision_engine.feasibility import check_feasibility


PROFILE_ID = "ROVER_EXPLORATION_V1"


def test_shackleton_is_feasible():

    result = check_feasibility(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "FEASIBLE"
    assert len(result["failed_constraints"]) == 0


def test_malapert_is_not_feasible():

    result = check_feasibility(
        "MALAPERT_MASSIF",
        PROFILE_ID
    )

    assert result["feasibility"] == "NOT_FEASIBLE"
    assert len(result["failed_constraints"]) == 2


def test_de_gerlache_is_not_feasible():

    result = check_feasibility(
        "DE_GERLACHE_RIM",
        PROFILE_ID
    )

    assert result["feasibility"] == "NOT_FEASIBLE"
    assert len(result["failed_constraints"]) == 3


def test_invalid_site_is_rejected():

    with pytest.raises(ValueError):

        check_feasibility(
            "INVALID_SITE",
            PROFILE_ID
        )


def test_invalid_profile_is_rejected():

    with pytest.raises(ValueError):

        check_feasibility(
            "SHACKLETON_RIM",
            "INVALID_PROFILE"
        )