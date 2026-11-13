"""Multi-scale terrain roughness calculation using local elevation standard deviation.

Phase 2 Roughness module:
- Defines three provisional analytical neighbourhood scales in metres (15 m, 35 m, 75 m).
  (Labelled as provisional analytical scales pending integration of certified vehicle/lander dimensions).
- Converts physical metres to odd integer pixel window sizes using validated resolution.
- Computes unbiased local elevation sample standard deviation with ddof=1.
- Excludes NoData cells from local neighbourhood statistics and computes effective sample counts.
- Explicitly marks neighbourhoods with insufficient samples (< 2 valid cells) as unknown (NaN).
- Edge handling uses actual boundary samples without fabricating artificial reflected terrain.
- Employs median-shifted double-precision (float64) moment filtering for complete cancellation immunity.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
from rasterio.transform import Affine
from scipy.ndimage import uniform_filter

from app.scientific_engines.terrain.slope import extract_pixel_spacing_from_transform

RoughnessEdgeMode = Literal["valid_only", "nan", "reflect"]

# Provisional analytical planetary geomorphometry roughness scales (in metres)
PROVISIONAL_ROUGHNESS_SCALES_M = {
    "small": 15.0,   # Provisional small scale: 3x3 pixels at 5m resolution
    "medium": 35.0,  # Provisional medium scale: 7x7 pixels at 5m resolution
    "large": 75.0,   # Provisional large scale: 15x15 pixels at 5m resolution
}

# Retained alias for backwards-compatibility
ROUGHNESS_SCALES_M = PROVISIONAL_ROUGHNESS_SCALES_M


def physical_scale_to_window_size(scale_m: float, pixel_res_m: float) -> int:
    """Convert physical neighbourhood scale in metres to odd integer pixel window size.

    Symmetric centering requires odd integer dimensions (2k + 1).

    Args:
        scale_m: Physical scale diameter in metres.
        pixel_res_m: Pixel spatial resolution in metres.

    Returns:
        Odd integer window size (>= 3).
    """
    if scale_m <= 0 or pixel_res_m <= 0:
        raise ValueError(f"Scale and resolution must be positive, got scale={scale_m}, res={pixel_res_m}")

    raw_pixels = scale_m / pixel_res_m
    w = int(round(raw_pixels))

    # Ensure window is at least 3x3
    if w < 3:
        w = 3
    # Ensure window is odd for symmetric spatial centering
    if w % 2 == 0:
        w += 1

    return w


def calculate_roughness_std(
    dem: np.ndarray,
    window_size_pixels: int,
    edge_mode: RoughnessEdgeMode = "valid_only",
    ddof: int = 1,
    min_samples: int = 2,
) -> np.ndarray:
    """Calculate local elevation sample standard deviation over an odd-sized moving window.

    Mathematical Formulation:
        For each focal cell (i, j), let W be the window and V be the set of valid
        (finite, non-NoData) cells within the window.
        Let N_valid = |V|.
        If N_valid < min_samples or focal cell is NoData:
            roughness = NaN (marked unknown due to insufficient neighbourhood support)
        Else:
            mean = (1 / N_valid) * sum_{k in V} Z_k
            variance = (1 / (N_valid - ddof)) * sum_{k in V} (Z_k - mean)^2
            roughness = sqrt(max(variance, 0))

    Numerical Stability:
        Calculated in float64 using a median-shifted sum of squares:
            sum_{k in V} (Z_k - mean)^2 = S_2 - (S_1^2 / N_valid)
        where Z is shifted by Z_ref = nanmedian(Z) to eliminate catastrophic cancellation.

    NoData & Edge Handling:
        - NoData cells are excluded from both the sums and the sample count N_valid.
        - Under 'valid_only' (default), border neighbourhoods use only real pixels within the
          grid boundary (N_valid decreases near edges without creating artificial terrain).
        - Under 'nan', border cells within window_size // 2 of the grid boundary are set to NaN.
        - Under 'reflect', border cells are reflected (legacy mode).

    Args:
        dem: 2D array of elevations in metres.
        window_size_pixels: Odd integer window dimension (e.g. 3, 7, 15).
        edge_mode: "valid_only" (default, no artificial terrain), "nan", or "reflect".
        ddof: Delta degrees of freedom (default 1 for sample standard deviation).
        min_samples: Minimum valid samples required to compute standard deviation (>= 2).

    Returns:
        2D array of local elevation standard deviation in metres.
    """
    if dem.ndim != 2:
        raise ValueError(f"DEM must be a 2D array, got {dem.ndim}D")
    if window_size_pixels < 3 or window_size_pixels % 2 == 0:
        raise ValueError(f"window_size_pixels must be an odd integer >= 3, got {window_size_pixels}")
    if min_samples < 2:
        min_samples = 2

    w = window_size_pixels
    w2 = float(w * w)

    z = dem.astype(np.float64)
    valid_mask = np.isfinite(z)

    # If entire array has no valid data
    if not np.any(valid_mask):
        return np.full_like(dem, np.nan, dtype=np.float32)

    # Stable median reference to eliminate cancellation
    z_ref = float(np.nanmedian(z[valid_mask]))

    # Zero-filled shifted arrays for convolution
    z_shift = np.where(valid_mask, z - z_ref, 0.0)
    z2_shift = np.where(valid_mask, (z - z_ref) ** 2, 0.0)
    m = valid_mask.astype(np.float64)

    scipy_mode = "reflect" if edge_mode == "reflect" else "constant"

    # Effective sample count and local sums via separable box filtering
    n_valid = np.round(uniform_filter(m, size=w, mode=scipy_mode, cval=0.0) * w2)
    s1 = uniform_filter(z_shift, size=w, mode=scipy_mode, cval=0.0) * w2
    s2 = uniform_filter(z2_shift, size=w, mode=scipy_mode, cval=0.0) * w2

    # Safe denominator with non-negative guard
    denom = np.maximum(n_valid - float(ddof), 1.0)
    n_safe = np.maximum(n_valid, 1.0)

    # Local sample variance
    sum_sq_diff = s2 - (s1 ** 2) / n_safe
    var = np.maximum(sum_sq_diff / denom, 0.0)

    # Evaluate where valid: must have focal cell valid AND n_valid >= min_samples
    eval_mask = valid_mask & (n_valid >= float(min_samples))
    std = np.where(eval_mask, np.sqrt(var), np.nan).astype(np.float32)

    # Pad edges with NaN if requested
    if edge_mode == "nan":
        pad = w // 2
        std[:pad, :] = np.nan
        std[-pad:, :] = np.nan
        std[:, :pad] = np.nan
        std[:, -pad:] = np.nan

    return std


def compute_multi_scale_roughness(
    dem: np.ndarray,
    transform: Affine | Tuple[float, float, float, float, float, float],
    scales_m: Optional[Dict[str, float]] = None,
    edge_mode: RoughnessEdgeMode = "valid_only",
    ddof: int = 1,
    min_samples: int = 2,
) -> Dict[str, Tuple[np.ndarray, Dict[str, Any]]]:
    """Calculate local elevation sample standard deviation at three provisional analytical scales.

    Provisional Scale Definitions:
    - Small (15 m / 3x3 pixels): Micro-topographic variability, local breaks-of-slope.
    - Medium (35 m / 7x7 pixels): Intermediate morphology, small crater relief.
    - Large (75 m / 15x15 pixels): Mesoscale topographic texture, regional rolling undulation.

    Scale Qualification:
    These scales are designated as PROVISIONAL ANALYTICAL SCALES because certified,
    mission-specific vehicle or lander hardware dimensions are not yet established in the repository.

    Returns:
        Dict mapping scale key ('small', 'medium', 'large') to:
        (roughness_array, scale_metadata)
    """
    if scales_m is None:
        scales_m = PROVISIONAL_ROUGHNESS_SCALES_M

    dx, dy = extract_pixel_spacing_from_transform(transform)
    pixel_res = (dx + dy) / 2.0  # Average pixel spacing in metres

    results: Dict[str, Tuple[np.ndarray, Dict[str, Any]]] = {}

    for scale_key, scale_m in scales_m.items():
        w_pixels = physical_scale_to_window_size(scale_m, pixel_res)
        effective_scale_m = w_pixels * pixel_res

        roughness_arr = calculate_roughness_std(
            dem=dem,
            window_size_pixels=w_pixels,
            edge_mode=edge_mode,
            ddof=ddof,
            min_samples=min_samples,
        )

        valid_vals = roughness_arr[np.isfinite(roughness_arr)]
        if valid_vals.size > 0:
            stats = {
                "minimum_m": round(float(np.min(valid_vals)), 4),
                "maximum_m": round(float(np.max(valid_vals)), 4),
                "mean_m": round(float(np.mean(valid_vals)), 4),
                "std_dev_m": round(float(np.std(valid_vals, ddof=1)), 4) if valid_vals.size > 1 else 0.0,
                "median_m": round(float(np.median(valid_vals)), 4),
            }
        else:
            stats = {}

        meta = {
            "scale_key": scale_key,
            "scale_classification": "provisional_analytical_scale",
            "scale_qualification_note": (
                "Designated as a provisional analytical scale. Certified vehicle or lander "
                "dimensions are not yet integrated into the repository configuration."
            ),
            "nominal_scale_m": scale_m,
            "effective_scale_m": round(effective_scale_m, 2),
            "window_size_pixels": w_pixels,
            "window_shape": [w_pixels, w_pixels],
            "window_centering": "symmetrically_centred_on_focal_pixel",
            "edge_mode": edge_mode,
            "ddof": ddof,
            "min_samples": min_samples,
            "metric": "unbiased_sample_elevation_standard_deviation_ddof1",
            "units": "metre",
            "statistics": stats,
        }

        results[scale_key] = (roughness_arr, meta)

    return results
