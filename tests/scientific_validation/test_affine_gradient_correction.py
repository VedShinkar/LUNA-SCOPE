
import numpy as np
import pytest
from rasterio.transform import Affine

from app.scientific_engines.terrain.aspect import calculate_aspect
from app.scientific_engines.terrain.slope import calculate_slope


def plane_dem(transform):
    rows, cols = np.indices((40, 40), dtype=np.float64)
    # The half-pixel offset locates each elevation sample at its pixel centre.
    x, y = transform @ (cols + 0.5, rows + 0.5)
    return (1200.0 + 0.12 * x - 0.16 * y).astype(np.float32)


@pytest.mark.parametrize(
    "transform",
    [
        Affine(5.0, 0.0, 100.0, 0.0, -4.0, 200.0),

        # Rotated, orthogonal pixel axes
        Affine(4.0, 2.0, 100.0, 2.0, -4.0, 200.0),

        # Skewed, non-orthogonal pixel axes
        Affine(5.0, 1.5, 100.0, 0.8, -4.0, 200.0),

        Affine(-5.0, 0.0, 100.0, 0.0, 4.0, 200.0),
    ],
    ids=["north-up", "rotated", "skewed", "reversed-axes"],
)
@pytest.mark.parametrize("method", ["zevenbergen_thorne", "horn"])
def test_affine_slope_and_aspect_match_analytical_plane(transform, method):
    """
    Verify slope and downslope aspect on a planar DEM defined in map
    coordinates, independently of raster rotation or skew.
    """
    p = 0.12
    q = -0.16
    dem = plane_dem(transform)

    expected_slope = np.degrees(np.arctan(np.hypot(p, q)))
    expected_aspect = (
        np.degrees(np.arctan2(-p, -q)) + 360.0
    ) % 360.0

    calculated_slope = calculate_slope(
        dem, transform=transform, method=method, edge_mode="gradient"
    )
    calculated_aspect = calculate_aspect(
        dem, transform=transform, method=method
    )

    # Ignore boundaries to avoid making this test about edge stencils.
    interior = np.s_[2:-2, 2:-2]

    assert np.allclose(
        calculated_slope[interior],
        expected_slope,
        atol=2e-3,
    ), (
        f"{method}: expected slope {expected_slope:.6f}°, "
        f"got median {np.nanmedian(calculated_slope[interior]):.6f}°"
    )

    # Circular angular difference handles 0°/360° wraparound.
    aspect_difference = np.abs(
        calculated_aspect[interior] - expected_aspect
    )
    aspect_difference = np.minimum(
        aspect_difference, 360.0 - aspect_difference
    )

    assert np.max(aspect_difference) < 0.1, (
        f"{method}: expected aspect {expected_aspect:.6f}°, "
        f"got median {np.nanmedian(calculated_aspect[interior]):.6f}°"
    )


@pytest.mark.parametrize("method", ["zevenbergen_thorne", "horn"])
@pytest.mark.parametrize("calculate", [calculate_slope, calculate_aspect])
def test_affine_translation_does_not_change_angles(calculate, method):
    transform = Affine(5.0, 1.5, 100.0, 0.8, -4.0, 200.0)
    dem = plane_dem(transform)
    translated = (transform.a, transform.b, 12345.0, transform.d, transform.e, -98765.0)
    np.testing.assert_array_equal(
        calculate(dem, transform=translated, method=method),
        calculate(dem, transform=transform, method=method),
    )


@pytest.mark.parametrize("calculate", [calculate_slope, calculate_aspect])
@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (Affine(1, 2, 100, 2, 4, 200), "singular"),
        (Affine(5, 0, 100, 0, 0, 200), "singular"),
        (Affine(5, np.inf, 100, 0, -4, 200), "finite"),
        ((5, 0, np.nan, 0, -4, 200), "finite"),
    ],
    ids=["dependent-axes", "zero-axis", "nonfinite-linear", "nonfinite-translation"],
)
def test_invalid_affine_is_rejected(calculate, transform, message):
    with pytest.raises(ValueError, match=message):
        calculate(np.ones((5, 5)), transform=transform)


@pytest.mark.parametrize("method", ["zevenbergen_thorne", "horn"])
def test_affine_nodata_edges_and_flat_aspect(method):
    transform = Affine(5.0, 1.5, 100.0, 0.8, -4.0, 200.0)
    dem = np.full((7, 7), 1200.0)
    dem[3, 3] = np.nan
    original = dem.copy()

    expected_nodata = np.zeros(dem.shape, dtype=bool)
    expected_nodata[2:5, 3] = True
    expected_nodata[3, 2:5] = True
    if method == "horn":
        expected_nodata[2:5, 2:5] = True

    slope = calculate_slope(dem, transform, method, edge_mode="gradient")
    aspect = calculate_aspect(dem, transform, method)
    np.testing.assert_array_equal(np.isnan(slope), expected_nodata)
    np.testing.assert_array_equal(np.isnan(aspect), expected_nodata)
    np.testing.assert_array_equal(slope[~expected_nodata], 0.0)
    np.testing.assert_array_equal(aspect[~expected_nodata], -1.0)

    expected_nodata[[0, -1], :] = True
    expected_nodata[:, [0, -1]] = True
    slope = calculate_slope(dem, transform, method, edge_mode="nan")
    np.testing.assert_array_equal(np.isnan(slope), expected_nodata)
    np.testing.assert_array_equal(dem, original)
