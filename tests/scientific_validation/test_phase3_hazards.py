"""Phase 3 Terrain Hazard Screening – Scientific Validation Tests.

Validates Option B: Decoupled Decisional Screening.
Tests cover:
  1. Decoupled physical hazard vs epistemic quality representation.
  2. Observation coverage: LDEC=0 is INTERPOLATED (code 3), LDEC>0 is DIRECT OBSERVATION (codes 1 & 2),
     missing LDEC is UNKNOWN (code 0). Missing LDEC is distinct from LDEC=0.
  3. Interpolated steep terrain (slope > 15 deg) remains HIGH (3).
  4. Interpolated moderate terrain (slope 5-15 deg) remains MODERATE (2).
  5. Interpolated low-hazard terrain (slope <= 5 deg, LDEC=0) becomes UNKNOWN (0).
  6. Directly observed low-hazard terrain (slope <= 5 deg, LDEC>0, uncertainty acceptable) becomes LOW (1).
  7. Missing critical physical indicators do not become LOW:
     - Missing indicator without HIGH/MOD remains UNKNOWN (0).
     - Missing indicator with independent HIGH remains HIGH (3).
     - Missing indicator with independent MODERATE remains MODERATE (2).
  8. Class 0 remains distinct from NoData 255 in GeoTIFF outputs.
  9. Threshold boundaries, units, NaN handling.
  10. JSON report completeness and Option B documentation.
"""

from pathlib import Path
import json

import numpy as np
import pytest
import rasterio

from app.scientific_engines.terrain.loader import (
    SiteTerrainDataset,
    TerrainRaster,
    TerrainRasterMetadata,
)
from app.scientific_engines.terrain.hazards import (
    SEVERITY_TO_CODE,
    CODE_TO_SEVERITY,
    HAZARD_THRESHOLDS,
    PHYSICAL_HAZARD_KEYS,
    DATA_QUALITY_KEYS,
    classify_increasing,
    classify_observation_coverage,
    combine_hazard_screening,
    generate_hazard_screening,
    write_indicator_geotiff,
)


# ─── Helpers ────────────────────────────────────────────────────────────────
LUNAR_WKT = (
    'PROJCS["Lunar South-Polar Stereographic",'
    'GEOGCS["Moon 2000",'
    'DATUM["Moon 2000",SPHEROID["Moon",1737400,0]],'
    'PRIMEM["Greenwich",0],UNIT["metre",1]],'
    'PROJECTION["Polar_Stereographic"],'
    'PARAMETER["latitude_of_origin",-90],'
    'PARAMETER["central_meridian",0],'
    'PARAMETER["scale_factor",1],'
    'PARAMETER["false_easting",0],'
    'PARAMETER["false_northing",0],'
    'UNIT["metre",1]]'
)


def _meta(shape=(20, 20)):
    h, w = shape
    return TerrainRasterMetadata(
        file_name="dummy.tif",
        file_path="/tmp/dummy.tif",
        file_size_bytes=0,
        sha256_hash="",
        is_valid_tiff_header=True,
        width=w,
        height=h,
        band_count=1,
        dtype="float32",
        nodata=float("nan"),
        crs_wkt=LUNAR_WKT,
        crs_proj4="",
        is_lunar_crs=True,
        is_terrestrial_epsg=False,
        epsg_code=None,
        transform=(5.0, 0.0, -9000.0, 0.0, -5.0, 1000.0),
        resolution=(5.0, 5.0),
        bounds=(-9000.0, 1000.0 - h * 5.0, -9000.0 + w * 5.0, 1000.0),
        tags={},
    )


def _make_dataset(
    shape=(20, 20),
    slope_val=3.0,
    elev_unc_val=0.3,
    slope_unc_val=0.3,
    ldec_val=15.0,
):
    """Build a synthetic SiteTerrainDataset with uniform flat DEM."""
    meta = _meta(shape)
    # Uniform base DEM so local roughness standard deviation is 0.0m (LOW)
    dem = np.full(shape, -6000.0, dtype=np.float32)
    slope = np.full(shape, slope_val, dtype=np.float32)
    elev_unc = np.full(shape, elev_unc_val, dtype=np.float32)
    slope_unc = np.full(shape, slope_unc_val, dtype=np.float32)
    ldec = np.full(shape, ldec_val, dtype=np.float32)
    rasters = {
        "elevation": TerrainRaster(key="elevation", metadata=meta, data=dem),
        "slope": TerrainRaster(key="slope", metadata=meta, data=slope),
        "elevation_uncertainty": TerrainRaster(key="elevation_uncertainty", metadata=meta, data=elev_unc),
        "slope_uncertainty": TerrainRaster(key="slope_uncertainty", metadata=meta, data=slope_unc),
        "observation_count": TerrainRaster(key="observation_count", metadata=meta, data=ldec),
    }
    return SiteTerrainDataset(site_id="Site04", site_dir=Path("/tmp"), rasters=rasters)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Observation Coverage & Quality Decoupling Tests
# ═══════════════════════════════════════════════════════════════════════════
class TestObservationCoverageDecoupling:
    """Requirement 2: LDEC=0 is INTERPOLATED (code 3), LDEC>0 is DIRECT (1 or 2), missing is UNKNOWN (0)."""

    def test_ldec_zero_is_interpolated_high_epistemic_concern(self):
        arr = np.array([0.0, 0.0], dtype=np.float32)
        result = classify_observation_coverage(arr)
        # LDEC = 0 represents interpolated terrain -> HIGH epistemic concern (code 3)
        assert np.all(result == SEVERITY_TO_CODE["HIGH"])

    def test_missing_ldec_nan_is_unknown(self):
        arr = np.array([np.nan], dtype=np.float32)
        result = classify_observation_coverage(arr)
        # Missing LDEC is UNKNOWN (code 0)
        assert result[0] == SEVERITY_TO_CODE["UNKNOWN"]

    def test_negative_invalid_ldec_is_unknown(self):
        arr = np.array([-1.0], dtype=np.float32)
        result = classify_observation_coverage(arr)
        assert result[0] == SEVERITY_TO_CODE["UNKNOWN"]

    def test_missing_ldec_is_strictly_distinct_from_ldec_zero(self):
        nan_result = classify_observation_coverage(np.array([np.nan], dtype=np.float32))
        zero_result = classify_observation_coverage(np.array([0.0], dtype=np.float32))
        assert nan_result[0] != zero_result[0]
        assert nan_result[0] == SEVERITY_TO_CODE["UNKNOWN"]  # 0
        assert zero_result[0] == SEVERITY_TO_CODE["HIGH"]    # 3 (INTERPOLATED)

    def test_ldec_single_shot_is_moderate_concern(self):
        arr = np.array([1.0], dtype=np.float32)
        result = classify_observation_coverage(arr)
        assert result[0] == SEVERITY_TO_CODE["MODERATE"]  # 2

    def test_ldec_multi_shot_is_low_concern_confident(self):
        arr = np.array([2.0, 5.0, 20.0], dtype=np.float32)
        result = classify_observation_coverage(arr)
        assert np.all(result == SEVERITY_TO_CODE["LOW"])  # 1

    def test_observation_coverage_is_in_data_quality_domain(self):
        assert "observation_coverage" in DATA_QUALITY_KEYS
        assert "observation_coverage" not in PHYSICAL_HAZARD_KEYS


# ═══════════════════════════════════════════════════════════════════════════
# 2. Option B: Decoupled Decisional Screening Combination Tests
# ═══════════════════════════════════════════════════════════════════════════
class TestOptionBCombinedClassification:
    """Requirement 3 & 5: Combined classification rules."""

    def test_interpolated_steep_terrain_remains_high(self, tmp_path):
        """Rule 1: Known HIGH physical hazard remains HIGH regardless of LDEC=0."""
        ds = _make_dataset(slope_val=35.0, ldec_val=0.0)
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        assert np.all(combined == SEVERITY_TO_CODE["HIGH"])

    def test_interpolated_moderate_terrain_remains_moderate(self, tmp_path):
        """Rule 2: Known MODERATE physical hazard remains MODERATE regardless of LDEC=0."""
        ds = _make_dataset(slope_val=10.0, ldec_val=0.0)
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        assert np.all(combined == SEVERITY_TO_CODE["MODERATE"])

    def test_interpolated_low_hazard_terrain_does_not_become_low(self, tmp_path):
        """Rule 4: LOW physical hazard with LDEC=0 (interpolated) becomes UNKNOWN."""
        ds = _make_dataset(slope_val=2.0, ldec_val=0.0)
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        # Cannot certify LOW without direct observation evidence
        assert np.all(combined == SEVERITY_TO_CODE["UNKNOWN"])

    def test_directly_observed_low_hazard_terrain_becomes_low(self, tmp_path):
        """Rule 3: Directly observed low hazard becomes LOW when uncertainty criteria pass."""
        ds = _make_dataset(slope_val=2.0, ldec_val=5.0, elev_unc_val=0.2, slope_unc_val=0.4)
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        assert np.all(combined == SEVERITY_TO_CODE["LOW"])

    def test_directly_observed_low_slope_with_high_uncertainty_becomes_unknown(self, tmp_path):
        """Rule 4: LOW physical hazard with high slope uncertainty (> 1.5 deg) becomes UNKNOWN."""
        ds = _make_dataset(slope_val=2.0, ldec_val=5.0, elev_unc_val=0.2, slope_unc_val=3.5)
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        # High uncertainty prevents silent certification of LOW hazard
        assert np.all(combined == SEVERITY_TO_CODE["UNKNOWN"])

    def test_missing_critical_physical_indicator_does_not_become_low(self, tmp_path):
        """Rule 5: Missing physical indicator with apparent low slope remains UNKNOWN."""
        ds = _make_dataset(slope_val=2.0, ldec_val=5.0)
        ds.rasters["slope"].data[4, 4] = np.nan
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        assert combined[4, 4] == SEVERITY_TO_CODE["UNKNOWN"]
        assert combined[4, 5] == SEVERITY_TO_CODE["LOW"]

    def test_missing_indicator_with_independent_high_remains_high(self, tmp_path):
        """Rule 5: Known HIGH slope independently establishes HIGH even if another indicator is missing."""
        ds = _make_dataset(slope_val=40.0, ldec_val=5.0)
        # Even if elevation uncertainty is NaN for a pixel, the 40 deg slope establishes HIGH
        ds.rasters["elevation_uncertainty"].data[2, 2] = np.nan
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        assert combined[2, 2] == SEVERITY_TO_CODE["HIGH"]

    def test_missing_indicator_with_independent_moderate_remains_moderate(self, tmp_path):
        """Rule 5: Known MODERATE slope independently establishes MODERATE."""
        ds = _make_dataset(slope_val=10.0, ldec_val=5.0)
        ds.rasters["elevation_uncertainty"].data[2, 2] = np.nan
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        with rasterio.open(report["combined_geotiff"]) as src:
            combined = src.read(1)
        assert combined[2, 2] == SEVERITY_TO_CODE["MODERATE"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. GeoTIFF Encoding: Class 0 vs NoData 255
# ═══════════════════════════════════════════════════════════════════════════
class TestGeoTIFFEncoding:
    """Requirement 5: Class 0 remains distinct from NoData 255."""

    def test_class_0_written_as_zero_distinct_from_nodata_255(self, tmp_path):
        arr = np.array([[0, 1], [2, 3]], dtype=np.uint8)
        meta = _meta((2, 2))
        out = tmp_path / "encoding_test.tif"
        write_indicator_geotiff(arr, meta, out, "encoding test")
        with rasterio.open(out) as src:
            assert src.nodata == 255.0
            data = src.read(1)
            assert data[0, 0] == 0  # UNKNOWN
            assert data[0, 1] == 1  # LOW
            assert data[1, 0] == 2  # MODERATE
            assert data[1, 1] == 3  # HIGH

    def test_geotiff_metadata_tags_document_both(self, tmp_path):
        arr = np.zeros((4, 4), dtype=np.uint8)
        meta = _meta((4, 4))
        out = tmp_path / "tags_test.tif"
        write_indicator_geotiff(arr, meta, out, "tags test")
        with rasterio.open(out) as src:
            tags = src.tags()
            assert tags["CLASS_0"] == "UNKNOWN"
            assert tags["CLASS_1"] == "LOW"
            assert tags["CLASS_2"] == "MODERATE"
            assert tags["CLASS_3"] == "HIGH"
            assert "255" in tags["NODATA_VALUE"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Threshold Boundaries & Units
# ═══════════════════════════════════════════════════════════════════════════
class TestThresholdBoundaries:
    """Audit point 5: exact boundary classification and NaN handling."""

    def test_slope_at_exact_low_boundary_is_low(self):
        arr = np.array([5.0], dtype=np.float32)
        result = classify_increasing(arr, low=5.0, moderate=15.0)
        assert result[0] == SEVERITY_TO_CODE["LOW"]

    def test_slope_just_above_low_boundary_is_moderate(self):
        arr = np.array([5.001], dtype=np.float32)
        result = classify_increasing(arr, low=5.0, moderate=15.0)
        assert result[0] == SEVERITY_TO_CODE["MODERATE"]

    def test_slope_at_exact_moderate_boundary_is_moderate(self):
        arr = np.array([15.0], dtype=np.float32)
        result = classify_increasing(arr, low=5.0, moderate=15.0)
        assert result[0] == SEVERITY_TO_CODE["MODERATE"]

    def test_slope_just_above_moderate_boundary_is_high(self):
        arr = np.array([15.001], dtype=np.float32)
        result = classify_increasing(arr, low=5.0, moderate=15.0)
        assert result[0] == SEVERITY_TO_CODE["HIGH"]

    def test_nan_classified_as_unknown(self):
        arr = np.array([np.nan], dtype=np.float32)
        result = classify_increasing(arr, low=5.0, moderate=15.0)
        assert result[0] == SEVERITY_TO_CODE["UNKNOWN"]

    def test_thresholds_contain_units_domain_provisional(self):
        for key, spec in HAZARD_THRESHOLDS.items():
            assert "units" in spec
            assert "domain" in spec
            assert spec.get("provisional") is True


# ═══════════════════════════════════════════════════════════════════════════
# 5. Independent Layer Availability
# ═══════════════════════════════════════════════════════════════════════════
class TestIndependentLayerAvailability:
    """Requirement 1: Separate outputs for physical and quality indicators."""

    def test_separate_geotiffs_generated(self, tmp_path):
        ds = _make_dataset()
        report = generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)
        for key in PHYSICAL_HAZARD_KEYS:
            assert key in report["indicator_geotiffs"]
            assert Path(report["indicator_geotiffs"][key]).exists()
        for key in DATA_QUALITY_KEYS:
            assert key in report["indicator_geotiffs"]
            assert Path(report["indicator_geotiffs"][key]).exists()
        assert Path(report["combined_geotiff"]).exists()
        assert Path(report["data_quality_geotiff"]).exists()


# ═══════════════════════════════════════════════════════════════════════════
# 6. JSON Reporting Verification
# ═══════════════════════════════════════════════════════════════════════════
class TestReportVerification:
    """Requirement 4: JSON report contains all required metrics and percentages."""

    @pytest.fixture
    def report_data(self, tmp_path):
        ds = _make_dataset(slope_val=3.0, ldec_val=15.0)
        return generate_hazard_screening(ds, processed_dir=tmp_path, metadata_dir=tmp_path)

    def test_report_structure(self, report_data):
        assert report_data["policy"] == "Option B: Decoupled Decisional Screening"
        assert "combined_class_counts" in report_data
        assert "combined_class_percentages" in report_data
        assert "physical_hazard_summary_counts" in report_data
        assert "epistemic_quality_summary_counts" in report_data
        assert "interpolation_and_observation_summary" in report_data

    def test_interpolation_percentages_recorded(self, report_data):
        interp = report_data["interpolation_and_observation_summary"]
        assert "interpolated_cells_ldec_zero" in interp
        assert "interpolated_percentage" in interp
        assert "direct_observation_cells_ldec_positive" in interp
        assert "direct_observation_percentage" in interp

    def test_combination_rules_documented(self, report_data):
        rules = report_data["combination_rules"]
        assert "rule_1_high_physical" in rules
        assert "rule_2_moderate_physical" in rules
        assert "rule_3_low_physical" in rules
        assert "rule_4_unverified_low" in rules
        assert "rule_5_missing_indicators" in rules

    def test_class_counts_sum_to_total(self, report_data):
        counts = report_data["combined_class_counts"]
        total = sum(counts.values())
        assert total == report_data["total_pixels"]
