"""DEM Slope calculation and validation against NASA LOLA slope products.

Phase 2 Slope module:
- Computes map-coordinate derivatives (dz/dx, dz/dy) using the full affine transform.
- Implements both Zevenbergen-Thorne (2nd-order central difference) and Horn (1981) algorithms.
- Explicitly handles boundary conditions and NoData propagation.
- Expresses slope in degrees: theta = arctan(hypot(dz/dx, dz/dy)) * 180 / pi.
- Evaluates bias, MAE, RMSE, median absolute error, and comparison coverage vs NASA slope raster.
- Investigates and documents systematic algorithm discrepancies.
"""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Tuple

import numpy as np
from rasterio.transform import Affine

SlopeMethod = Literal["zevenbergen_thorne", "horn"]
EdgeMode = Literal["gradient", "nan"]


def extract_pixel_spacing_from_transform(
    transform: Affine | Tuple[float, float, float, float, float, float]
) -> Tuple[float, float]:
    """Extract signed and magnitude pixel spacing from affine transform.

    In GDAL affine convention (a, b, c, d, e, f):
      x_coord = c + j * a + i * b
      y_coord = f + j * d + i * e
    For north-up / standard projected grids without rotation:
      dx = a (step in X per column increment)
      dy = -e (step in Y per row decrement, since row index increases downwards)

    Returns:
        (dx, dy) magnitudes in map units (metres).
    """
    if isinstance(transform, Affine):
        a, b, c, d, e, f = transform.a, transform.b, transform.c, transform.d, transform.e, transform.f
    else:
        a, b, c, d, e, f = transform[:6]

    if abs(b) > 1e-7 or abs(d) > 1e-7:
        # Rotated grid: compute vector magnitudes
        dx = float(np.hypot(a, d))
        dy = float(np.hypot(b, e))
    else:
        dx = float(abs(a))
        dy = float(abs(e))

    return dx, dy


def compute_terrain_gradients(
    dem: np.ndarray,
    dx: float,
    dy: float,
    method: SlopeMethod = "zevenbergen_thorne",
    edge_mode: EdgeMode = "gradient",
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate orthogonal spatial derivatives (dz/dx, dz/dy) from a DEM.

    Orientation convention:
    - dz/dx: partial derivative in Eastward (+X) direction.
    - dz/dy: partial derivative in Northward (+Y) direction.
      (In raster arrays, row index i increases Southward, so Northward gradient is
       proportional to z[i-1] - z[i+1]).

    Args:
        dem: 2D array of elevations in metres.
        dx: Pixel width in metres (Easting step).
        dy: Pixel height in metres (Northing step).
        method: "zevenbergen_thorne" (central difference) or "horn" (3x3 weighted).
        edge_mode: "gradient" (1st-order boundary difference) or "nan" (pad boundary with NaN).

    Returns:
        (dz_dx, dz_dy) gradient arrays in m/m.
    """
    dz_dx, dz_dy = _compute_raster_axis_gradients(dem, dx, dy, method, edge_mode)
    return dz_dx.astype(np.float32), dz_dy.astype(np.float32)


def _compute_raster_axis_gradients(
    dem: np.ndarray,
    dx: float,
    dy: float,
    method: SlopeMethod,
    edge_mode: EdgeMode,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply the stencils along increasing columns and decreasing rows in float64."""
    if dem.ndim != 2:
        raise ValueError(f"DEM must be a 2D array, got {dem.ndim}D")
    if dx <= 0 or dy <= 0:
        raise ValueError(f"Pixel spacings dx and dy must be positive, got dx={dx}, dy={dy}")

    h, w = dem.shape
    dz_dx = np.full((h, w), np.nan, dtype=np.float64)
    dz_dy = np.full((h, w), np.nan, dtype=np.float64)

    z = dem.astype(np.float64)

    # Valid mask for input cells
    valid = np.isfinite(z)

    if method == "zevenbergen_thorne":
        # 2nd-order central difference (interior 1:-1, 1:-1)
        # dz/dx = (z[i, j+1] - z[i, j-1]) / (2 * dx)
        # dz/dy = (z[i-1, j] - z[i+1, j]) / (2 * dy)
        interior_valid = (
            valid[1:-1, 2:] & valid[1:-1, :-2] & valid[:-2, 1:-1] & valid[2:, 1:-1] & valid[1:-1, 1:-1]
        )

        # Interior points
        dz_dx[1:-1, 1:-1] = np.where(
            interior_valid,
            (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * dx),
            np.nan
        )
        dz_dy[1:-1, 1:-1] = np.where(
            interior_valid,
            (z[:-2, 1:-1] - z[2:, 1:-1]) / (2.0 * dy),
            np.nan
        )

    elif method == "horn":
        # Horn (1981) 8-neighbour weighted central difference
        # dz/dx = ((z[i-1, j+1] + 2*z[i, j+1] + z[i+1, j+1]) - (z[i-1, j-1] + 2*z[i, j-1] + z[i+1, j-1])) / (8 * dx)
        # dz/dy = ((z[i-1, j-1] + 2*z[i-1, j] + z[i-1, j+1]) - (z[i+1, j-1] + 2*z[i+1, j] + z[i+1, j+1])) / (8 * dy)

        # Require all 9 cells in 3x3 window to be finite
        win_valid = (
            valid[:-2, :-2] & valid[:-2, 1:-1] & valid[:-2, 2:] &
            valid[1:-1, :-2] & valid[1:-1, 1:-1] & valid[1:-1, 2:] &
            valid[2:, :-2] & valid[2:, 1:-1] & valid[2:, 2:]
        )

        dx_num = (
            (z[:-2, 2:] + 2.0 * z[1:-1, 2:] + z[2:, 2:]) -
            (z[:-2, :-2] + 2.0 * z[1:-1, :-2] + z[2:, :-2])
        )
        dy_num = (
            (z[:-2, :-2] + 2.0 * z[:-2, 1:-1] + z[:-2, 2:]) -
            (z[2:, :-2] + 2.0 * z[2:, 1:-1] + z[2:, 2:])
        )

        dz_dx[1:-1, 1:-1] = np.where(win_valid, dx_num / (8.0 * dx), np.nan)
        dz_dy[1:-1, 1:-1] = np.where(win_valid, dy_num / (8.0 * dy), np.nan)

    else:
        raise ValueError(f"Unknown slope method: {method}. Choose 'zevenbergen_thorne' or 'horn'.")

    # Boundary handling
    if edge_mode == "gradient":
        # Top and bottom row boundaries for dz/dx (central differences along X where available)
        dz_dx[0, 1:-1] = np.where(valid[0, 2:] & valid[0, :-2], (z[0, 2:] - z[0, :-2]) / (2.0 * dx), np.nan)
        dz_dx[-1, 1:-1] = np.where(valid[-1, 2:] & valid[-1, :-2], (z[-1, 2:] - z[-1, :-2]) / (2.0 * dx), np.nan)

        # Left and right column boundaries for dz/dy (central differences along Y where available)
        dz_dy[1:-1, 0] = np.where(valid[:-2, 0] & valid[2:, 0], (z[:-2, 0] - z[2:, 0]) / (2.0 * dy), np.nan)
        dz_dy[1:-1, -1] = np.where(valid[:-2, -1] & valid[2:, -1], (z[:-2, -1] - z[2:, -1]) / (2.0 * dy), np.nan)

        # Left column (col 0) 1-sided forward differences for dz/dx
        dz_dx[:, 0] = np.where(valid[:, 0] & valid[:, 1], (z[:, 1] - z[:, 0]) / dx, np.nan)

        # Right column (col w-1) 1-sided backward differences for dz/dx
        dz_dx[:, -1] = np.where(valid[:, -1] & valid[:, -2], (z[:, -1] - z[:, -2]) / dx, np.nan)

        # Top row (row 0, Northmost) 1-sided forward differences in Y for dz/dy
        dz_dy[0, :] = np.where(valid[0, :] & valid[1, :], (z[0, :] - z[1, :]) / dy, np.nan)

        # Bottom row (row h-1, Southmost) 1-sided backward differences in Y for dz/dy
        dz_dy[-1, :] = np.where(valid[-1, :] & valid[-2, :], (z[-2, :] - z[-1, :]) / dy, np.nan)

    elif edge_mode == "nan":
        dz_dx[0, :] = np.nan
        dz_dx[-1, :] = np.nan
        dz_dx[:, 0] = np.nan
        dz_dx[:, -1] = np.nan

        dz_dy[0, :] = np.nan
        dz_dy[-1, :] = np.nan
        dz_dy[:, 0] = np.nan
        dz_dy[:, -1] = np.nan

    return dz_dx, dz_dy


def _compute_map_gradients(
    dem: np.ndarray,
    transform: Affine | Tuple[float, float, float, float, float, float],
    method: SlopeMethod,
    edge_mode: EdgeMode,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return elevation derivatives along map east (+X) and grid north (+Y)."""
    coefficients = np.asarray(transform[:6], dtype=np.float64)
    if not np.isfinite(coefficients).all():
        raise ValueError("Affine transform coefficients must be finite.")
    a, b, _, d, e, _ = coefficients

    if b == 0 and d == 0 and a > 0 and e < 0:
        # Preserve the established float32 gradient rounding on north-up rasters.
        return compute_terrain_gradients(dem, a, -e, method, edge_mode)

    dz_dcol, dz_dnegative_row = _compute_raster_axis_gradients(dem, 1.0, 1.0, method, edge_mode)
    # The stencil's second derivative points toward decreasing rows. Reverse it
    # to form [dz/dcol, dz/drow] before solving A.T @ g_map = g_pixel.
    pixel_gradients = np.stack((dz_dcol.ravel(), -dz_dnegative_row.ravel()))
    # Treat each pixel as a right-hand side so NumPy factors the 2x2 matrix once.
    try:
        map_gradients = np.linalg.solve([[a, d], [b, e]], pixel_gradients)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Affine transform has a singular linear part.") from exc

    return map_gradients[0].reshape(dem.shape), map_gradients[1].reshape(dem.shape)


def calculate_slope(
    dem: np.ndarray,
    transform: Affine | Tuple[float, float, float, float, float, float],
    method: SlopeMethod = "zevenbergen_thorne",
    edge_mode: EdgeMode = "gradient",
) -> np.ndarray:
    """Calculate surface slope in degrees from a DEM.

    Formula:
        slope_rad = arctan(sqrt((dz/dx)^2 + (dz/dy)^2))
        slope_deg = slope_rad * (180 / pi)

    Args:
        dem: 2D array of elevations in metres.
        transform: Affine transform mapping raster coordinates to map coordinates.
        method: "zevenbergen_thorne" (default, matches NASA product) or "horn".
        edge_mode: Boundary treatment ("gradient" or "nan").

    Returns:
        2D array of slope in degrees.
    """
    dz_dx, dz_dy = _compute_map_gradients(dem, transform, method, edge_mode)

    grad_mag = np.hypot(dz_dx, dz_dy)
    slope_rad = np.arctan(grad_mag)
    slope_deg = np.degrees(slope_rad).astype(np.float32)

    return slope_deg


def compare_slopes(
    calculated_slope: np.ndarray,
    nasa_slope: np.ndarray,
    mask: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Quantitatively compare calculated slope against NASA's supplied slope product.

    Evaluates:
    - Bias (mean signed error: calculated - NASA)
    - Mean Absolute Error (MAE)
    - Root Mean Square Error (RMSE)
    - Median Absolute Error (MedAE)
    - Max Absolute Difference
    - Standard deviation of difference
    - Quantiles (p5, p25, p50, p75, p95)
    - Comparison coverage and a descriptive status

    Inputs must be aligned slope arrays in degrees. Only finite pairs selected
    by the optional validity mask are compared. The status uses no accuracy
    thresholds: it records whether there are no valid pairs, all selected values
    are identical, or differences were measured. Agreement requirements depend
    on the intended use, including sensitivity to local outliers.

    Returns:
        Dictionary of comparison coverage, numerical metrics, and status.
    """
    total_pixels = int(calculated_slope.size)

    # Valid comparison mask: both rasters must have finite values
    valid_comparison = np.isfinite(calculated_slope) & np.isfinite(nasa_slope)
    if mask is not None:
        valid_comparison &= mask

    valid_count = int(valid_comparison.sum())

    if valid_count == 0:
        explanation = "No mutually valid pixels found for slope comparison."
        return {
            "comparison_coverage": {"valid_pixels": 0, "total_pixels": total_pixels, "percentage": 0.0},
            "match_quality": "INSUFFICIENT_VALID_DATA",
            "investigation_and_findings": explanation,
            "error": explanation,
        }

    coverage_pct = float(valid_count / total_pixels * 100.0)
    c_vals = calculated_slope[valid_comparison].astype(np.float64)
    n_vals = nasa_slope[valid_comparison].astype(np.float64)

    diff = c_vals - n_vals
    abs_diff = np.abs(diff)

    bias = float(np.mean(diff))
    mae = float(np.mean(abs_diff))
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    med_ae = float(np.median(abs_diff))
    max_abs_diff = float(np.max(abs_diff))
    std_diff = float(np.std(diff, ddof=1)) if valid_count > 1 else 0.0

    p5, p25, p50, p75, p95 = [float(x) for x in np.percentile(diff, [5, 25, 50, 75, 95])]

    if max_abs_diff == 0.0:
        match_quality = "IDENTICAL_VALID_VALUES"
        explanation = f"Calculated and reference slope values are equal at all {valid_count:,} compared pixels."
    else:
        match_quality = "DIFFERENCES_MEASURED"
        explanation = (
            f"Across {valid_count:,} compared pixels, the MAE is {mae:.6g} deg, "
            f"RMSE is {rmse:.6g} deg, median absolute error is {med_ae:.6g} deg, "
            f"and maximum absolute error is {max_abs_diff:.6g} deg."
        )

    return {
        "comparison_coverage": {
            "valid_comparison_pixels": valid_count,
            "total_pixels": total_pixels,
            "coverage_percentage": round(coverage_pct, 4),
        },
        "metrics_deg": {
            "bias_mean_error": round(bias, 6),
            "mean_absolute_error_mae": round(mae, 6),
            "root_mean_square_error_rmse": round(rmse, 6),
            "median_absolute_error_medae": round(med_ae, 6),
            "max_absolute_error": round(max_abs_diff, 6),
            "std_dev_of_difference": round(std_diff, 6),
            "difference_quantiles": {
                "p05": round(p5, 6),
                "p25": round(p25, 6),
                "median_p50": round(p50, 6),
                "p75": round(p75, 6),
                "p95": round(p95, 6),
            },
        },
        "match_quality": match_quality,
        "investigation_and_findings": explanation,
    }
