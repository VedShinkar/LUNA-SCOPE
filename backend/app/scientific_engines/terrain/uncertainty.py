"""Terrain uncertainty and data-quality evaluation engine for lunar datasets.

Phase 3 Uncertainty module:
- Analyzes total vertical elevation uncertainty (toterr, metres RMS).
- Analyzes slope uncertainty (slperr, degrees RMS).
- Analyzes LOLA laser observation count (ldec) to separate direct empirical
  laser spot returns from interpolated continuous-curvature terrain.
- Computes comprehensive descriptive statistics, percentiles, and coverage metrics.
- Provides independent data-quality and epistemic confidence classifications,
  strictly decoupled from physical terrain hazards.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import numpy as np

# Configurable (provisional) data-quality and uncertainty thresholds
DATA_QUALITY_THRESHOLDS: Dict[str, Any] = {
    "elevation_uncertainty_m": {
        "low_max": 0.5,       # <= 0.5m: Low uncertainty / high confidence
        "moderate_max": 1.5,  # 0.5 - 1.5m: Moderate uncertainty
        "units": "metres_rms",
        "domain": "data_quality",
        "provisional": True,
        "description": "Total vertical elevation uncertainty (toterr) from LOLA geodetic adjustments.",
    },
    "slope_uncertainty_deg": {
        "low_max": 0.5,       # <= 0.5 deg: Low uncertainty / high confidence
        "moderate_max": 1.5,  # 0.5 - 1.5 deg: Moderate uncertainty
        "units": "degrees_rms",
        "domain": "data_quality",
        "provisional": True,
        "description": "Slope calculation uncertainty (slperr) propagating elevation and baseline errors.",
    },
    "observation_coverage": {
        "confident_min": 2,   # >= 2 direct laser shots: multi-observation direct constraint
        "single_obs_min": 1,  # == 1 direct laser shot: single direct observation constraint
        "units": "laser_spot_count",
        "domain": "data_quality",
        "provisional": True,
        "description": "LOLA laser altimetry shot count (ldec) per 5m pixel.",
        "scientific_note": (
            "LDEC is an epistemic (data-quality) measure, not a physical terrain hazard. "
            "LDEC == 0 (interpolated) indicates terrain gridded between orbital tracks, "
            "not invalid elevation or physically dangerous terrain."
        ),
    },
}

QUALITY_SEVERITY_TO_CODE: Dict[str, int] = {
    "UNKNOWN": 0,
    "LOW": 1,       # Low concern = High confidence / high quality
    "MODERATE": 2,  # Moderate concern = Moderate confidence
    "HIGH": 3,      # High concern = Low confidence / unconstrained or high error
}
CODE_TO_QUALITY_SEVERITY: Dict[int, str] = {v: k for k, v in QUALITY_SEVERITY_TO_CODE.items()}


def analyze_uncertainty_layer(
    data: np.ndarray,
    name: str = "uncertainty",
    units: str = "metres_rms",
    nodata: Optional[float] = None,
) -> Dict[str, Any]:
    """Calculate descriptive statistics and percentiles for an uncertainty raster.

    Args:
        data: 2D array of uncertainty values.
        name: Name of the uncertainty layer (e.g. 'elevation_uncertainty').
        units: Measurement units.
        nodata: Optional NoData value to exclude.

    Returns:
        Structured dictionary of statistics and coverage.
    """
    total = int(data.size)
    if nodata is not None and not np.isnan(nodata):
        valid_mask = np.isfinite(data) & (data != nodata)
    else:
        valid_mask = np.isfinite(data)

    valid_count = int(np.sum(valid_mask))
    invalid_count = total - valid_count
    coverage_pct = round(float(valid_count / total * 100.0), 4)

    if valid_count == 0:
        return {
            "layer_name": name,
            "units": units,
            "total_pixels": total,
            "valid_pixels": 0,
            "invalid_pixels": total,
            "coverage_percentage": 0.0,
            "statistics": None,
        }

    vals = data[valid_mask].astype(np.float64)
    min_val = float(np.min(vals))
    max_val = float(np.max(vals))
    mean_val = float(np.mean(vals))
    std_val = float(np.std(vals, ddof=1)) if valid_count > 1 else 0.0
    median_val = float(np.median(vals))

    p1, p5, p25, p75, p95, p99 = [
        float(x) for x in np.percentile(vals, [1, 5, 25, 75, 95, 99])
    ]

    return {
        "layer_name": name,
        "units": units,
        "total_pixels": total,
        "valid_pixels": valid_count,
        "invalid_pixels": invalid_count,
        "coverage_percentage": coverage_pct,
        "statistics": {
            "minimum": round(min_val, 6),
            "maximum": round(max_val, 6),
            "mean": round(mean_val, 6),
            "std_dev": round(std_val, 6),
            "median": round(median_val, 6),
            "percentiles": {
                "p01": round(p1, 6),
                "p05": round(p5, 6),
                "p25": round(p25, 6),
                "p75": round(p75, 6),
                "p95": round(p95, 6),
                "p99": round(p99, 6),
            },
            "interquartile_range": round(p75 - p25, 6),
        },
    }


def classify_uncertainty_thresholds(
    arr: np.ndarray,
    low_max: float,
    moderate_max: float,
) -> np.ndarray:
    """Classify an uncertainty array into discrete quality-concern levels.

    Encoding:
      0 = UNKNOWN (NaN or invalid)
      1 = LOW concern (high quality, <= low_max)
      2 = MODERATE concern (low_max < val <= moderate_max)
      3 = HIGH concern (low quality / high uncertainty, > moderate_max)
    """
    out = np.full(arr.shape, QUALITY_SEVERITY_TO_CODE["UNKNOWN"], dtype=np.uint8)
    valid = np.isfinite(arr)
    out[valid & (arr <= low_max)] = QUALITY_SEVERITY_TO_CODE["LOW"]
    out[valid & (arr > low_max) & (arr <= moderate_max)] = QUALITY_SEVERITY_TO_CODE["MODERATE"]
    out[valid & (arr > moderate_max)] = QUALITY_SEVERITY_TO_CODE["HIGH"]
    return out


def classify_observation_coverage_confidence(
    ldec: np.ndarray,
    confident_min: int = 2,
    single_obs_min: int = 1,
) -> np.ndarray:
    """Classify LOLA observation count (LDEC) into epistemic confidence levels.

    Levels:
      - LOW concern / High direct confidence: LDEC >= confident_min (multi-shot direct return)
      - MODERATE concern: LDEC == single_obs_min (single direct shot)
      - HIGH concern / Interpolated: LDEC == 0 (gridded surface between tracks)
      - UNKNOWN: NaN or negative (missing/unmeasured)

    Note: LDEC == 0 is HIGH epistemic concern (interpolated), NOT physical HIGH hazard.
    """
    out = np.full(ldec.shape, QUALITY_SEVERITY_TO_CODE["UNKNOWN"], dtype=np.uint8)
    valid = np.isfinite(ldec) & (ldec >= 0)

    out[valid & (ldec == 0)] = QUALITY_SEVERITY_TO_CODE["HIGH"]
    # Single observation -> Moderate confidence
    out[valid & (ldec >= single_obs_min) & (ldec < confident_min)] = QUALITY_SEVERITY_TO_CODE["MODERATE"]
    # Multiple direct laser spots -> High confidence / Low concern
    out[valid & (ldec >= confident_min)] = QUALITY_SEVERITY_TO_CODE["LOW"]
    return out


# Backward-compatible alias
classify_observation_confidence = classify_observation_coverage_confidence
