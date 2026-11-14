"""
Tests for LUNA-SCOPE Mission Assessment.
"""

import pytest

from app.mission.decision_engine.assessment import (
    assess_mission,
    classify_provenance
)
from copy import deepcopy

from app.mission.decision_engine import assessment
from app.mission.decision_engine.mock_data import LUNAR_SITES


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

def test_synthetic_data_provenance():

    result = assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "SYNTHETIC"


def test_verified_provenance(monkeypatch):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["data_source"] = "NASA Test Fixture"

    site["provenance"] = {
        "provider": "NASA",
        "product": "LOLA Test Fixture",
        "product_version": "1.0",
        "processing_lineage": ["Test processing step"],
        "verification_status": "VERIFIED",
        "quality_flags": []
    }

    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "VERIFIED"


def test_missing_provenance(monkeypatch):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site.pop("provenance", None)

    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "MISSING_PROVENANCE"


def test_unverified_provenance(monkeypatch):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["provenance"]["verification_status"] = "NOT_VERIFIED"
    site["provenance"]["quality_flags"] = []
    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "UNVERIFIED"


def test_unknown_data_status(monkeypatch):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "UNKNOWN_FUTURE_STATUS"

    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "UNKNOWN"
def test_assessment_calculates_feasibility_and_scoring_once(monkeypatch):

    call_counts = {
        "feasibility": 0,
        "scoring": 0
    }

    original_feasibility = assessment.check_feasibility
    original_scoring = assessment.calculate_site_score

    def counted_feasibility(*args, **kwargs):
        call_counts["feasibility"] += 1
        return original_feasibility(*args, **kwargs)

    def counted_scoring(*args, **kwargs):
        call_counts["scoring"] += 1
        return original_scoring(*args, **kwargs)

    monkeypatch.setattr(
        assessment,
        "check_feasibility",
        counted_feasibility
    )

    monkeypatch.setattr(
        assessment,
        "calculate_site_score",
        counted_scoring
    )

    assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert call_counts["feasibility"] == 1
    assert call_counts["scoring"] == 1
def test_assessment_does_not_repeat_calculations(monkeypatch):

    call_counts = {
        "feasibility": 0,
        "scoring": 0
    }

    original_feasibility = assessment.check_feasibility
    original_scoring = assessment.calculate_site_score

    def counted_feasibility(*args, **kwargs):
        call_counts["feasibility"] += 1
        return original_feasibility(*args, **kwargs)

    def counted_scoring(*args, **kwargs):
        call_counts["scoring"] += 1
        return original_scoring(*args, **kwargs)

    monkeypatch.setattr(
        assessment,
        "check_feasibility",
        counted_feasibility
    )

    monkeypatch.setattr(
        assessment,
        "calculate_site_score",
        counted_scoring
    )

    assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert call_counts["feasibility"] == 1
    assert call_counts["scoring"] == 1
def test_unknown_verification_status(monkeypatch):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["provenance"]["verification_status"] = "FUTURE_STATUS"
    site["provenance"]["quality_flags"] = []
    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "UNKNOWN"


def test_invalid_quality_flags_are_rejected_as_missing_provenance(
    monkeypatch
):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["provenance"]["quality_flags"] = "NOT_A_LIST"

    monkeypatch.setattr(
        assessment,
         "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert (
        result["data_quality"]["provenance_status"]
        == "MISSING_PROVENANCE"
    )
# --------------------------------------------------
# Final provenance quality-flag tests
# --------------------------------------------------

@pytest.mark.parametrize(
    "quality_flag",
    [
        "SYNTHETIC",
        "NOT_SCIENTIFIC_MEASUREMENTS"
    ]
)
def test_contradictory_quality_flags_prevent_verified_status(
    monkeypatch,
    quality_flag
):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["data_source"] = "NASA Test Fixture"

    site["provenance"]["verification_status"] = "VERIFIED"
    site["provenance"]["quality_flags"] = [quality_flag]

    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "SYNTHETIC"


def test_unknown_quality_flag_is_preserved(monkeypatch):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["data_source"] = "NASA Test Fixture"

    site["provenance"]["verification_status"] = "VERIFIED"
    site["provenance"]["quality_flags"] = [
        "FUTURE_QUALITY_FLAG"
    ]

    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "VERIFIED"

    assert (
        result["data_quality"]["unknown_quality_flags"]
        == ["FUTURE_QUALITY_FLAG"]
    )


def test_multiple_unknown_quality_flags_are_preserved(monkeypatch):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["data_source"] = "NASA Test Fixture"

    site["provenance"]["verification_status"] = "VERIFIED"
    site["provenance"]["quality_flags"] = [
        "FUTURE_FLAG_A",
        "FUTURE_FLAG_B"
    ]

    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["unknown_quality_flags"] == [
        "FUTURE_FLAG_A",
        "FUTURE_FLAG_B"
    ]


def test_known_and_unknown_quality_flags_are_both_handled(
    monkeypatch
):

    site = deepcopy(LUNAR_SITES["SHACKLETON_RIM"])

    site["data_status"] = "AVAILABLE"
    site["data_source"] = "NASA Test Fixture"

    site["provenance"]["verification_status"] = "VERIFIED"
    site["provenance"]["quality_flags"] = [
        "SYNTHETIC",
        "FUTURE_FLAG_A"
    ]

    monkeypatch.setattr(
        assessment,
        "get_lunar_site",
        lambda site_id: site
    )

    result = assessment.assess_mission(
        "SHACKLETON_RIM",
        PROFILE_ID
    )

    assert result["data_quality"]["provenance_status"] == "SYNTHETIC"

    assert result["data_quality"]["unknown_quality_flags"] == [
        "FUTURE_FLAG_A"
    ]
