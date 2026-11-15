"""Integration tests: real-data Mission Intelligence and AI Copilot pipeline.

All tests use deterministic mocks. These mocks replace only the boundary
calls that require real LOLA rasters or SPICE kernels; production logic
in the adapter, engine, and copilot is exercised unchanged.

TEST FIXTURE LABEL: Every mock in this module is explicitly labelled
  MOCK_TEST_FIXTURE to prevent it from silently entering production paths.

Tested properties
-----------------
1.  Real terrain values reach Mission Intelligence (via adapter).
2.  Illumination summary reaches the illumination criterion.
3.  Communication summary reaches the communication criterion.
4.  Multi-site comparison uses the same real-data pipeline.
5.  Copilot assessment returns the same evidence as Mission Intelligence.
6.  Missing data produces INSUFFICIENT_DATA.
7.  Synthetic fixtures cannot silently enter a real-data assessment
    (SYNTHETIC_EXAMPLE status propagates to overall_data_status).
8.  Provisional Horizons/SPICE validation is never presented as
    completed live NASA validation (PROVISIONAL label is preserved).
9.  Existing terrain unit tests are not broken (import-level smoke test).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared datetime fixtures
# ---------------------------------------------------------------------------

START_UTC = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_UTC = datetime(2025, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
STEP_S = 3600

# ---------------------------------------------------------------------------
# Terrain mock data — MOCK_TEST_FIXTURE
# ---------------------------------------------------------------------------

_MOCK_TERRAIN_RESULT = {
    "site_id": "Site04",
    "within_bounds": True,
    "is_valid": True,
    "elevation_m": -3200.5,
    "slope_deg": 8.4,
    "aspect_deg": 45.0,
    "aspect_description": "Clockwise from grid North.",
    "roughness": {
        "roughness_15m_m": 0.12,
        "roughness_35m_m": 0.21,
        "roughness_75m_m": 0.38,
        "scale_classification": "provisional_analytical_scales",
        "metric": "unbiased_sample_elevation_standard_deviation_ddof1",
    },
    "hazard_classification": {
        "physical_hazard_class": "LOW",
        "physical_hazard_code": 1,
        "epistemic_quality_class": "LOW",
        "epistemic_quality_code": 1,
        "combined_screening_class": "LOW",
        "combined_screening_code": 1,
        "policy": "Option B: Decoupled Decisional Screening",
    },
    "uncertainty_and_observation": {
        "lola_observation_count": 3,
        "elevation_uncertainty_m_rms": 0.05,
        "slope_uncertainty_deg_rms": 0.3,
        "is_interpolated": False,
        "is_direct_observation": True,
    },
    "provenance": {
        "source_dataset": "NASA LOLA 5m South Polar PGDA (Site04: Shackleton Crater Rim)",
        "dem_product_id": "Site04_final_adj_5mpp_surf",
        "grid_resolution_m": [5.0, 5.0],
        "vertical_datum": "1737.4 km lunar spherical datum",
        "evidence_class": "DIRECT_OBSERVATION",
    },
    "raster_indices": {"col": 160, "row": 160},
    "coordinates": {"easting_m": 1000.0, "northing_m": 2000.0,
                    "coordinate_system": "Lunar South-Polar Stereographic",
                    "reference_frame": "MOON_ME associated with DE421 ephemeris"},
}

# ---------------------------------------------------------------------------
# Illumination mock data — MOCK_TEST_FIXTURE
# ---------------------------------------------------------------------------

_MOCK_ILLUMINATION_RESULT = {
    "site_id": "Site04",
    "terrain": {"file": "Site04_processed_elevation.tif", "source_url": "https://example.test",
                "source_dem_sha256": "abc123", "resolution_m": (5.0, 5.0), "datum": "...",
                "frame": "MOON_ME (DE421)", "bounds_m": (900.0, 1900.0, 1100.0, 2100.0),
                "affine": [5.0, 0.0, 900.0, 0.0, -5.0, 2100.0], "shape": (40, 40),
                "rms_source_url": None},
    "celestial": {"source": "Phase 3.1 JPL DE440s", "conventions": {}, "kernels": []},
    "method": {"name": "Great-circle native LOLA radial-cell solar centre ray",
               "grazing_tolerance_deg": 0.5, "radial_ceiling_m": 1737400.0,
               "maximum_trace_distance_m": 5000.0,
               "solar_disc": "Solar angular radius reported; centre ray only.",
               "rms": "Opposite ±1 RMS height scenarios; sensitivity indicator, not confidence bounds."},
    "classification": {"illuminated": "...", "shadowed": "...", "unknown": "...",
                       "invalid": "...", "clear": "..."},
    "quality_flags": ["finite_terrain_extent", "solar_centre_only", "native_raster_model",
                      "earth_occultation_not_modelled"],
    "observer": {"site_id": "Site04", "latitude_deg": -89.9, "longitude_deg_east": 10.0,
                 "elevation_m": -3200.5, "easting_m": 1000.0, "northing_m": 2000.0,
                 "source_pixel_row": 20, "source_pixel_column": 20,
                 "source_url": "https://example.test", "source_file": "Site04.tif",
                 "source_dem_sha256": "abc123", "placement": "raster centre"},
    "requested_point_m": None,
    "samples": [],
    "counts": {"illuminated": 5, "shadowed": 1, "unknown": 0, "invalid": 0,
               "valid_samples": 6, "classified": 6},
    "summary": {
        "duration_s": {"illuminated": 18000.0, "shadowed": 3600.0, "unknown": 0.0},
        "longest_clear_s": 18000.0,
        "longest_shadow_s": 3600.0,
        "fraction_known_time_clear": 0.833,
        "transitions": [],
        "gap_count": 0,
        "gaps": [],
        "intervals": [],
    },
    "native_summary": {},
}

# ---------------------------------------------------------------------------
# Communication mock data — MOCK_TEST_FIXTURE
# ---------------------------------------------------------------------------

_MOCK_COMM_RESULT = {
    "site_id": "Site04",
    "terrain": _MOCK_ILLUMINATION_RESULT["terrain"],
    "celestial": _MOCK_ILLUMINATION_RESULT["celestial"],
    "method": {"name": "Native LOLA spherical cell Earth visibility",
               "grazing_tolerance_deg": 0.5, "radial_ceiling_m": 1737400.0,
               "maximum_trace_distance_m": 5000.0, "rim_rays": 64,
               "rms": "Opposite ±1 RMS height scenarios."},
    "antenna_min_elevation_deg": 0.0,
    "criterion": "centre",
    "quality_flags": ["geometric_visibility_only", "finite_terrain_extent",
                      "spherical_earth_disc", "nominal_native_cell_model"],
    "observer": _MOCK_ILLUMINATION_RESULT["observer"],
    "requested_point_m": None,
    "samples": [],
    "summary": {
        "duration_s": {"visible": 14400.0, "obstructed": 7200.0, "unresolved": 0.0},
        "longest_visible_s": 14400.0,
        "longest_interruption_s": 7200.0,
        "fraction_classified_time_visible": 0.667,
        "transitions": [],
        "intervals": [],
    },
    "requested_sample_count": 7,
    "refinement_sample_count": 0,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_service_with_query_result(result: dict) -> MagicMock:
    """Return a mock TerrainService whose query_point returns *result*."""
    mock = MagicMock()
    mock._meta = MagicMock()
    mock._meta.bounds = (900.0, 1900.0, 1100.0, 2100.0)
    mock.query_point.return_value = result
    return mock


# ===========================================================================
# Test 1 — Real terrain values reach Mission Intelligence
# ===========================================================================

class TestTerrainReachesMissionIntelligence:
    def test_slope_from_terrain_reaches_criterion(self):
        """Terrain slope from the scientific engine populates the criterion."""
        with patch(
            "app.mission.decision_engine.adapter.TerrainService.get_instance",
            return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
        ):
            from app.mission.decision_engine.engine import assess_site

            result = assess_site("SHACKLETON_RIM")

        slope_criterion = next(c for c in result.criteria if c.criterion == "terrain_slope")
        # The mock returns slope_deg=8.4; score must be derived from it.
        assert slope_criterion.value == pytest.approx(8.4)
        assert slope_criterion.score is not None
        assert 0.0 <= slope_criterion.score <= 1.0
        assert slope_criterion.data_status == "VERIFIED_SOURCE"

    def test_roughness_from_terrain_reaches_criterion(self):
        with patch(
            "app.mission.decision_engine.adapter.TerrainService.get_instance",
            return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
        ):
            from app.mission.decision_engine.engine import assess_site

            result = assess_site("SHACKLETON_RIM")

        roughness_criterion = next(
            c for c in result.criteria if c.criterion == "terrain_roughness_15m"
        )
        assert roughness_criterion.value == pytest.approx(0.12)
        assert roughness_criterion.score is not None


# ===========================================================================
# Test 2 — Illumination result reaches illumination criterion
# ===========================================================================

class TestIlluminationReachesCriterion:
    def test_illumination_fraction_propagates(self):
        with (
            patch(
                "app.mission.decision_engine.adapter.TerrainService.get_instance",
                return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
            ),
            patch(
                "app.mission.decision_engine.adapter.observer_analysis",
                return_value=_MOCK_ILLUMINATION_RESULT,
            ) as mock_illum,
        ):
            from app.mission.decision_engine.engine import assess_site

            result = assess_site("SHACKLETON_RIM", START_UTC, END_UTC, STEP_S)

        illum_criterion = next(
            c for c in result.criteria if c.criterion == "illumination_fraction"
        )
        assert illum_criterion.value == pytest.approx(0.833)
        assert illum_criterion.score == pytest.approx(0.833)
        # Engine is PROVISIONAL due to solar_centre_only flag.
        assert illum_criterion.data_status == "PROVISIONAL"


# ===========================================================================
# Test 3 — Communication result reaches communication criterion
# ===========================================================================

class TestCommunicationReachesCriterion:
    def test_communication_fraction_propagates(self):
        with (
            patch(
                "app.mission.decision_engine.adapter.TerrainService.get_instance",
                return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
            ),
            patch(
                "app.mission.decision_engine.adapter.observer_analysis",
                return_value=_MOCK_ILLUMINATION_RESULT,
            ),
            patch(
                "app.mission.decision_engine.adapter.comm_analysis",
                return_value=_MOCK_COMM_RESULT,
            ),
        ):
            from app.mission.decision_engine.engine import assess_site

            result = assess_site("SHACKLETON_RIM", START_UTC, END_UTC, STEP_S)

        comm_criterion = next(
            c for c in result.criteria
            if c.criterion == "communication_visibility_fraction"
        )
        assert comm_criterion.value == pytest.approx(0.667)
        assert comm_criterion.score == pytest.approx(0.667)
        assert comm_criterion.data_status == "PROVISIONAL"


# ===========================================================================
# Test 4 — Multi-site comparison uses the same real-data pipeline
# ===========================================================================

class TestMultiSiteComparisonPipeline:
    def test_all_three_sites_use_same_pipeline(self):
        mock_service = _mock_service_with_query_result(_MOCK_TERRAIN_RESULT)
        with patch(
            "app.mission.decision_engine.adapter.TerrainService.get_instance",
            return_value=mock_service,
        ):
            from app.mission.decision_engine.engine import compare_sites

            results = compare_sites(
                ["SHACKLETON_RIM", "DE_GERLACHE_RIM", "MALAPERT_MASSIF"]
            )

        assert set(results) == {"SHACKLETON_RIM", "DE_GERLACHE_RIM", "MALAPERT_MASSIF"}
        for site_id, assessment in results.items():
            assert assessment.assessment_label == "PRELIMINARY"
            assert assessment.mission_site_id == site_id
            # Same mock data → same slope value for each site.
            slope_c = next(c for c in assessment.criteria if c.criterion == "terrain_slope")
            assert slope_c.value == pytest.approx(8.4)


# ===========================================================================
# Test 5 — Copilot assessment returns the same evidence as Mission Intelligence
# ===========================================================================

class TestCopilotMatchesMissionIntelligence:
    def test_copilot_site_assessment_matches_engine(self):
        mock_service = _mock_service_with_query_result(_MOCK_TERRAIN_RESULT)
        with patch(
            "app.mission.decision_engine.adapter.TerrainService.get_instance",
            return_value=mock_service,
        ):
            from app.ai_copilot.copilot import site_assessment_response
            from app.mission.decision_engine.engine import assess_site

            engine_result = assess_site("SHACKLETON_RIM")
            copilot_result = site_assessment_response("SHACKLETON_RIM")

        engine_slope = next(
            c for c in engine_result.criteria if c.criterion == "terrain_slope"
        )
        copilot_assessment = copilot_result.assessments["SHACKLETON_RIM"]
        copilot_slope = next(
            c for c in copilot_assessment["criteria"] if c["criterion"] == "terrain_slope"
        )

        # Both must derive the same score from the same underlying value.
        assert copilot_slope["value"] == pytest.approx(engine_slope.value)
        assert copilot_slope["score"] == pytest.approx(engine_slope.score)
        assert copilot_result.query_type == "site_assessment"
        assert "terrain" in copilot_result.evidence


# ===========================================================================
# Test 6 — Missing data produces INSUFFICIENT_DATA
# ===========================================================================

class TestMissingDataProducesInsufficientData:
    def test_terrain_unavailable_gives_insufficient_data(self):
        from app.scientific_engines.ephemeris.observer import ObserverUnavailable

        with patch(
            "app.mission.decision_engine.adapter.TerrainService.get_instance",
            side_effect=ObserverUnavailable("MOCK_TEST_FIXTURE: terrain files absent"),
        ):
            from app.mission.decision_engine.adapter import get_terrain

            result = get_terrain("SHACKLETON_RIM")

        assert result.data_status == "INSUFFICIENT_DATA"
        assert result.elevation_m is None
        assert result.slope_deg is None
        assert "MOCK_TEST_FIXTURE" in result.error

    def test_assessment_with_no_time_window_marks_temporal_criteria_insufficient(self):
        with patch(
            "app.mission.decision_engine.adapter.TerrainService.get_instance",
            return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
        ):
            from app.mission.decision_engine.engine import assess_site

            result = assess_site("SHACKLETON_RIM")  # No start/end

        illum_c = next(c for c in result.criteria if c.criterion == "illumination_fraction")
        comm_c = next(
            c for c in result.criteria if c.criterion == "communication_visibility_fraction"
        )
        assert illum_c.data_status == "INSUFFICIENT_DATA"
        assert illum_c.score is None
        assert comm_c.data_status == "INSUFFICIENT_DATA"
        assert comm_c.score is None
        assert "illumination_fraction" in result.missing_criteria
        assert "communication_visibility_fraction" in result.missing_criteria


# ===========================================================================
# Test 7 — Synthetic fixtures cannot silently enter a real-data assessment
# ===========================================================================

class TestSyntheticFixturesDoNotEnterAssessment:
    def test_synthetic_status_propagates_to_overall(self):
        """If any criterion carries SYNTHETIC_EXAMPLE, overall reflects it."""
        from app.mission.decision_engine.engine import (
            CriterionResult,
            SiteAssessment,
            _aggregate_status,
        )

        statuses = [
            "VERIFIED_SOURCE",
            "PROVISIONAL",
            "SYNTHETIC_EXAMPLE",    # ← injected synthetic
        ]
        overall = _aggregate_status(*statuses)
        # SYNTHETIC_EXAMPLE is less certain than PROVISIONAL.
        assert overall == "SYNTHETIC_EXAMPLE"

    def test_assessment_label_always_preliminary(self):
        with patch(
            "app.mission.decision_engine.adapter.TerrainService.get_instance",
            return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
        ):
            from app.mission.decision_engine.engine import assess_site

            result = assess_site("MALAPERT_MASSIF")

        assert result.assessment_label == "PRELIMINARY"


# ===========================================================================
# Test 8 — Provisional validation is not presented as completed NASA validation
# ===========================================================================

class TestProvisionalLabelPreserved:
    def test_illumination_data_status_is_provisional_not_verified(self):
        """The illumination engine sets solar_centre_only → PROVISIONAL, not VERIFIED."""
        with (
            patch(
                "app.mission.decision_engine.adapter.TerrainService.get_instance",
                return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
            ),
            patch(
                "app.mission.decision_engine.adapter.observer_analysis",
                return_value=_MOCK_ILLUMINATION_RESULT,
            ),
        ):
            from app.mission.decision_engine.adapter import get_illumination

            result = get_illumination("SHACKLETON_RIM", START_UTC, END_UTC)

        assert result.data_status == "PROVISIONAL"
        # Confirm the provisional flag is in the quality flags.
        assert "solar_centre_only" in result.quality_flags

    def test_communication_data_status_is_provisional_not_verified(self):
        with (
            patch(
                "app.mission.decision_engine.adapter.TerrainService.get_instance",
                return_value=_mock_service_with_query_result(_MOCK_TERRAIN_RESULT),
            ),
            patch(
                "app.mission.decision_engine.adapter.comm_analysis",
                return_value=_MOCK_COMM_RESULT,
            ),
        ):
            from app.mission.decision_engine.adapter import get_communication

            result = get_communication("SHACKLETON_RIM", START_UTC, END_UTC)

        assert result.data_status == "PROVISIONAL"
        assert "geometric_visibility_only" in result.quality_flags

    def test_copilot_communication_response_includes_link_budget_disclaimer(self):
        with patch(
            "app.mission.decision_engine.adapter.comm_analysis",
            return_value=_MOCK_COMM_RESULT,
        ):
            from app.ai_copilot.copilot import communication_query_response

            resp = communication_query_response("SHACKLETON_RIM", START_UTC, END_UTC)

        # Limitation must state this is NOT a confirmed link budget.
        assert any("link" in note.lower() or "link budget" in note.lower()
                   or "geometric" in note.lower()
                   for note in resp.limitations)


# ===========================================================================
# Test 9 — Existing tests smoke-import without breakage
# ===========================================================================

class TestExistingTestSuiteIntegrity:
    def test_terrain_service_module_still_importable(self):
        """Importing the terrain service must not raise after our additions."""
        import app.scientific_engines.terrain.service  # noqa: F401

    def test_catalog_module_still_importable(self):
        import app.scientific_engines.terrain.catalog  # noqa: F401

    def test_decision_engine_adapter_importable(self):
        import app.mission.decision_engine.adapter  # noqa: F401

    def test_decision_engine_engine_importable(self):
        import app.mission.decision_engine.engine  # noqa: F401

    def test_copilot_importable(self):
        import app.ai_copilot.copilot  # noqa: F401

    def test_site_map_covers_all_three_sites(self):
        from app.mission.decision_engine.adapter import SITE_MAP

        assert "SHACKLETON_RIM" in SITE_MAP
        assert "DE_GERLACHE_RIM" in SITE_MAP
        assert "MALAPERT_MASSIF" in SITE_MAP
        assert SITE_MAP["SHACKLETON_RIM"] == "Site04"
        assert SITE_MAP["DE_GERLACHE_RIM"] == "Site11"
        assert SITE_MAP["MALAPERT_MASSIF"] == "Site23"
