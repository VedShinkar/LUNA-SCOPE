"""
LUNA-SCOPE — Horizons–SPICE Geometric Vector Comparison Engine.

Implements E1-R6 §6.4:
- Direct component and Euclidean residual calculation between Horizons ICRF and SPICE J2000 vectors.
- Topocentric angular, range, and range-rate residuals.
- Rigorous provisional threshold evaluation (1 km position, 5 km range, 0.05 deg angular).
- Full structured result serialization matching E1-R6 §8.1.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

from .geometric_state import (
    LunarSurfaceLocation,
    SpiceGeometricState,
    enu_basis,
    vector_me_to_azel,
)
from .horizons import ParsedHorizonsVectorData
from .provenance import (
    HorizonsQueryError,
    PROVISIONAL_ANGULAR_RESIDUAL_TOLERANCE_DEG,
    PROVISIONAL_POSITION_RESIDUAL_TOLERANCE_KM,
    PROVISIONAL_RANGE_RESIDUAL_TOLERANCE_KM,
    STATUS_EXCEEDS_PROVISIONAL_TOLERANCE,
    STATUS_NOT_ASSESSED,
    STATUS_WITHIN_PROVISIONAL_TOLERANCE,
    VectorProvenanceRecord,
    _compute_angular_separation_robust,
    _verify_calendar_label_consistency,
    _wrap_angle_180,
    build_vector_provenance_record,
)


@dataclasses.dataclass(frozen=True)
class GeometricVectorComparisonResult:
    """
    Structured outcome of comparing a Horizons geometric Cartesian vector against
    an independently calculated SPICE geometric state at a shared requested UTC epoch.
    """
    target_id: int
    target_name: str
    requested_epoch_utc: str
    horizons_epoch_str: str

    pos_horizons_km: np.ndarray
    vel_horizons_kms: np.ndarray
    pos_spice_km: np.ndarray
    vel_spice_kms: np.ndarray

    pos_delta_km: np.ndarray
    pos_delta_norm_km: float
    vel_delta_kms: np.ndarray
    vel_delta_norm_kms: float

    range_horizons_km: float
    range_spice_km: float
    range_delta_km: float

    azimuth_horizons_deg: float
    azimuth_spice_deg: float
    azimuth_delta_deg: float

    elevation_horizons_deg: float
    elevation_spice_deg: float
    elevation_delta_deg: float

    angular_separation_deg: float
    range_rate_delta_kms: float

    position_status: str
    range_status: str
    angular_status: str
    overall_status: str
    is_provisional: bool = True

    tolerances_used: Dict[str, float] = dataclasses.field(default_factory=dict)
    provenance: Optional[VectorProvenanceRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize comparison result to dictionary conforming to E1-R6 §8.1."""
        return {
            "target_id": self.target_id,
            "target_name": self.target_name,
            "requested_epoch_utc": self.requested_epoch_utc,
            "horizons_epoch_str": self.horizons_epoch_str,
            "horizons_vector": {
                "pos_km": self.pos_horizons_km.tolist() if isinstance(self.pos_horizons_km, np.ndarray) else list(self.pos_horizons_km),
                "vel_kms": self.vel_horizons_kms.tolist() if isinstance(self.vel_horizons_kms, np.ndarray) else list(self.vel_horizons_kms),
                "range_km": self.range_horizons_km,
                "azimuth_deg": self.azimuth_horizons_deg,
                "elevation_deg": self.elevation_horizons_deg,
            },
            "spice_state": {
                "pos_km": self.pos_spice_km.tolist() if isinstance(self.pos_spice_km, np.ndarray) else list(self.pos_spice_km),
                "vel_kms": self.vel_spice_kms.tolist() if isinstance(self.vel_spice_kms, np.ndarray) else list(self.vel_spice_kms),
                "range_km": self.range_spice_km,
                "azimuth_deg": self.azimuth_spice_deg,
                "elevation_deg": self.elevation_spice_deg,
            },
            "residuals": {
                "pos_delta_km": self.pos_delta_km.tolist() if isinstance(self.pos_delta_km, np.ndarray) else list(self.pos_delta_km),
                "pos_delta_norm_km": self.pos_delta_norm_km,
                "vel_delta_kms": self.vel_delta_kms.tolist() if isinstance(self.vel_delta_kms, np.ndarray) else list(self.vel_delta_kms),
                "vel_delta_norm_kms": self.vel_delta_norm_kms,
                "range_delta_km": self.range_delta_km,
                "azimuth_delta_deg": self.azimuth_delta_deg,
                "elevation_delta_deg": self.elevation_delta_deg,
                "angular_separation_deg": self.angular_separation_deg,
                "range_rate_delta_kms": self.range_rate_delta_kms,
            },
            "acceptance_evaluation": {
                "position_status": self.position_status,
                "range_status": self.range_status,
                "angular_status": self.angular_status,
                "overall_status": self.overall_status,
                "is_provisional": self.is_provisional,
                "tolerances_used": self.tolerances_used,
            },
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


def compare_geometric_vectors(
    horizons_data: ParsedHorizonsVectorData,
    spice_state: SpiceGeometricState,
    location: Optional[Union[LunarSurfaceLocation, Any]] = None,
    provenance_record: Optional[VectorProvenanceRecord] = None,
    tolerances: Optional[Dict[str, float]] = None,
) -> GeometricVectorComparisonResult:
    """
    Quantify agreement between a Horizons geometric Cartesian state vector and
    an independently calculated SPICE geometric state at a shared requested UTC epoch.

    Evaluates:
    - Euclidean Cartesian position and velocity residuals in ICRF/J2000.
    - Local topocentric Azimuth, Elevation, Range, and radial Range-rate residuals.
    - Great-circle angular separation between target direction unit vectors.
    - Acceptance classification against provisional tolerances (E1-R6 §6.4).
    """
    # 1. Verify calendar epoch consistency
    _verify_calendar_label_consistency(
        spice_utc=spice_state.requested_epoch_utc,
        horizons_epoch_str=horizons_data.epoch_str,
    )

    # 2. Extract Cartesian vectors
    pos_horizons = np.array([horizons_data.x_km, horizons_data.y_km, horizons_data.z_km], dtype=np.float64)
    vel_horizons = np.array([horizons_data.vx_kms, horizons_data.vy_kms, horizons_data.vz_kms], dtype=np.float64)

    pos_spice = np.array(spice_state.pos_j2000_km, dtype=np.float64)
    vel_spice = np.array(spice_state.vel_j2000_kms, dtype=np.float64)

    # 3. Compute Cartesian residuals (Horizons - SPICE)
    pos_delta = pos_horizons - pos_spice
    pos_delta_norm = float(np.linalg.norm(pos_delta))

    vel_delta = vel_horizons - vel_spice
    vel_delta_norm = float(np.linalg.norm(vel_delta))

    # 4. Ranges and Range residual
    range_horizons = float(np.linalg.norm(pos_horizons))
    range_spice = float(spice_state.range_km)
    range_delta = range_horizons - range_spice

    # 5. Compute topocentric observables for Horizons vector
    # Project Horizons J2000 position into local ENU using observer location basis
    if location is not None:
        loc = location if isinstance(location, LunarSurfaceLocation) else LunarSurfaceLocation.from_observer(location)
    else:
        loc = LunarSurfaceLocation(latitude_deg=0.67416, longitude_deg=23.47314, altitude_m=0.0, site_name="Apollo 11")

    # In geometric tracking, convert relative ICRF vector into MOON_ME using the SPICE orientation at that epoch
    import spiceypy as sp
    et = spice_state.spice_et_sec
    sxform_j2000_to_me = sp.sxform("J2000", "MOON_ME", et)

    horizons_state_j2000 = np.hstack([pos_horizons, vel_horizons])
    horizons_state_me = np.dot(sxform_j2000_to_me, horizons_state_j2000)

    basis = enu_basis(loc.latitude_deg, loc.longitude_deg)
    pos_enu_horizons = np.dot(basis, horizons_state_me[0:3])
    vel_enu_horizons = np.dot(basis, horizons_state_me[3:6])

    az_horizons, el_horizons, _, rr_horizons = vector_me_to_azel(pos_enu_horizons, vel_enu_horizons)

    # 6. Topocentric Angular & Range-rate residuals
    az_spice = float(spice_state.azimuth_deg)
    el_spice = float(spice_state.elevation_deg)
    rr_spice = float(spice_state.range_rate_kms)

    az_delta = _wrap_angle_180(az_horizons - az_spice)
    el_delta = el_horizons - el_spice
    rr_delta = rr_horizons - rr_spice

    # 7. Robust great-circle angular separation
    _, angular_sep_deg = _compute_angular_separation_robust(pos_horizons, pos_spice)

    # 8. Evaluation against provisional tolerances
    tol = tolerances or {
        "position_km": PROVISIONAL_POSITION_RESIDUAL_TOLERANCE_KM,
        "range_km": PROVISIONAL_RANGE_RESIDUAL_TOLERANCE_KM,
        "angular_deg": PROVISIONAL_ANGULAR_RESIDUAL_TOLERANCE_DEG,
    }

    pos_tol = tol.get("position_km", PROVISIONAL_POSITION_RESIDUAL_TOLERANCE_KM)
    range_tol = tol.get("range_km", PROVISIONAL_RANGE_RESIDUAL_TOLERANCE_KM)
    ang_tol = tol.get("angular_deg", PROVISIONAL_ANGULAR_RESIDUAL_TOLERANCE_DEG)

    pos_status = STATUS_WITHIN_PROVISIONAL_TOLERANCE if pos_delta_norm <= pos_tol else STATUS_EXCEEDS_PROVISIONAL_TOLERANCE
    range_status = STATUS_WITHIN_PROVISIONAL_TOLERANCE if abs(range_delta) <= range_tol else STATUS_EXCEEDS_PROVISIONAL_TOLERANCE
    ang_status = STATUS_WITHIN_PROVISIONAL_TOLERANCE if angular_sep_deg <= ang_tol else STATUS_EXCEEDS_PROVISIONAL_TOLERANCE

    overall_status = STATUS_WITHIN_PROVISIONAL_TOLERANCE if (
        pos_status == STATUS_WITHIN_PROVISIONAL_TOLERANCE
        and range_status == STATUS_WITHIN_PROVISIONAL_TOLERANCE
        and ang_status == STATUS_WITHIN_PROVISIONAL_TOLERANCE
    ) else STATUS_EXCEEDS_PROVISIONAL_TOLERANCE

    # 9. Build or associate provenance
    if provenance_record is None:
        provenance = build_vector_provenance_record(
            horizons_vector=horizons_data,
            spice_state=spice_state,
            location=loc,
        )
    else:
        provenance = provenance_record

    return GeometricVectorComparisonResult(
        target_id=spice_state.target_id,
        target_name=spice_state.target_name,
        requested_epoch_utc=spice_state.requested_epoch_utc,
        horizons_epoch_str=horizons_data.epoch_str,
        pos_horizons_km=pos_horizons,
        vel_horizons_kms=vel_horizons,
        pos_spice_km=pos_spice,
        vel_spice_kms=vel_spice,
        pos_delta_km=pos_delta,
        pos_delta_norm_km=pos_delta_norm,
        vel_delta_kms=vel_delta,
        vel_delta_norm_kms=vel_delta_norm,
        range_horizons_km=range_horizons,
        range_spice_km=range_spice,
        range_delta_km=range_delta,
        azimuth_horizons_deg=az_horizons,
        azimuth_spice_deg=az_spice,
        azimuth_delta_deg=az_delta,
        elevation_horizons_deg=el_horizons,
        elevation_spice_deg=el_spice,
        elevation_delta_deg=el_delta,
        angular_separation_deg=angular_sep_deg,
        range_rate_delta_kms=rr_delta,
        position_status=pos_status,
        range_status=range_status,
        angular_status=ang_status,
        overall_status=overall_status,
        is_provisional=True,
        tolerances_used=tol,
        provenance=provenance,
    )
