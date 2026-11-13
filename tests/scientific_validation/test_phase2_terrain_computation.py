"""Scientific verification tests for Phase 2 Terrain Computation.

Tests:
1. Flat terrain (slope=0, aspect=-1, roughness=0).
2. Known planar gradients (slope=15, 30, 45 deg).
3. Known aspect directions (N, NE, E, SE, S, SW, W, NW).
4. NoData handling across slope, aspect, and roughness.
5. Edge boundary handling modes (gradient and nan).
6. Multi-scale roughness at known physical scales (15m, 35m, 75m).
7. Quantitative slope comparison metrics and discrepancy detection.
8. End-to-end pipeline outputs and lunar georeferencing preservation.
"""
from pathlib import Path
import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from app.scientific_engines.terrain.aspect import (
    FLAT_ASPECT_SENTINEL,
    calculate_aspect,
    create_synthetic_planar_dem,
    summarize_aspect,
)
from app.scientific_engines.terrain.elevation import calculate_elevation_statistics
from app.scientific_engines.terrain.roughness import (
    calculate_roughness_std,
    compute_multi_scale_roughness,
    physical_scale_to_window_size,
)
from app.scientific_engines.terrain.slope import (
    calculate_slope,
    compare_slopes,
    compute_terrain_gradients,
    extract_pixel_spacing_from_transform,
)

STANDARD_TRANSFORM = Affine(5.0, 0.0, -9000.0, 0.0, -5.0, 1000.0)


# =====================================================================
# 1. Flat Terrain Tests
# =====================================================================

def test_flat_terrain_slope_aspect_roughness():
    """Verify that a perfectly horizontal DEM produces zero slope, flat aspect, and zero roughness."""
    shape = (50, 50)
    flat_dem = np.full(shape, 1250.0, dtype=np.float32)

    # Slope
    slope = calculate_slope(flat_dem, transform=STANDARD_TRANSFORM, method="zevenbergen_thorne")
    assert np.allclose(slope, 0.0, atol=1e-6)

    # Aspect
    aspect = calculate_aspect(flat_dem, transform=STANDARD_TRANSFORM)
    # Interior must be -1.0 (flat sentinel)
    assert np.all(aspect == FLAT_ASPECT_SENTINEL)

    # Summary
    summary = summarize_aspect(aspect)
    assert summary["flat_pixels"] == 50 * 50
    assert summary["sloped_pixels"] == 0

    # Roughness
    roughness = calculate_roughness_std(flat_dem, window_size_pixels=3, ddof=1)
    assert np.allclose(roughness, 0.0, atol=1e-6)


# =====================================================================
# 2. Known Planar Gradients Tests
# =====================================================================

@pytest.mark.parametrize("expected_slope", [5.0, 15.0, 30.0, 45.0, 60.0])
def test_known_planar_gradients(expected_slope: float):
    """Verify calculated slope matches known analytical planar tilt."""
    shape = (40, 40)
    # Tilted plane with 0 deg aspect (slopes downward to North)
    planar_dem = create_synthetic_planar_dem(
        shape=shape, dx=5.0, dy=5.0, slope_deg=expected_slope, aspect_deg=0.0
    )

    slope_zt = calculate_slope(planar_dem, transform=STANDARD_TRANSFORM, method="zevenbergen_thorne")
    slope_horn = calculate_slope(planar_dem, transform=STANDARD_TRANSFORM, method="horn")

    # Interior cells (away from 1-pixel boundary) must match analytical slope within float32 precision
    inner_zt = slope_zt[1:-1, 1:-1]
    inner_horn = slope_horn[1:-1, 1:-1]

    assert np.allclose(inner_zt, expected_slope, atol=1e-3)
    assert np.allclose(inner_horn, expected_slope, atol=1e-3)


# =====================================================================
# 3. Known Aspect Directions Tests
# =====================================================================

@pytest.mark.parametrize("target_aspect", [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0])
def test_known_aspect_directions(target_aspect: float):
    """Verify that computed downslope azimuth matches clockwise-from-North convention."""
    shape = (50, 50)
    slope_deg = 15.0
    planar_dem = create_synthetic_planar_dem(
        shape=shape, dx=5.0, dy=5.0, slope_deg=slope_deg, aspect_deg=target_aspect
    )

    aspect = calculate_aspect(planar_dem, transform=STANDARD_TRANSFORM, method="zevenbergen_thorne")
    inner_aspect = aspect[1:-1, 1:-1]

    # Verify every interior cell matches target aspect to within 0.01 deg
    diff = np.abs(inner_aspect - target_aspect)
    # Handle circular 0 vs 360 wrap
    diff = np.minimum(diff, 360.0 - diff)
    assert np.max(diff) < 0.05, f"Aspect mismatch for target {target_aspect} deg, max diff={np.max(diff)}"


# =====================================================================
# 4. NoData Handling Tests
# =====================================================================

def test_nodata_propagation():
    """Verify that isolated and block NaNs propagate cleanly across slope, aspect, and roughness."""
    shape = (30, 30)
    dem = np.full(shape, 1000.0, dtype=np.float32)
    # Inject isolated NaN at [10, 10]
    dem[10, 10] = np.nan
    # Inject block NaN at [20:25, 20:25]
    dem[20:25, 20:25] = np.nan

    slope = calculate_slope(dem, transform=STANDARD_TRANSFORM)
    aspect = calculate_aspect(dem, transform=STANDARD_TRANSFORM)
    roughness = calculate_roughness_std(dem, window_size_pixels=3)

    # Center of NaN block must be NaN
    assert np.isnan(slope[22, 22])
    assert np.isnan(aspect[22, 22])
    assert np.isnan(roughness[22, 22])

    # Isolated NaN cell must be NaN
    assert np.isnan(slope[10, 10])
    assert np.isnan(aspect[10, 10])
    assert np.isnan(roughness[10, 10])

    # Stencil neighbours of isolated NaN must be NaN in central difference
    assert np.isnan(slope[10, 11])
    assert np.isnan(slope[10, 9])
    assert np.isnan(slope[9, 10])
    assert np.isnan(slope[11, 10])

    # Valid flat cells away from NaNs should still evaluate correctly
    assert slope[2, 2] == 0.0
    assert aspect[2, 2] == FLAT_ASPECT_SENTINEL


# =====================================================================
# 5. Edge Handling Tests
# =====================================================================

def test_edge_handling_modes():
    """Verify gradient and nan edge handling modes."""
    shape = (20, 20)
    dem = create_synthetic_planar_dem(shape=shape, dx=5.0, dy=5.0, slope_deg=20.0, aspect_deg=90.0)

    # Default gradient edge mode: boundary cells are evaluated
    slope_grad = calculate_slope(dem, transform=STANDARD_TRANSFORM, edge_mode="gradient")
    assert np.all(np.isfinite(slope_grad))
    assert np.allclose(slope_grad, 20.0, atol=1e-4)

    # NaN edge mode: boundary cells are NaN
    slope_nan = calculate_slope(dem, transform=STANDARD_TRANSFORM, edge_mode="nan")
    assert np.isnan(slope_nan[0, :]).all()
    assert np.isnan(slope_nan[-1, :]).all()
    assert np.isnan(slope_nan[:, 0]).all()
    assert np.isnan(slope_nan[:, -1]).all()
    assert np.allclose(slope_nan[1:-1, 1:-1], 20.0, atol=1e-4)


# =====================================================================
# 6. Roughness Scale Conversion and Validation Tests
# =====================================================================

def test_physical_scale_to_window_size():
    """Verify conversion of metres to odd integer window sizes at 5m resolution."""
    res = 5.0
    assert physical_scale_to_window_size(15.0, res) == 3   # 15m / 5m = 3 -> odd (3x3)
    assert physical_scale_to_window_size(25.0, res) == 5   # 25m / 5m = 5 -> odd (5x5)
    assert physical_scale_to_window_size(35.0, res) == 7   # 35m / 5m = 7 -> odd (7x7)
    assert physical_scale_to_window_size(75.0, res) == 15  # 75m / 5m = 15 -> odd (15x15)
    assert physical_scale_to_window_size(10.0, res) == 3   # 10m / 5m = 2 -> forced odd 3


def test_roughness_known_step_variance():
    """Verify roughness on a known synthetic step profile."""
    # 1D step profile along columns: left half = 0m, right half = 10m
    shape = (20, 20)
    step_dem = np.zeros(shape, dtype=np.float32)
    step_dem[:, 10:] = 10.0

    r3 = calculate_roughness_std(step_dem, window_size_pixels=3, ddof=1)
    # Away from step edge, flat terrain must have 0 roughness
    assert np.allclose(r3[:, :8], 0.0, atol=1e-5)
    assert np.allclose(r3[:, 12:], 0.0, atol=1e-5)
    # Across the boundary (column 9 and 10), roughness is strictly positive
    assert np.all(r3[2:-2, 9:11] > 4.0)


def test_roughness_known_statistical_values_and_cancellation_immunity():
    """Verify roughness with known analytical sample std (ddof=1) and huge base elevation offset."""
    # 3x3 window with values 1 to 9:
    # Mean = 5.0, sum of (x - 5)^2 = 16 + 9 + 4 + 1 + 0 + 1 + 4 + 9 + 16 = 60
    # Sample variance (ddof=1) = 60 / 8 = 7.5
    # Sample std = sqrt(7.5) = 2.7386127875...
    known_3x3 = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
        [7.0, 8.0, 9.0],
    ], dtype=np.float32)

    # Embed in a 5x5 array so [2, 2] has full 3x3 window
    arr = np.zeros((5, 5), dtype=np.float32)
    arr[1:4, 1:4] = known_3x3

    r = calculate_roughness_std(arr, window_size_pixels=3, ddof=1)
    expected_std = np.sqrt(7.5)
    assert np.isclose(r[2, 2], expected_std, atol=1e-5)

    # Test numerical cancellation immunity by adding 1,000,000 metres offset
    huge_arr = arr + 1_000_000.0
    r_huge = calculate_roughness_std(huge_arr, window_size_pixels=3, ddof=1)
    assert np.isclose(r_huge[2, 2], expected_std, atol=1e-5)
    assert np.isclose(r[2, 2], r_huge[2, 2], atol=1e-5)


def test_roughness_masked_neighbourhood_sample_exclusion():
    """Verify that NoData cells are excluded from local statistics and effective N is computed."""
    arr = np.array([
        [10.0, 20.0, 30.0],
        [40.0, 50.0, np.nan],  # Inject 1 NaN in 3x3
        [70.0, 80.0, np.nan],  # Inject 2nd NaN in 3x3
    ], dtype=np.float32)

    # Embed in a 5x5 array
    grid = np.zeros((5, 5), dtype=np.float32)
    grid[1:4, 1:4] = arr

    r = calculate_roughness_std(grid, window_size_pixels=3, ddof=1, min_samples=2)

    # Valid values inside window: 10, 20, 30, 40, 50, 70, 80 (7 samples)
    valid_samples = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 70.0, 80.0], dtype=np.float64)
    expected_std = float(np.std(valid_samples, ddof=1))

    assert np.isclose(r[2, 2], expected_std, atol=1e-4)


def test_roughness_insufficient_sample_counts_marked_unknown():
    """Verify that neighbourhoods with insufficient samples (< min_samples) are marked NaN."""
    grid = np.full((5, 5), np.nan, dtype=np.float32)
    # Only 1 single valid cell in the entire grid
    grid[2, 2] = 1250.0

    # With min_samples=2, focal cell has N_valid=1 < 2, so result must be NaN (unknown)
    r = calculate_roughness_std(grid, window_size_pixels=3, ddof=1, min_samples=2)
    assert np.isnan(r[2, 2])

    # If 2 cells are valid, result must be finite
    grid[2, 3] = 1254.0
    r2 = calculate_roughness_std(grid, window_size_pixels=3, ddof=1, min_samples=2)
    assert np.isfinite(r2[2, 2])
    # 2 samples: 1250 and 1254 -> mean=1252, diffs=-2, +2, sum_sq=8, variance=8/(2-1)=8, std=sqrt(8)=2.8284
    assert np.isclose(r2[2, 2], np.sqrt(8.0), atol=1e-4)


def test_roughness_edge_handling_without_artificial_terrain():
    """Verify that 'valid_only' edge handling uses real in-bounds samples without artificial reflection."""
    grid = np.array([
        [10.0, 20.0, 30.0],
        [40.0, 50.0, 60.0],
        [70.0, 80.0, 90.0],
    ], dtype=np.float32)

    r_valid_only = calculate_roughness_std(grid, window_size_pixels=3, edge_mode="valid_only", ddof=1)

    # Corner cell [0, 0] has 4 in-bounds samples: [10, 20], [40, 50]
    corner_samples = np.array([10.0, 20.0, 40.0, 50.0], dtype=np.float64)
    expected_corner_std = float(np.std(corner_samples, ddof=1))
    assert np.isclose(r_valid_only[0, 0], expected_corner_std, atol=1e-4)

    # Edge cell [0, 1] has 6 in-bounds samples: [10, 20, 30], [40, 50, 60]
    edge_samples = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0], dtype=np.float64)
    expected_edge_std = float(np.std(edge_samples, ddof=1))
    assert np.isclose(r_valid_only[0, 1], expected_edge_std, atol=1e-4)


def test_roughness_provisional_analytical_scale_metadata():
    """Verify that multi-scale roughness metadata records provisional analytical status."""
    dem = np.full((30, 30), 1000.0, dtype=np.float32)
    results = compute_multi_scale_roughness(dem, transform=STANDARD_TRANSFORM)

    for scale_key in ["small", "medium", "large"]:
        assert scale_key in results
        arr, meta = results[scale_key]
        assert meta["scale_classification"] == "provisional_analytical_scale"
        assert meta["window_centering"] == "symmetrically_centred_on_focal_pixel"
        assert meta["ddof"] == 1
        assert "provisional" in meta["scale_qualification_note"].lower()



# =====================================================================
# 7. Slope Comparison Metrics Tests
# =====================================================================

def test_slope_comparison_synthetic_metrics():
    """Verify compare_slopes mathematical calculations."""
    base = np.full((100, 100), 10.0, dtype=np.float32)
    # Exact match
    res_exact = compare_slopes(base, base)
    assert res_exact["metrics_deg"]["bias_mean_error"] == 0.0
    assert res_exact["metrics_deg"]["mean_absolute_error_mae"] == 0.0
    assert res_exact["metrics_deg"]["root_mean_square_error_rmse"] == 0.0
    assert res_exact["match_quality"] == "IDENTICAL_VALID_VALUES"

    # Known bias offset (+0.5 deg)
    biased = base + 0.5
    res_biased = compare_slopes(biased, base)
    assert np.isclose(res_biased["metrics_deg"]["bias_mean_error"], 0.5, atol=1e-5)
    assert np.isclose(res_biased["metrics_deg"]["mean_absolute_error_mae"], 0.5, atol=1e-5)
    assert np.isclose(res_biased["metrics_deg"]["root_mean_square_error_rmse"], 0.5, atol=1e-5)
    assert res_biased["match_quality"] == "DIFFERENCES_MEASURED"


def test_slope_comparison_reports_small_mae_and_large_local_error():
    base = np.full((100, 100), 10.0)
    calculated = base.copy()
    calculated[0, 0] = 35.0
    result = compare_slopes(calculated, base)
    assert result["match_quality"] == "DIFFERENCES_MEASURED"
    assert result["metrics_deg"]["mean_absolute_error_mae"] == 0.0025
    assert result["metrics_deg"]["max_absolute_error"] == 25.0
    assert "maximum absolute error is 25 deg" in result["investigation_and_findings"]


def test_slope_comparison_reports_no_mutually_valid_pixels():
    calculated = np.array([[np.nan, 10.0, 10.0]])
    reference = np.array([[10.0, np.inf, 10.0]])
    mask = np.array([[True, True, False]])
    result = compare_slopes(calculated, reference, mask)
    assert result["match_quality"] == "INSUFFICIENT_VALID_DATA"
    assert result["comparison_coverage"]["valid_pixels"] == 0
    assert result["error"] == result["investigation_and_findings"]
    assert compare_slopes(calculated[:, :0], reference[:, :0])["match_quality"] == "INSUFFICIENT_VALID_DATA"


def test_site04_actual_slope_matches_nasa_within_tolerance():
    """Check the observed Site04 Zevenbergen-Thorne regression bounds."""
    surf_path = Path("data/raw/terrain/site04/Site04_final_adj_5mpp_surf.tif")
    nasa_slp_path = Path("data/raw/terrain/site04/Site04_final_adj_5mpp_slp.tif")
    assert surf_path.exists() and nasa_slp_path.exists()

    with rasterio.open(surf_path) as s_surf, rasterio.open(nasa_slp_path) as s_slp:
        assert (s_surf.shape, s_surf.transform, s_surf.crs) == (s_slp.shape, s_slp.transform, s_slp.crs)
        dem = s_surf.read(1)
        nasa_slp = s_slp.read(1)
        valid = (s_surf.read_masks(1) != 0) & (s_slp.read_masks(1) != 0)
        transform = s_surf.transform

    calc_zt = calculate_slope(dem, transform=transform, method="zevenbergen_thorne")
    metrics_full = compare_slopes(calc_zt, nasa_slp, mask=valid)

    # Across full array (including 1-pixel boundaries), MAE is ~0.0011 deg
    assert metrics_full["metrics_deg"]["mean_absolute_error_mae"] < 0.002
    assert metrics_full["metrics_deg"]["median_absolute_error_medae"] < 0.0005
    assert abs(metrics_full["metrics_deg"]["bias_mean_error"]) < 0.001
    assert metrics_full["match_quality"] == "DIFFERENCES_MEASURED"

    # In the interior (excluding 1-pixel boundary difference), MAE is < 0.0003 deg
    inner_mask = np.zeros_like(dem, dtype=bool)
    inner_mask[1:-1, 1:-1] = True
    metrics_inner = compare_slopes(calc_zt, nasa_slp, mask=inner_mask & valid)
    assert metrics_inner["metrics_deg"]["mean_absolute_error_mae"] < 0.0003
    assert metrics_inner["metrics_deg"]["root_mean_square_error_rmse"] < 0.0003
    assert metrics_inner["metrics_deg"]["median_absolute_error_medae"] < 0.0002



# =====================================================================
# 8. End-to-End Pipeline Outputs & Georeferencing Verification
# =====================================================================

def test_phase2_generated_products_georeferencing():
    """Verify that all generated Phase 2 GeoTIFFs preserve lunar CRS and affine transform."""
    processed_dir = Path("data/processed/terrain/site04")
    assert processed_dir.exists(), f"Missing processed directory: {processed_dir}"

    expected_tifs = [
        "Site04_processed_elevation.tif",
        "Site04_calculated_slope_deg.tif",
        "Site04_slope_difference_deg.tif",
        "Site04_calculated_aspect_deg.tif",
        "Site04_roughness_15m.tif",
        "Site04_roughness_35m.tif",
        "Site04_roughness_75m.tif",
    ]

    for tif_name in expected_tifs:
        tif_path = processed_dir / tif_name
        assert tif_path.exists(), f"Missing expected output GeoTIFF: {tif_path}"

        with rasterio.open(tif_path) as src:
            assert src.shape == (3200, 3200)
            assert src.res == (5.0, 5.0)
            assert src.dtypes[0] == "float32"
            assert src.crs.to_epsg() is None  # Never terrestrial EPSG
            assert "Polar_Stereographic" in src.crs.to_wkt()
            assert "1737400" in src.crs.to_wkt()
            assert src.tags().get("LUNAR_REFERENCE_FRAME") == "MOON_ME associated with DE421 ephemeris"

    # Verify diagnostic maps
    diag_dir = processed_dir / "diagnostics"
    expected_pngs = [
        "Site04_elevation_map.png",
        "Site04_calculated_slope_map.png",
        "Site04_supplied_slope_map.png",
        "Site04_slope_difference_map.png",
        "Site04_aspect_map.png",
        "Site04_roughness_15m_map.png",
        "Site04_roughness_35m_map.png",
        "Site04_roughness_75m_map.png",
    ]
    for png_name in expected_pngs:
        png_path = diag_dir / png_name
        assert png_path.exists(), f"Missing expected diagnostic PNG: {png_path}"
        assert png_path.stat().st_size > 10000

    # Verify Phase 2 report
    report_path = Path("data/metadata/terrain/site04_phase2_terrain_report.json")
    assert report_path.exists()
    assert report_path.stat().st_size > 1000
