"""
LUNA-SCOPE — Horizons–SPICE Scientific Validation Subsystem.

Public interfaces and validation orchestration for:
- Stage A: Horizons apparent observer benchmark catalog verification.
- Stage B1: Geometric Cartesian vector query construction and CSV parsing.
- Stage B2: SPICE geometric state construction in J2000 and MOON_ME.
- Stage B3: Horizons–SPICE geometric vector comparison engine.
- Phase C0: Hardened, auditable offline/live HTTP capture pipeline.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from .comparison import (
    GeometricVectorComparisonResult,
    compare_geometric_vectors,
)
from .geometric_state import (
    FRAME_J2000,
    FRAME_MOON_ME,
    LUNAR_RADIUS_MEAN_KM,
    LunarSurfaceLocation,
    SpiceGeometricState,
    compute_spice_geometric_state,
    enu_basis,
    lunar_to_cartesian_me,
    vector_me_to_azel,
)
from .horizons import (
    HORIZONS_API_BASE_URL,
    MAX_CAPTURE_BYTES,
    READ_CHUNK_SIZE,
    HorizonsVectorCaptureResult,
    ParsedHorizonsVectorData,
    build_horizons_observer_url,
    build_horizons_vector_url,
    capture_horizons_vector_pilot,
    parse_horizons_observer_response,
    parse_horizons_vector_csv,
)
from .kernels import _load
from .provenance import (
    E1_R6_PROVENANCE_SCHEMA,
    EPHEMERIS_TRACK_APPARENT_OBSERVER,
    EPHEMERIS_TRACK_GEOMETRIC_VECTORS,
    HorizonsQueryError,
    PROVISIONAL_ANGULAR_RESIDUAL_TOLERANCE_DEG,
    PROVISIONAL_POSITION_RESIDUAL_TOLERANCE_KM,
    PROVISIONAL_RANGE_RESIDUAL_TOLERANCE_KM,
    SOURCE_CLASSIFICATION_SYNTHETIC,
    SOURCE_CLASSIFICATION_UNVERIFIED,
    SOURCE_CLASSIFICATION_VERIFIED_PILOT,
    STATUS_EXCEEDS_PROVISIONAL_TOLERANCE,
    STATUS_NOT_ASSESSED,
    STATUS_WITHIN_PROVISIONAL_TOLERANCE,
    VectorProvenanceRecord,
    _CAPTURE_TOKEN,
    _CaptureReceipt,
    _compute_angular_separation_robust,
    _create_capture_receipt,
    _parse_calendar_components,
    _verify_calendar_label_consistency,
    _wrap_angle_180,
    build_vector_provenance_record,
    validate_provenance_record_dict,
)

# Canonical benchmark catalog path
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "metadata" / "ephemeris" / "horizons_benchmark_catalog.json"
)


def validate_geometric_vectors(
    target_id: Union[int, str],
    location: Union[LunarSurfaceLocation, Any],
    iso_utc: str,
    http_client: Optional[Callable[..., Any]] = None,
    tolerances: Optional[Dict[str, float]] = None,
) -> Tuple[HorizonsVectorCaptureResult, Optional[GeometricVectorComparisonResult]]:
    """
    Orchestrate full geometric vector validation pipeline:
    1. Captures or mocks Horizons vector payload via capture_horizons_vector_pilot().
    2. Computes independent SPICE geometric state via compute_spice_geometric_state().
    3. If capture succeeds, evaluates residuals via compare_geometric_vectors().
    Returns (capture_result, comparison_result).
    """
    capture_res = capture_horizons_vector_pilot(
        target_id=target_id,
        location=location,
        iso_utc=iso_utc,
        http_client=http_client,
    )

    if not capture_res.success or capture_res.parsed_vector is None:
        return capture_res, None

    # Evaluate SPICE state
    spice_state = compute_spice_geometric_state(
        target_id=target_id,
        location=location,
        iso_utc=iso_utc,
    )

    comparison_res = compare_geometric_vectors(
        horizons_data=capture_res.parsed_vector,
        spice_state=spice_state,
        location=location,
        provenance_record=capture_res.provenance,
        tolerances=tolerances,
    )

    return capture_res, comparison_res


def validate_horizons_catalog(
    catalog_path: Optional[Union[str, Path]] = None,
    angular_tolerance_deg: float = PROVISIONAL_ANGULAR_RESIDUAL_TOLERANCE_DEG,
    distance_tolerance_km: float = PROVISIONAL_RANGE_RESIDUAL_TOLERANCE_KM,
) -> Dict[str, Any]:
    """
    Verify the 25-epoch JPL Horizons benchmark catalog against SPICE ephemerides.
    Computes RMS error, maximum error, and pass/fail status per target body.
    """
    path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Horizons benchmark catalog not found at {path}")

    with path.open("r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Ensure kernels are loaded
    _load()

    total_cases = 0
    passed_cases = 0
    sun_errors: List[float] = []
    earth_errors: List[float] = []
    case_results: List[Dict[str, Any]] = []

    for key, entry in catalog.items():
        epoch = entry["epoch"]
        iso_utc = epoch if epoch.endswith("Z") else f"{epoch}Z"
        site_info = entry["site"]
        loc = LunarSurfaceLocation(
            latitude_deg=site_info["lat"],
            longitude_deg=site_info["lon"],
            altitude_m=site_info.get("alt_m", site_info.get("alt_km", 0.0) * 1000.0),
            site_name=key,
        )

        case_summary: Dict[str, Any] = {"case_id": key, "epoch": epoch, "targets": {}}

        # Evaluate Sun (target 10)
        if "sun" in entry:
            sun_ref = entry["sun"]
            sun_spice = compute_spice_geometric_state(10, loc, iso_utc)
            az_diff = _wrap_angle_180(sun_ref["azimuth_deg"] - sun_spice.azimuth_deg)
            el_diff = sun_ref["elevation_deg"] - sun_spice.elevation_deg
            ang_err = math.sqrt(az_diff * az_diff * math.cos(math.radians(sun_ref["elevation_deg"])) ** 2 + el_diff * el_diff)
            sun_errors.append(ang_err)
            sun_pass = ang_err <= angular_tolerance_deg
            case_summary["targets"]["sun"] = {
                "angular_error_deg": ang_err,
                "passed": sun_pass,
            }

        # Evaluate Earth (target 399)
        if "earth" in entry:
            earth_ref = entry["earth"]
            earth_spice = compute_spice_geometric_state(399, loc, iso_utc)
            az_diff = _wrap_angle_180(earth_ref["azimuth_deg"] - earth_spice.azimuth_deg)
            el_diff = earth_ref["elevation_deg"] - earth_spice.elevation_deg
            ang_err = math.sqrt(az_diff * az_diff * math.cos(math.radians(earth_ref["elevation_deg"])) ** 2 + el_diff * el_diff)
            earth_errors.append(ang_err)
            earth_pass = ang_err <= angular_tolerance_deg
            case_summary["targets"]["earth"] = {
                "angular_error_deg": ang_err,
                "passed": earth_pass,
            }

        case_pass = all(t["passed"] for t in case_summary["targets"].values())
        if case_pass:
            passed_cases += 1
        total_cases += 1
        case_summary["all_passed"] = case_pass
        case_results.append(case_summary)

    sun_rms = float(np.sqrt(np.mean(np.square(sun_errors)))) if sun_errors else 0.0
    earth_rms = float(np.sqrt(np.mean(np.square(earth_errors)))) if earth_errors else 0.0

    return {
        "catalog_path": str(path),
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "all_passed": passed_cases == total_cases,
        "sun_rms_angular_error_deg": sun_rms,
        "earth_rms_angular_error_deg": earth_rms,
        "sun_max_angular_error_deg": max(sun_errors) if sun_errors else 0.0,
        "earth_max_angular_error_deg": max(earth_errors) if earth_errors else 0.0,
        "cases": case_results,
    }
