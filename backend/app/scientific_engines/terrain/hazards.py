"""Terrain hazard screening (Phase 3) for LUNA-SCOPE.

Option B: Decoupled Decisional Screening
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Maintains independent outputs for:
  1. Physical hazard severity: slope and three provisional roughness scales (15m, 35m, 75m).
  2. Epistemic quality: LOLA observation count (LDEC), elevation uncertainty (toterr),
     slope uncertainty (slperr).
  3. Combined hazard screening: Gated combination reflecting physical hazard with
     rigorous epistemic quality qualification.

Observation Coverage Representation:
  - LDEC = 0: INTERPOLATED / no direct laser observations (epistemic concern: HIGH / code 3).
  - LDEC > 0: DIRECT OBSERVATION, with count retained (code 1 for multi-shot, code 2 for single-shot).
  - Missing or invalid LDEC: UNKNOWN (code 0).

Combined Classification Rules:
  - Known HIGH physical hazard remains HIGH (3) regardless of observation coverage.
  - Known MODERATE physical hazard remains MODERATE (2) regardless of observation coverage.
  - LOW physical hazard becomes LOW (1) only when required quality evidence satisfies
    documented provisional criteria (direct observation LDEC > 0, acceptable elevation
    and slope uncertainty, no missing quality inputs).
  - LOW physical hazard with interpolated or insufficient quality evidence becomes UNKNOWN (0).
  - Missing critical physical indicators remain UNKNOWN (0) unless a known HIGH or MODERATE
    indicator independently establishes that severity.

GeoTIFF Encoding:
  - Class 0: UNKNOWN (valid in-grid category for unverified/missing data).
  - Class 1: LOW.
  - Class 2: MODERATE.
  - Class 3: HIGH.
  - NoData: 255 (outside raster domain).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio
from rasterio.transform import Affine

# ---------------------------------------------------------------------------
# Configurable (provisional) hazard thresholds
# ---------------------------------------------------------------------------
HAZARD_THRESHOLDS: Dict[str, Any] = {
    # --- Physical hazard thresholds ---
    "slope_deg": {
        "low": 5.0,
        "low_max": 5.0,
        "moderate": 15.0,
        "moderate_max": 15.0,
        "high": 30.0,
        "units": "degrees",
        "domain": "physical_hazard",
        "provisional": True,
        "description": "Slope hazard: LOW <= 5 deg, MODERATE 5-15 deg, HIGH > 15 deg (slopes > 30 deg represent extreme terrain).",
    },
    "roughness_small_m": {
        "low": 0.5,
        "low_max": 0.5,
        "moderate": 1.5,
        "moderate_max": 1.5,
        "high": 3.0,
        "units": "metres",
        "domain": "physical_hazard",
        "provisional": True,
        "description": "15m micro-scale roughness: LOW <= 0.5m, MODERATE 0.5-1.5m, HIGH > 1.5m.",
    },
    "roughness_medium_m": {
        "low": 1.0,
        "low_max": 1.0,
        "moderate": 2.5,
        "moderate_max": 2.5,
        "high": 5.0,
        "units": "metres",
        "domain": "physical_hazard",
        "provisional": True,
        "description": "35m meso-scale roughness: LOW <= 1.0m, MODERATE 1.0-2.5m, HIGH > 2.5m.",
    },
    "roughness_large_m": {
        "low": 2.0,
        "low_max": 2.0,
        "moderate": 4.0,
        "moderate_max": 4.0,
        "high": 8.0,
        "units": "metres",
        "domain": "physical_hazard",
        "provisional": True,
        "description": "75m macro-scale roughness: LOW <= 2.0m, MODERATE 2.0-4.0m, HIGH > 4.0m.",
    },
    # --- Data-quality thresholds ---
    "elevation_uncertainty_m": {
        "low": 0.5,
        "low_max": 0.5,
        "moderate": 1.5,
        "moderate_max": 1.5,
        "high": 3.0,
        "units": "metres_rms",
        "domain": "data_quality",
        "provisional": True,
        "description": "Total vertical elevation uncertainty (toterr): LOW <= 0.5m, MODERATE 0.5-1.5m, HIGH > 1.5m.",
    },
    "slope_uncertainty_deg": {
        "low": 0.5,
        "low_max": 0.5,
        "moderate": 1.5,
        "moderate_max": 1.5,
        "high": 3.0,
        "units": "degrees_rms",
        "domain": "data_quality",
        "provisional": True,
        "description": "Slope uncertainty (slperr): LOW <= 0.5 deg, MODERATE 0.5-1.5 deg, HIGH > 1.5 deg.",
    },
    "observation_coverage": {
        "confident_min": 2,
        "single_obs_min": 1,
        "units": "laser_spot_count",
        "domain": "data_quality",
        "provisional": True,
        "description": (
            "LOLA observation count (ldec): DIRECT MULTI-SHOT >= 2 (LOW concern, code 1), "
            "DIRECT SINGLE-SHOT == 1 (MODERATE concern, code 2), "
            "INTERPOLATED == 0 (HIGH concern, code 3), MISSING/INVALID (UNKNOWN, code 0)."
        ),
        "scientific_note": (
            "LDEC observation count is an epistemic (data-quality) measure, "
            "not a physical hazard. LDEC=0 represents mathematically interpolated "
            "terrain between orbital tracks, not invalid elevation or physical danger."
        ),
    },
}

# Integer codes for categorical rasters
SEVERITY_TO_CODE: Dict[str, int] = {"UNKNOWN": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3}
CODE_TO_SEVERITY: Dict[int, str] = {v: k for k, v in SEVERITY_TO_CODE.items()}

# Domain tags
PHYSICAL_HAZARD_KEYS: List[str] = [
    "slope",
    "roughness_small",
    "roughness_medium",
    "roughness_large",
]
DATA_QUALITY_KEYS: List[str] = [
    "elevation_uncertainty",
    "slope_uncertainty",
    "observation_coverage",
]


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------
def classify_increasing(
    arr: np.ndarray,
    low: float,
    moderate: float,
) -> np.ndarray:
    """Classify a raster where higher values mean higher severity / concern.

    Returns uint8 array:
      0 = UNKNOWN  (NaN input)
      1 = LOW      (value <= low)
      2 = MODERATE (low < value <= moderate)
      3 = HIGH     (value > moderate)
    """
    out = np.full(arr.shape, SEVERITY_TO_CODE["UNKNOWN"], dtype=np.uint8)
    valid = np.isfinite(arr)
    out[valid & (arr <= low)] = SEVERITY_TO_CODE["LOW"]
    out[valid & (arr > low) & (arr <= moderate)] = SEVERITY_TO_CODE["MODERATE"]
    out[valid & (arr > moderate)] = SEVERITY_TO_CODE["HIGH"]
    return out


def classify_observation_coverage(
    ldec: np.ndarray,
    confident_min: int = 2,
    single_obs_min: int = 1,
    **kwargs: Any,
) -> np.ndarray:
    """Classify LDEC observation count as an epistemic data-quality indicator.

    Epistemic concern levels:
      - LOW concern (1): LDEC >= confident_min (direct multi-shot laser returns)
      - MODERATE concern (2): LDEC == single_obs_min (direct single laser return)
      - HIGH concern / INTERPOLATED (3): LDEC == 0 (interpolated terrain between orbital tracks)
      - UNKNOWN (0): NaN or negative (missing/unmeasured raster data)

    Scientific constraint:
      LDEC=0 is classified as HIGH epistemic concern (interpolated, code 3), strictly distinct
      from UNKNOWN (missing data, code 0) and strictly decoupled from physical terrain hazards.
    """
    out = np.full(ldec.shape, SEVERITY_TO_CODE["UNKNOWN"], dtype=np.uint8)
    valid = np.isfinite(ldec) & (ldec >= 0)

    # LDEC == 0 -> Interpolated terrain (High epistemic concern / code 3)
    out[valid & (ldec == 0)] = SEVERITY_TO_CODE["HIGH"]
    # LDEC == 1 -> Direct single observation (Moderate epistemic concern / code 2)
    out[valid & (ldec >= single_obs_min) & (ldec < confident_min)] = SEVERITY_TO_CODE["MODERATE"]
    # LDEC >= 2 -> Direct multi-observation (Low epistemic concern / code 1)
    out[valid & (ldec >= confident_min)] = SEVERITY_TO_CODE["LOW"]
    return out


# ---------------------------------------------------------------------------
# GeoTIFF writer for categorical indicators
# ---------------------------------------------------------------------------
def write_indicator_geotiff(
    arr: np.ndarray,
    meta: Any,
    out_path: Path,
    description: str,
) -> Path:
    """Write a uint8 categorical indicator raster.

    Encoding:
      0 = UNKNOWN (valid in-grid class – unverified or missing data)
      1 = LOW
      2 = MODERATE
      3 = HIGH
      255 = NoData (outside raster domain)

    The output raster preserves verbatim lunar CRS WKT and affine transform.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    height, width = arr.shape

    # Ensure small rasters disable tiling (GDAL requires block >= 16 when tiled)
    use_tiled = (height >= 256) and (width >= 256)
    profile: Dict[str, Any] = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": rasterio.crs.CRS.from_wkt(meta.crs_wkt),
        "transform": Affine(*meta.transform),
        "nodata": 255,
        "compress": "deflate",
    }
    if use_tiled:
        profile["tiled"] = True
        profile["blockxsize"] = 256
        profile["blockysize"] = 256
    else:
        profile["tiled"] = False

    write_arr = arr.astype(np.uint8)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(write_arr, 1)
        dst.update_tags(
            AREA_OR_POINT="Area",
            DESCRIPTION=description,
            LUNAR_REFERENCE_FRAME="MOON_ME associated with DE421 ephemeris",
            PROJECTION="Lunar South-Polar Stereographic",
            UNITS="category",
            CLASS_0="UNKNOWN",
            CLASS_1="LOW",
            CLASS_2="MODERATE",
            CLASS_3="HIGH",
            NODATA_VALUE="255 (outside raster domain)",
        )
    return out_path


# ---------------------------------------------------------------------------
# Decoupled Decisional Screening Combiner
# ---------------------------------------------------------------------------
def combine_hazard_screening(
    physical_indicators: Dict[str, np.ndarray],
    quality_indicators: Dict[str, np.ndarray],
) -> np.ndarray:
    """Implement Option B: Decoupled Decisional Screening combination logic.

    Rules:
      1. Known HIGH physical hazard remains HIGH (3) regardless of observation coverage.
      2. Known MODERATE physical hazard remains MODERATE (2) regardless of observation coverage.
      3. Missing critical physical indicators without a known HIGH or MODERATE indicator
         remain UNKNOWN (0).
      4. LOW physical hazard becomes LOW (1) ONLY when required quality evidence satisfies
         documented provisional criteria:
           - Direct observations present (LDEC > 0, i.e. observation_coverage code 1 or 2)
           - Elevation uncertainty acceptable (toterr <= moderate threshold, code 1 or 2)
           - Slope uncertainty acceptable (slperr <= moderate threshold, code 1 or 2)
           - No quality indicator is UNKNOWN (0)
      5. LOW physical hazard with interpolated or insufficient quality evidence
         becomes UNKNOWN (0) (unverified low).
    """
    phys_stack = np.stack([a for a in physical_indicators.values()], axis=0)

    # Known HIGH physical hazard (code 3)
    is_high = np.any(phys_stack == SEVERITY_TO_CODE["HIGH"], axis=0)

    # Known MODERATE physical hazard (code 2), when not HIGH
    is_mod = (~is_high) & np.any(phys_stack == SEVERITY_TO_CODE["MODERATE"], axis=0)

    # All physical indicators known and all LOW (code 1)
    all_phys_low = np.all(phys_stack == SEVERITY_TO_CODE["LOW"], axis=0)

    # Epistemic quality criteria for certifying LOW hazard
    obs_cov = quality_indicators["observation_coverage"]
    elev_unc = quality_indicators["elevation_uncertainty"]
    slope_unc = quality_indicators["slope_uncertainty"]

    # Direct observations: LDEC > 0 (code 1 for multi-shot, code 2 for single-shot)
    direct_obs = (obs_cov == SEVERITY_TO_CODE["LOW"]) | (obs_cov == SEVERITY_TO_CODE["MODERATE"])

    # Elevation uncertainty acceptable (code 1 or 2)
    elev_ok = (elev_unc == SEVERITY_TO_CODE["LOW"]) | (elev_unc == SEVERITY_TO_CODE["MODERATE"])

    # Slope uncertainty acceptable (code 1 or 2)
    slope_ok = (slope_unc == SEVERITY_TO_CODE["LOW"]) | (slope_unc == SEVERITY_TO_CODE["MODERATE"])

    # No quality indicator is UNKNOWN (code 0)
    qual_stack = np.stack([a for a in quality_indicators.values()], axis=0)
    no_qual_unknown = ~np.any(qual_stack == SEVERITY_TO_CODE["UNKNOWN"], axis=0)

    quality_criteria_passed = direct_obs & elev_ok & slope_ok & no_qual_unknown

    # Output combined array
    shape = phys_stack.shape[1:]
    combined = np.full(shape, SEVERITY_TO_CODE["UNKNOWN"], dtype=np.uint8)

    # Apply precedence rules
    combined[is_high] = SEVERITY_TO_CODE["HIGH"]
    combined[is_mod] = SEVERITY_TO_CODE["MODERATE"]
    combined[all_phys_low & quality_criteria_passed] = SEVERITY_TO_CODE["LOW"]
    # All other cells remain UNKNOWN (0):
    # - Missing physical indicators without HIGH or MOD remain UNKNOWN.
    # - Low physical hazard with interpolated (LDEC=0) or high uncertainty remains UNKNOWN.

    return combined


# ---------------------------------------------------------------------------
# Primary public API
# ---------------------------------------------------------------------------
def generate_hazard_screening(
    site_dataset: "SiteTerrainDataset",
    processed_dir: Path = Path("data/processed/terrain/site04"),
    metadata_dir: Path = Path("data/metadata/terrain"),
    site: str = "Site04",
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate Phase 3 hazard screening products under Option B policy.

    Architecture:
      1. Compute physical hazard indicators (slope, 15m/35m/75m roughness).
      2. Compute data-quality indicators (toterr, slperr, ldec).
      3. Write each as a separate GeoTIFF preserving georeferencing.
      4. Combine into a categorical screening raster using decoupled decisional logic.
      5. Write JSON report with per-indicator and combined class counts,
         interpolated cell percentages, thresholds, assumptions, valid coverage and limitations.

    Returns:
        Machine-readable report dictionary.
    """
    if thresholds is None:
        thresholds = HAZARD_THRESHOLDS

    timestamp = datetime.now(timezone.utc).isoformat()
    processed_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # ── Load source arrays ───────────────────────────────────────────────
    dem = site_dataset.elevation.data
    slope_arr = site_dataset.slope.data
    elev_unc = site_dataset.elevation_uncertainty.data
    slope_unc = site_dataset.slope_uncertainty.data
    ldec = site_dataset.observation_count.data
    meta = site_dataset.elevation.metadata

    # Roughness at three scales
    from app.scientific_engines.terrain.roughness import (
        PROVISIONAL_ROUGHNESS_SCALES_M,
        compute_multi_scale_roughness,
    )
    roughness_dict = compute_multi_scale_roughness(
        dem,
        transform=meta.transform,
        scales_m=PROVISIONAL_ROUGHNESS_SCALES_M,
    )

    # ── Physical hazard indicators ───────────────────────────────────────
    physical_indicators: Dict[str, Tuple[np.ndarray, str]] = {}

    t = thresholds["slope_deg"]
    physical_indicators["slope"] = (
        classify_increasing(slope_arr, t["low"], t["moderate"]),
        "Slope physical hazard classification (degrees)",
    )
    for scale_key in ("small", "medium", "large"):
        r_arr, _ = roughness_dict[scale_key]
        t = thresholds[f"roughness_{scale_key}_m"]
        physical_indicators[f"roughness_{scale_key}"] = (
            classify_increasing(r_arr, t["low"], t["moderate"]),
            f"Roughness ({scale_key}) physical hazard classification (metres)",
        )

    # ── Data-quality indicators ──────────────────────────────────────────
    quality_indicators: Dict[str, Tuple[np.ndarray, str]] = {}

    t = thresholds["elevation_uncertainty_m"]
    quality_indicators["elevation_uncertainty"] = (
        classify_increasing(elev_unc, t["low"], t["moderate"]),
        "Elevation uncertainty data-quality classification (metres)",
    )
    t = thresholds["slope_uncertainty_deg"]
    quality_indicators["slope_uncertainty"] = (
        classify_increasing(slope_unc, t["low"], t["moderate"]),
        "Slope uncertainty data-quality classification (degrees)",
    )
    t_obs = thresholds["observation_coverage"]
    quality_indicators["observation_coverage"] = (
        classify_observation_coverage(
            ldec,
            confident_min=t_obs.get("confident_min", 2),
            single_obs_min=t_obs.get("single_obs_min", 1),
        ),
        "Observation-count data-quality classification (LDEC count: 0=interpolated/code 3, 1=single/code 2, >=2=multi/code 1)",
    )

    # ── Write individual indicator GeoTIFFs ──────────────────────────────
    all_indicators = {**physical_indicators, **quality_indicators}
    indicator_paths: Dict[str, str] = {}
    indicator_class_counts: Dict[str, Dict[str, int]] = {}

    for key, (arr, desc) in all_indicators.items():
        out_path = processed_dir / f"{site}_hazard_{key}.tif"
        write_indicator_geotiff(arr, meta, out_path, desc)
        indicator_paths[key] = str(out_path)
        indicator_class_counts[key] = _count_classes(arr)

    # ── Combined screening raster (Option B) ─────────────────────────────
    phys_arrays = {k: arr for k, (arr, _) in physical_indicators.items()}
    qual_arrays = {k: arr for k, (arr, _) in quality_indicators.items()}

    combined = combine_hazard_screening(phys_arrays, qual_arrays)
    combined_path = processed_dir / f"{site}_combined_hazard_screen.tif"
    write_indicator_geotiff(
        combined, meta, combined_path,
        "Combined terrain hazard screening – Option B Decoupled Decisional Screening",
    )
    combined_class_counts = _count_classes(combined)

    # ── Data-quality summary raster ──────────────────────────────────────
    qual_stack = np.stack(list(qual_arrays.values()), axis=0)
    any_qual_unknown = np.any(qual_stack == SEVERITY_TO_CODE["UNKNOWN"], axis=0)
    max_quality = np.max(qual_stack, axis=0)
    quality_summary = np.where(any_qual_unknown, SEVERITY_TO_CODE["UNKNOWN"], max_quality).astype(np.uint8)
    quality_path = processed_dir / f"{site}_data_quality_screen.tif"
    write_indicator_geotiff(
        quality_summary, meta, quality_path,
        "Data-quality summary – max(elevation_uncertainty, slope_uncertainty, observation_coverage)",
    )
    quality_class_counts = _count_classes(quality_summary)

    # ── Physical hazard summary (for reporting) ──────────────────────────
    phys_stack = np.stack(list(phys_arrays.values()), axis=0)
    any_phys_unknown = np.any(phys_stack == SEVERITY_TO_CODE["UNKNOWN"], axis=0)
    max_phys = np.max(phys_stack, axis=0)
    physical_summary = np.where(any_phys_unknown, SEVERITY_TO_CODE["UNKNOWN"], max_phys).astype(np.uint8)
    physical_class_counts = _count_classes(physical_summary)

    # ── Statistics & JSON report ─────────────────────────────────────────
    total_pixels = int(combined.size)
    combined_percentages = {
        cls_name: round(float(cnt / total_pixels * 100.0), 4)
        for cls_name, cnt in combined_class_counts.items()
    }
    physical_percentages = {
        cls_name: round(float(cnt / total_pixels * 100.0), 4)
        for cls_name, cnt in physical_class_counts.items()
    }
    quality_percentages = {
        cls_name: round(float(cnt / total_pixels * 100.0), 4)
        for cls_name, cnt in quality_class_counts.items()
    }

    # Interpolation statistics
    interpolated_mask = np.isfinite(ldec) & (ldec == 0)
    interpolated_count = int(np.sum(interpolated_mask))
    interpolated_pct = round(float(interpolated_count / total_pixels * 100.0), 4)

    direct_obs_mask = np.isfinite(ldec) & (ldec > 0)
    direct_obs_count = int(np.sum(direct_obs_mask))
    direct_obs_pct = round(float(direct_obs_count / total_pixels * 100.0), 4)

    missing_ldec_mask = ~np.isfinite(ldec) | (ldec < 0)
    missing_ldec_count = int(np.sum(missing_ldec_mask))

    valid_coverage_pct = round(
        float(np.count_nonzero(combined != SEVERITY_TO_CODE["UNKNOWN"]) / total_pixels * 100.0), 4
    )

    report: Dict[str, Any] = {
        "report_type": "LUNA-SCOPE Phase 3 Terrain Hazard Screening Report",
        "policy": "Option B: Decoupled Decisional Screening",
        "site": site,
        "timestamp_utc": timestamp,
        "phase3_complete": True,
        "classification_encoding": {
            "codes": SEVERITY_TO_CODE,
            "nodata_value": 255,
            "nodata_meaning": "Pixel outside raster domain",
            "class_0_meaning": "UNKNOWN – unverified low-hazard evidence or missing critical data",
        },
        "indicator_domains": {
            "physical_hazard": PHYSICAL_HAZARD_KEYS,
            "data_quality": DATA_QUALITY_KEYS,
        },
        "thresholds": thresholds,
        "combination_rules": {
            "rule_1_high_physical": "Known HIGH physical hazard (slope > 15 deg or roughness > high threshold) remains HIGH (3) regardless of observation coverage.",
            "rule_2_moderate_physical": "Known MODERATE physical hazard (slope 5-15 deg or roughness moderate) remains MODERATE (2) regardless of observation coverage.",
            "rule_3_low_physical": "LOW physical hazard becomes LOW (1) only when required quality evidence satisfies criteria: direct observations LDEC > 0, acceptable elevation uncertainty (toterr <= 1.5m), and acceptable slope uncertainty (slperr <= 1.5 deg).",
            "rule_4_unverified_low": "LOW physical hazard with interpolated (LDEC=0) or insufficient quality evidence becomes UNKNOWN (0).",
            "rule_5_missing_indicators": "Missing critical physical indicators remain UNKNOWN (0) unless a known HIGH or MODERATE indicator independently establishes that severity.",
        },
        "interpolation_and_observation_summary": {
            "total_pixels": total_pixels,
            "interpolated_cells_ldec_zero": interpolated_count,
            "interpolated_percentage": interpolated_pct,
            "direct_observation_cells_ldec_positive": direct_obs_count,
            "direct_observation_percentage": direct_obs_pct,
            "missing_invalid_ldec_cells": missing_ldec_count,
        },
        "combined_class_counts": combined_class_counts,
        "combined_class_percentages": combined_percentages,
        "physical_hazard_summary_counts": physical_class_counts,
        "physical_hazard_summary_percentages": physical_percentages,
        "epistemic_quality_summary_counts": quality_class_counts,
        "epistemic_quality_summary_percentages": quality_percentages,
        "per_indicator_class_counts": indicator_class_counts,
        "valid_coverage_percentage": valid_coverage_pct,
        "total_pixels": total_pixels,
        "indicator_geotiffs": indicator_paths,
        "combined_geotiff": str(combined_path),
        "data_quality_geotiff": str(quality_path),
        "scientific_limitations": [
            "All thresholds are provisional and not tied to any specific lunar vehicle or lander design.",
            "LDEC observation count is an epistemic (data-quality) measure, not a physical terrain hazard. "
            "LDEC=0 represents mathematically interpolated terrain between orbital tracks, not invalid elevation or physical danger.",
            "Elevation and slope uncertainty layers reflect interpolation variance and instrument error; they are not exhaustive error budgets.",
            "Combined classification uses Decoupled Decisional Screening: crater walls and rough slopes are flagged as hazardous regardless of laser spot support, "
            "while benign slopes without direct laser support are held as UNKNOWN to prevent silent certification of interpolated terrain as safe.",
            "Roughness scales (15 m, 35 m, 75 m) are provisional analytical scales; mission-specific hardware dimensions are not defined.",
            "This product is a decision-support preliminary screening layer, NOT a certified landing-site safety assessment.",
        ],
        "assumptions": [
            "All input rasters share identical spatial grids (validated in Phase 1).",
            "Slope and roughness are computed from the same 5 m LOLA DEM (Phase 2).",
            "NoData in any source raster propagates as UNKNOWN in the combined product unless overridden by a known physical hazard.",
            "Independent physical hazards (slope > 15 deg) are unlandable/impassable regardless of measurement density.",
        ],
    }

    report_path = metadata_dir / f"{site.lower()}_phase3_hazard_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _count_classes(arr: np.ndarray) -> Dict[str, int]:
    """Count pixels in each severity class."""
    return {
        name: int(np.count_nonzero(arr == code))
        for name, code in SEVERITY_TO_CODE.items()
    }
