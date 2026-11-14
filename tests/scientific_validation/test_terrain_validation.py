"""Scientific validation tests for Phase 1 Terrain Intelligence Engine.

Validates:
1. Spatial alignment across all five Site04 rasters (dimensions, transforms, CRS, bounds).
2. NoData and data integrity (NaN/Inf absence, lunar physical limits).
3. Handling of missing files and corrupt/truncated GeoTIFF inputs.
4. Observation masks and LDEC distribution (decoupling DEM validity from LDEC > 0).
5. Strict adherence to lunar South-Polar Stereographic CRS without terrestrial EPSG.
"""
from pathlib import Path
import tempfile
import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from app.scientific_engines.terrain.loader import (
    LOLA_CORE_PRODUCTS,
    SiteTerrainDataset,
    TerrainRasterMetadata,
    check_tiff_header,
    extract_raster_metadata,
    load_site_dataset,
    read_raster_band,
)
from app.scientific_engines.terrain.validation import (
    analyze_ldec_distribution,
    evaluate_dem_validity_and_coverage,
    validate_data_integrity,
    validate_lunar_crs,
    validate_site_rasters,
    validate_spatial_alignment,
)

SITE04_DIR = Path("data/raw/terrain/site04")


@pytest.fixture(scope="session")
def site04_dataset() -> SiteTerrainDataset:
    """Fixture providing the loaded Site04 dataset."""
    assert SITE04_DIR.exists(), f"Site04 data directory missing: {SITE04_DIR}"
    return load_site_dataset(SITE04_DIR, site="Site04", load_arrays=True)


# =====================================================================
# 1. Spatial Alignment Tests
# =====================================================================

def test_site04_all_five_rasters_present(site04_dataset: SiteTerrainDataset):
    """Verify all five expected LOLA products exist and are loaded."""
    assert len(site04_dataset.rasters) == 5
    for key in LOLA_CORE_PRODUCTS:
        assert key in site04_dataset.rasters
        assert site04_dataset.rasters[key].metadata is not None
        assert site04_dataset.rasters[key].data is not None


def test_site04_spatial_alignment_exact_match(site04_dataset: SiteTerrainDataset):
    """Verify dimensions, transforms, bounds, and resolution match across all rasters."""
    metas = {k: r.metadata for k, r in site04_dataset.rasters.items()}
    alignment = validate_spatial_alignment(metas, reference_key="elevation")

    assert alignment["passed"] is True
    assert alignment["status"] == "PASS"
    assert alignment["grid_shape"] == [3200, 3200]
    assert alignment["pixel_size_m"] == (5.0, 5.0)

    for key, layer in alignment["layers"].items():
        assert layer["aligned_with_reference"] is True
        assert layer["dimensions_match"] is True
        assert layer["resolution_match"] is True
        assert layer["transform_match"] is True
        assert layer["bounds_match"] is True
        assert layer["crs_match"] is True
        assert layer["band_count_match"] is True
        assert layer["dtype_match"] is True


def test_spatial_alignment_detects_mismatch():
    """Verify that synthetic mismatched rasters trigger alignment failure."""
    ref_meta = TerrainRasterMetadata(
        file_name="ref.tif",
        file_path="/ref.tif",
        file_size_bytes=1000,
        sha256_hash="abc",
        is_valid_tiff_header=True,
        width=3200,
        height=3200,
        band_count=1,
        dtype="float32",
        nodata=np.nan,
        crs_wkt="LUNAR_WKT",
        crs_proj4="+proj=stere",
        is_lunar_crs=True,
        is_terrestrial_epsg=False,
        epsg_code=None,
        transform=(5.0, 0.0, -9000.0, 0.0, -5.0, 1000.0),
        resolution=(5.0, 5.0),
        bounds=(-9000.0, -15000.0, 7000.0, 1000.0),
    )

    # Raster with mismatched dimensions
    mismatched_meta = TerrainRasterMetadata(
        file_name="bad_dim.tif",
        file_path="/bad_dim.tif",
        file_size_bytes=1000,
        sha256_hash="def",
        is_valid_tiff_header=True,
        width=1600,
        height=1600,
        band_count=1,
        dtype="float32",
        nodata=np.nan,
        crs_wkt="LUNAR_WKT",
        crs_proj4="+proj=stere",
        is_lunar_crs=True,
        is_terrestrial_epsg=False,
        epsg_code=None,
        transform=(10.0, 0.0, -9000.0, 0.0, -10.0, 1000.0),
        resolution=(10.0, 10.0),
        bounds=(-9000.0, -15000.0, 7000.0, 1000.0),
    )

    res = validate_spatial_alignment({"elevation": ref_meta, "mismatched": mismatched_meta})
    assert res["passed"] is False
    assert res["status"] == "FAIL"
    assert res["layers"]["mismatched"]["aligned_with_reference"] is False
    assert res["layers"]["mismatched"]["dimensions_match"] is False


# =====================================================================
# 2. NoData and Data Integrity Tests
# =====================================================================

def test_site04_rasters_have_zero_nans_and_zero_infs(site04_dataset: SiteTerrainDataset):
    """Verify that all five Site04 rasters contain 100% finite values (0 NaNs, 0 Infs)."""
    for key, raster in site04_dataset.rasters.items():
        assert raster.data is not None
        nan_count = np.isnan(raster.data).sum()
        inf_count = np.isinf(raster.data).sum()
        assert nan_count == 0, f"{key} contains {nan_count} NaNs"
        assert inf_count == 0, f"{key} contains {inf_count} Infs"
        assert raster.data.size == 3200 * 3200


def test_site04_physical_value_ranges(site04_dataset: SiteTerrainDataset):
    """Verify that values adhere to lunar physical limits."""
    # Elevation: Site04 Shackleton rim (-2848 m to +1805 m)
    surf = site04_dataset.elevation.data
    assert -3000.0 < np.min(surf) < -2800.0
    assert 1700.0 < np.max(surf) < 1900.0

    # Slope: non-negative, <= 90 deg
    slp = site04_dataset.slope.data
    assert np.min(slp) >= 0.0
    assert np.max(slp) < 90.0

    # Observation count: non-negative integers
    ldec = site04_dataset.observation_count.data
    assert np.min(ldec) == 0.0
    assert np.max(ldec) <= 10.0

    # Uncertainties: strictly non-negative
    toterr = site04_dataset.elevation_uncertainty.data
    slperr = site04_dataset.slope_uncertainty.data
    assert np.min(toterr) >= 0.0
    assert np.min(slperr) >= 0.0


def test_data_integrity_detects_corrupt_values():
    """Verify that injected NaNs, Infs, or out-of-range elevations are caught."""
    bad_data = np.array([[100.0, np.nan], [np.inf, 200.0]], dtype=np.float32)
    report = validate_data_integrity(bad_data, product_key="elevation")
    assert report["passed"] is False
    assert report["nan_pixels"] == 1
    assert report["inf_pixels"] == 1

    # Out of lunar elevation bounds
    unrealistic_elev = np.array([[50000.0, -30000.0]], dtype=np.float32)
    report_bounds = validate_data_integrity(unrealistic_elev, product_key="elevation")
    assert report_bounds["passed"] is False
    assert report_bounds["checks"]["within_lunar_elevation_limits"] is False


# =====================================================================
# 3. Missing Files and Corrupt Inputs Tests
# =====================================================================

def test_missing_raster_file_raises_error():
    """Verify FileNotFoundError is raised when a required file is missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        with pytest.raises(FileNotFoundError, match="Missing required LOLA"):
            load_site_dataset(tmp_path, site="Site04", load_arrays=False)


def test_corrupt_tiff_header_detected():
    """Verify that non-TIFF or corrupted header files are detected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_file = Path(tmp_dir) / "corrupt.tif"
        # Write random non-TIFF bytes
        fake_file.write_bytes(b"NOT_A_TIFF_FILE_DATA_HERE")

        assert check_tiff_header(fake_file) is False
        with pytest.raises(ValueError, match="Corrupt or non-TIFF file"):
            extract_raster_metadata(fake_file)


# =====================================================================
# 4. Observation Masks and LDEC Distribution Tests
# =====================================================================

def test_ldec_observation_count_distribution(site04_dataset: SiteTerrainDataset):
    """Verify LDEC observation distribution: ~90.85% zero-count, ~9.15% positive-count."""
    ldec = site04_dataset.observation_count.data
    analysis = analyze_ldec_distribution(ldec)

    assert analysis["total_pixels"] == 10240000
    assert analysis["zero_count_pixels"] == 9302619
    assert abs(analysis["zero_count_percentage"] - 90.8459) < 0.01

    assert analysis["positive_count_pixels"] == 937381
    assert abs(analysis["positive_count_percentage"] - 9.1541) < 0.01

    assert analysis["maximum_spots_per_pixel"] == 5
    # Verify histogram covers all spots 0 through 5
    for s in range(6):
        key = f"spots_per_pixel_{s}"
        assert key in analysis["histogram"]


def test_dem_validity_strictly_decoupled_from_ldec(site04_dataset: SiteTerrainDataset):
    """Verify scientific constraint: LDEC=0 does NOT invalidate DEM elevation.

    Distinguishes:
    1. finite_raster_values (100% numerical population)
    2. direct_observations (9.15% LOLA laser spots)
    3. interpolated_elevations (90.85% continuous surface approximation)
    4. scientifically_validated_terrain (geodetically checked with documented uncertainty)

    Verifies finite != automatically physically accurate:
    interpolated pixels carry higher vertical uncertainty (toterr reaching 7.64 m RMS).
    """
    surf = site04_dataset.elevation.data
    ldec = site04_dataset.observation_count.data
    toterr = site04_dataset.elevation_uncertainty.data
    slperr = site04_dataset.slope_uncertainty.data

    coverage = evaluate_dem_validity_and_coverage(surf, ldec, toterr, slperr)

    assert coverage["status"] == "PASS"
    assert coverage["decoupling_verified"] is True
    assert coverage["finite_dem_pixels"] == 10240000
    assert coverage["finite_dem_percentage"] == 100.0
    assert coverage["direct_observation_pixels"] == 937381
    assert coverage["interpolated_dem_pixels"] == 9302619

    # Verify evidence tier distinction exists and is explicit
    distinction = coverage["scientific_evidence_distinction"]
    assert "finite_raster_values" in distinction
    assert "direct_observations" in distinction
    assert "interpolated_elevations" in distinction
    assert "scientifically_validated_terrain" in distinction

    # Elevation comparison shows valid continuous terrain across both masks
    direct_stats = coverage["elevation_comparison"]["direct_observations"]
    interp_stats = coverage["elevation_comparison"]["interpolated_terrain"]

    assert -3000.0 < direct_stats["minimum_m"] < -2800.0
    assert -3000.0 < interp_stats["minimum_m"] < -2800.0
    assert 1700.0 < direct_stats["maximum_m"] < 1900.0
    assert 1700.0 < interp_stats["maximum_m"] < 1900.0

    # Ensure mean elevations are consistent with continuous surface
    assert abs(direct_stats["mean_m"] - interp_stats["mean_m"]) < 20.0

    # Verify that interpolated elevation has higher max uncertainty than direct spots
    toterr_comp = coverage["uncertainty_comparison"]["elevation_uncertainty_toterr_m_rms"]
    assert toterr_comp["interpolated_terrain_max"] > toterr_comp["direct_observations_max"]



# =====================================================================
# 5. Lunar Coordinate Reference System Tests
# =====================================================================

def test_site04_rasters_preserve_lunar_crs_without_terrestrial_epsg(site04_dataset: SiteTerrainDataset):
    """Verify that all rasters use lunar South-Polar Stereographic CRS and NO terrestrial EPSG."""
    for key, raster in site04_dataset.rasters.items():
        meta = raster.metadata
        crs_report = validate_lunar_crs(meta)

        assert crs_report["passed"] is True
        assert crs_report["status"] == "PASS"
        assert crs_report["checks"]["is_lunar_crs"] is True
        assert crs_report["checks"]["no_terrestrial_epsg"] is True
        assert crs_report["checks"]["epsg_code_is_none"] is True
        assert crs_report["checks"]["polar_stereographic_in_wkt"] is True
        assert crs_report["checks"]["lunar_radius_in_wkt"] is True
        assert crs_report["checks"]["south_pole_origin"] is True
        assert meta.epsg_code is None


def test_terrestrial_crs_fails_lunar_validation():
    """Verify that terrestrial EPSG codes (e.g. WGS84, Earth UTM) fail lunar validation."""
    terrestrial_meta = TerrainRasterMetadata(
        file_name="earth_dem.tif",
        file_path="/earth_dem.tif",
        file_size_bytes=1000,
        sha256_hash="xyz",
        is_valid_tiff_header=True,
        width=100,
        height=100,
        band_count=1,
        dtype="float32",
        nodata=np.nan,
        crs_wkt="GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\",SPHEROID[\"WGS 84\",6378137,298.257223563]]]",
        crs_proj4="+proj=longlat +datum=WGS84",
        is_lunar_crs=False,
        is_terrestrial_epsg=True,
        epsg_code=4326,
        transform=(1.0, 0.0, 0.0, 0.0, -1.0, 0.0),
        resolution=(1.0, 1.0),
        bounds=(0.0, 0.0, 100.0, 100.0),
    )

    res = validate_lunar_crs(terrestrial_meta)
    assert res["passed"] is False
    assert res["status"] == "FAIL"
    assert res["checks"]["is_lunar_crs"] is False
    assert res["checks"]["no_terrestrial_epsg"] is False
    assert res["checks"]["epsg_code_is_none"] is False


# =====================================================================
# 6. End-to-End Validation Report Generation Test
# =====================================================================

def test_full_phase1_validation_report_generation():
    """Verify that full validation pipeline runs and produces a valid report."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        report_path = Path(tmp_dir) / "test_report.json"
        report = validate_site_rasters(SITE04_DIR, site="Site04", output_report_path=report_path)

        assert report["phase1_gate_passed"] is True
        assert report["status"] == "PASS"
        assert report["summary"]["total_rasters_validated"] == 5
        assert report_path.exists()
        assert report_path.stat().st_size > 10000

        # Verify documentary provenance for MOON_ME and DE421
        geodetic_prov = report["provenance_and_integrity"]["geodetic_provenance"]
        assert "MOON_ME" in geodetic_prov["documentary_reference_frame"]
        assert "DE421" in geodetic_prov["documentary_reference_frame"]
        assert "Polar_Stereographic" in geodetic_prov["embedded_geotiff_wkt"]
        assert "1737400" in geodetic_prov["embedded_geotiff_wkt"]

        # Verify scientific constraints checklist
        checklist = report["scientific_constraints_checklist"]
        assert checklist["finite_pixels_not_assumed_physically_accurate"] is True
        assert checklist["lunar_south_polar_stereographic_preserved"] is True
        assert checklist["terrestrial_epsg_codes_strictly_prohibited"] is True
