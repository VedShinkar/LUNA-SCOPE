"""
LUNA-SCOPE — Ephemeris Provenance and Verification Safeguards.

Implements E1-R6 §8:
- Cryptographic and operational lineage for Horizons vector data and SPICE state.
- Strict gating for VERIFIED_HORIZONS_PILOT requiring raw response bytes and capture receipts.
- E1-R6 §8.1 nested JSON schema serialization and validation.
- Provisional tolerance status constants.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Source classification constants (E1-R6 §8.1)
SOURCE_CLASSIFICATION_UNVERIFIED = "UNVERIFIED_SOURCE"
SOURCE_CLASSIFICATION_SYNTHETIC = "SYNTHETIC_FIXTURE"
SOURCE_CLASSIFICATION_VERIFIED_PILOT = "VERIFIED_HORIZONS_PILOT"

# Acceptance evaluation status constants (E1-R6 §8.1)
STATUS_WITHIN_PROVISIONAL_TOLERANCE = "WITHIN_PROVISIONAL_THRESHOLD"
STATUS_EXCEEDS_PROVISIONAL_TOLERANCE = "OUTSIDE_PROVISIONAL_THRESHOLD"
STATUS_NOT_ASSESSED = "NOT_ASSESSED"

# Provisional tolerances (E1-R6 §6.4)
PROVISIONAL_POSITION_RESIDUAL_TOLERANCE_KM = 1.0
PROVISIONAL_RANGE_RESIDUAL_TOLERANCE_KM = 5.0
PROVISIONAL_ANGULAR_RESIDUAL_TOLERANCE_DEG = 0.05

# Ephemeris track constants
EPHEMERIS_TRACK_GEOMETRIC_VECTORS = "GEOMETRIC_VECTORS"
EPHEMERIS_TRACK_APPARENT_OBSERVER = "APPARENT_OBSERVER"

SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)

# Module-level sentinel for trusted capture receipt authorization.
_CAPTURE_TOKEN: object = object()


class HorizonsQueryError(Exception):
    """Exception raised when Horizons query construction, network, parsing, or validation fails."""

    def __init__(
        self,
        message: str,
        classification: str = "HORIZONS_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(f"{classification}: {message}")
        self.message = message
        self.classification = classification
        self.details = details or {}


@dataclasses.dataclass(frozen=True)
class _CaptureReceipt:
    """
    Internal cryptographic receipt verifying that response bytes and metadata
    originated from the trusted HTTP capture pipeline (`capture_horizons_vector_pilot`).

    Trust boundary note:
    In Python within a single runtime process, module-private tokens do not provide
    cryptographic protection against arbitrary local bytecode modification or reflection.
    Their architectural purpose is controlled application-level construction, ensuring that
    ordinary public constructors and synthetic fixtures cannot inadvertently or directly
    promote themselves to VERIFIED_HORIZONS_PILOT without passing through the capture workflow.
    """
    token: object
    timestamp_utc: str
    request_url: str
    request_url_sha256: str
    http_status: int
    raw_response_bytes: bytes
    response_bytes_sha256: str
    headers: Optional[Dict[str, str]] = None


def _create_capture_receipt(
    request_url: str,
    raw_response_bytes: bytes,
    http_status: int = 200,
    timestamp_utc: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> _CaptureReceipt:
    """
    Construct an authorized capture receipt for a verified HTTP capture.

    Validates all mandatory capture preconditions:
    - Non-empty raw response bytes.
    - Exactly HTTP status 200.
    - Valid request URL and valid ISO-8601 retrieval timestamp.
    """
    if not isinstance(raw_response_bytes, (bytes, bytearray)) or len(raw_response_bytes) == 0:
        raise HorizonsQueryError(
            "Capture receipt requires non-empty raw response bytes.",
            classification="PROVENANCE_ERROR",
        )
    if http_status != 200:
        raise HorizonsQueryError(
            f"Capture receipt requires HTTP status 200, got {http_status}.",
            classification="PROVENANCE_ERROR",
            details={"http_status": http_status},
        )
    if not isinstance(request_url, str) or not request_url.strip():
        raise HorizonsQueryError(
            "Capture receipt requires non-empty request_url.",
            classification="PROVENANCE_ERROR",
        )

    ts = timestamp_utc or datetime.now(timezone.utc).isoformat()
    try:
        ts_clean = ts.rstrip("Z")
        if "+" in ts_clean:
            ts_clean = ts_clean.split("+")[0]
        datetime.fromisoformat(ts_clean)
    except Exception as e:
        raise HorizonsQueryError(
            f"Capture receipt invalid ISO timestamp: {ts}",
            classification="PROVENANCE_ERROR",
            details={"timestamp": ts, "error": str(e)},
        )

    computed_bytes_sha256 = hashlib.sha256(raw_response_bytes).hexdigest()
    computed_url_sha256 = hashlib.sha256(request_url.encode("utf-8")).hexdigest()

    return _CaptureReceipt(
        token=_CAPTURE_TOKEN,
        timestamp_utc=ts,
        request_url=request_url,
        request_url_sha256=computed_url_sha256,
        http_status=http_status,
        raw_response_bytes=bytes(raw_response_bytes),
        response_bytes_sha256=computed_bytes_sha256,
        headers=headers or {},
    )


@dataclasses.dataclass(frozen=True)
class VectorProvenanceRecord:
    """
    Formal provenance representation for geometric state-vector ephemeris data
    complying with E1-R6 §8.

    Captures cryptographic and operational lineage:
    - Capture identity and source classification
    - Retrieval metadata and byte-level verification hashes
    - Request parameters and observer site configuration
    - Canonical temporal fields (raw timestamp, calendar label, returned string, SPICE ET)
    - SPICE execution environment (kernel filenames and SHA-256 hashes)
    - Dynamic parser metadata and parsed values

    Provenance Restrictions (E1-R6 §8.1):
    - VERIFIED_HORIZONS_PILOT strictly requires original HTTP response bytes, from which
      response_bytes_sha256 is independently computed.
    - Caller-supplied hash strings cannot substitute for missing raw response bytes.
    - Hashes must strictly match ^[a-f0-9]{64}$.
    - Non-null request_url, request_url_sha256, http_status == 200, and genuine network
      retrieval timestamp_utc are mandatory for verified classification.
    - Object construction time must never substitute for network retrieval time.
    - Synthetic fixtures remain SYNTHETIC_FIXTURE or UNVERIFIED_SOURCE.
    """
    capture_id: str
    source_classification: str
    requested_epoch_raw: str
    requested_epoch_utc_label: str
    spice_et_sec: float
    target_id: int
    target_name: str
    observer_site_name: str
    observer_body_code: int = 301
    observer_latitude_deg: float = 0.0
    observer_longitude_deg: float = 0.0
    observer_altitude_m: float = 0.0
    coordinate_frame: str = "ICRF"
    ephemeris_track: str = EPHEMERIS_TRACK_GEOMETRIC_VECTORS

    returned_epoch_string: Optional[str] = None
    timestamp_utc: Optional[str] = None
    http_status: Optional[int] = None
    request_url: Optional[str] = None
    request_url_sha256: Optional[str] = None
    response_bytes_sha256: Optional[str] = None
    raw_response_bytes: Optional[bytes] = None
    request_parameters: Optional[Dict[str, str]] = None

    loaded_kernels: Optional[List[Dict[str, str]]] = None
    active_lsk: Optional[Dict[str, str]] = None
    parser_version: str = "2.0-B1"
    raw_header_line: Optional[str] = None
    column_map: Optional[Dict[str, int]] = None
    parsed_data: Optional[Dict[str, Any]] = None
    original_parsed_values: Optional[Dict[str, float]] = None
    provenance_note: str = (
        "Cryptographic provenance requires byte-level SHA-256 hashes of the original HTTP stream. "
        "Source classification must be VERIFIED_HORIZONS_PILOT only when raw response bytes and "
        "HTTP 200 status are independently verified."
    )
    _capture_receipt: Optional[Any] = None

    @property
    def observer_altitude_km(self) -> float:
        """Observer altitude in kilometers."""
        return self.observer_altitude_m / 1000.0

    def __post_init__(self):
        allowed_classifications = {
            SOURCE_CLASSIFICATION_UNVERIFIED,
            SOURCE_CLASSIFICATION_SYNTHETIC,
            SOURCE_CLASSIFICATION_VERIFIED_PILOT,
        }
        if self.source_classification not in allowed_classifications:
            raise HorizonsQueryError(
                f"Unknown source_classification '{self.source_classification}'. "
                f"Allowed: {sorted(allowed_classifications)}",
                classification="PROVENANCE_ERROR",
                details={"source_classification": self.source_classification},
            )

        # Sync parsed_data and original_parsed_values
        if self.parsed_data is None and self.original_parsed_values is not None:
            object.__setattr__(self, "parsed_data", self.original_parsed_values)
        elif self.original_parsed_values is None and self.parsed_data is not None:
            object.__setattr__(self, "original_parsed_values", self.parsed_data)

        # If raw_response_bytes provided, verify bytes and compute hash
        if self.raw_response_bytes is not None:
            if not isinstance(self.raw_response_bytes, (bytes, bytearray)):
                raise HorizonsQueryError(
                    f"raw_response_bytes must be bytes or bytearray, got {type(self.raw_response_bytes).__name__}.",
                    classification="PROVENANCE_ERROR",
                )
            computed_bytes_sha256 = hashlib.sha256(self.raw_response_bytes).hexdigest()
            if self.response_bytes_sha256 is not None:
                if self.response_bytes_sha256.lower() != computed_bytes_sha256.lower():
                    raise HorizonsQueryError(
                        f"Response bytes SHA-256 mismatch: expected {self.response_bytes_sha256}, "
                        f"computed {computed_bytes_sha256}.",
                        classification="PROVENANCE_ERROR",
                        details={
                            "expected": self.response_bytes_sha256,
                            "computed": computed_bytes_sha256,
                        },
                    )
            else:
                object.__setattr__(self, "response_bytes_sha256", computed_bytes_sha256)

        # Validate request URL SHA-256 if provided
        if self.request_url is not None and self.request_url_sha256 is not None:
            computed_url_sha256 = hashlib.sha256(self.request_url.encode("utf-8")).hexdigest()
            if self.request_url_sha256.lower() != computed_url_sha256.lower():
                raise HorizonsQueryError(
                    f"Request URL SHA-256 mismatch: expected {self.request_url_sha256}, "
                    f"computed {computed_url_sha256}.",
                    classification="PROVENANCE_ERROR",
                    details={
                        "expected": self.request_url_sha256,
                        "computed": computed_url_sha256,
                    },
                )

        # Strict gating for VERIFIED_HORIZONS_PILOT
        if self.source_classification == SOURCE_CLASSIFICATION_VERIFIED_PILOT:
            if self._capture_receipt is None:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT without an authorized capture receipt. "
                    "Caller must execute capture through capture_horizons_vector_pilot().",
                    classification="PROVENANCE_ERROR",
                    details={"capture_id": self.capture_id},
                )
            if not isinstance(self._capture_receipt, _CaptureReceipt) or self._capture_receipt.token is not _CAPTURE_TOKEN:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: invalid or forged capture receipt token.",
                    classification="PROVENANCE_ERROR",
                    details={"capture_id": self.capture_id},
                )

            # Receipt invariants
            if self._capture_receipt.raw_response_bytes != self.raw_response_bytes:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: raw response bytes do not match capture receipt.",
                    classification="PROVENANCE_ERROR",
                )
            if self._capture_receipt.request_url != self.request_url:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: request URL does not match capture receipt.",
                    classification="PROVENANCE_ERROR",
                )
            if self._capture_receipt.http_status != 200 or self.http_status != 200:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: capture receipt HTTP status must be 200.",
                    classification="PROVENANCE_ERROR",
                )

            # Mandatory capture metadata
            if self.raw_response_bytes is None or len(self.raw_response_bytes) == 0:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: original HTTP response bytes must be provided.",
                    classification="PROVENANCE_ERROR",
                    details={"capture_id": self.capture_id},
                )
            if not self.response_bytes_sha256 or not SHA256_HEX_PATTERN.match(self.response_bytes_sha256):
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: response_bytes_sha256 must be a valid 64-hex SHA-256.",
                    classification="PROVENANCE_ERROR",
                    details={"response_bytes_sha256": self.response_bytes_sha256},
                )
            if not self.request_url:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: request_url must be provided.",
                    classification="PROVENANCE_ERROR",
                    details={"capture_id": self.capture_id},
                )
            if not self.request_url_sha256 or not SHA256_HEX_PATTERN.match(self.request_url_sha256):
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: request_url_sha256 must be a valid 64-hex SHA-256.",
                    classification="PROVENANCE_ERROR",
                    details={"request_url_sha256": self.request_url_sha256},
                )
            if self.http_status != 200:
                raise HorizonsQueryError(
                    f"Cannot assign VERIFIED_HORIZONS_PILOT: http_status must be 200, got {self.http_status}.",
                    classification="PROVENANCE_ERROR",
                    details={"http_status": self.http_status},
                )
            if not self.timestamp_utc:
                raise HorizonsQueryError(
                    "Cannot assign VERIFIED_HORIZONS_PILOT: timestamp_utc must be a verified retrieval timestamp.",
                    classification="PROVENANCE_ERROR",
                    details={"capture_id": self.capture_id},
                )
            try:
                ts_clean = self.timestamp_utc.rstrip("Z")
                if "+" in ts_clean:
                    ts_clean = ts_clean.split("+")[0]
                datetime.fromisoformat(ts_clean)
            except Exception as e:
                raise HorizonsQueryError(
                    f"Cannot assign VERIFIED_HORIZONS_PILOT: timestamp_utc is not a valid ISO 8601 string: '{self.timestamp_utc}'.",
                    classification="PROVENANCE_ERROR",
                    details={"timestamp_utc": self.timestamp_utc, "error": str(e)},
                )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary conforming to E1-R6 §8.1 nested schema.
        """
        # Verified capture metadata: non-null only for verified pilot
        verified_capture_metadata = None
        if self.source_classification == SOURCE_CLASSIFICATION_VERIFIED_PILOT:
            verified_capture_metadata = {
                "http_status": self.http_status,
                "request_url": self.request_url,
                "request_url_sha256": self.request_url_sha256,
                "response_bytes_sha256": self.response_bytes_sha256,
                "timestamp_utc": self.timestamp_utc,
            }

        # Format spice kernels list
        kernels_list = []
        if self.loaded_kernels:
            for k in self.loaded_kernels:
                if isinstance(k, dict):
                    kernels_list.append({
                        "file": k.get("file", k.get("filename", "")),
                        "sha256": k.get("sha256", ""),
                    })

        return {
            "source_classification": self.source_classification,
            "capture_id": self.capture_id,
            "requested_epoch_raw": self.requested_epoch_raw,
            "requested_epoch_utc_label": self.requested_epoch_utc_label,
            "spice_et_sec": self.spice_et_sec,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "observer_site_name": self.observer_site_name,
            "spice_kernels": kernels_list,
            "verified_capture_metadata": verified_capture_metadata,
            "returned_epoch_string": self.returned_epoch_string,
            "coordinate_frame": self.coordinate_frame,
            "ephemeris_track": self.ephemeris_track,
            "parser_version": self.parser_version,
            "provenance_note": self.provenance_note,
        }


def _parse_calendar_components(date_str: str) -> Optional[Tuple[int, int, int, int, int, int]]:
    """
    Parse calendar date components (year, month, day, hour, minute, second) from
    common ISO and Horizons date string formats.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    cleaned = date_str.strip()
    if cleaned.startswith("A.D."):
        cleaned = cleaned[4:].strip()
    elif cleaned.startswith("AD"):
        cleaned = cleaned[2:].strip()
    cleaned = cleaned.replace("T", " ").rstrip("Z")

    month_names = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    pattern = r"^(\d{4})[-/]([A-Za-z0-9]+)[-/](\d{1,2})(?:[\s]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?"
    m = re.match(pattern, cleaned)
    if not m:
        return None

    year = int(m.group(1))
    month_part = m.group(2).lower()
    if month_part.isdigit():
        month = int(month_part)
    elif month_part in month_names:
        month = month_names[month_part]
    else:
        return None

    day = int(m.group(3))
    hour = int(m.group(4)) if m.group(4) is not None else 0
    minute = int(m.group(5)) if m.group(5) is not None else 0
    second = int(m.group(6)) if m.group(6) is not None else 0

    return (year, month, day, hour, minute, second)


def _verify_calendar_label_consistency(spice_utc: str, horizons_epoch_str: Optional[str]) -> bool:
    """
    Verify calendar-level consistency between requested/SPICE UTC and Horizons returned epoch string.

    Raises HorizonsQueryError with classification EPOCH_MISMATCH_ERROR if the returned epoch
    represents a conflicting calendar timestamp.
    Returns True if verified consistent.
    Returns False if horizons_epoch_str is None or cannot be parsed as a calendar date.
    """
    if not horizons_epoch_str:
        return False

    spice_comp = _parse_calendar_components(spice_utc)
    if spice_comp is None:
        raise HorizonsQueryError(
            f"Invalid SPICE UTC format: '{spice_utc}'",
            classification="EPOCH_MISMATCH_ERROR",
            details={"spice_utc": spice_utc},
        )

    horizons_comp = _parse_calendar_components(horizons_epoch_str)
    if horizons_comp is None:
        return False

    if spice_comp != horizons_comp:
        raise HorizonsQueryError(
            f"Epoch mismatch: requested/SPICE UTC '{spice_utc}' does not match "
            f"Horizons returned calendar epoch '{horizons_epoch_str}'.",
            classification="EPOCH_MISMATCH_ERROR",
            details={
                "spice_utc": spice_utc,
                "horizons_epoch_str": horizons_epoch_str,
                "spice_components": spice_comp,
                "horizons_components": horizons_comp,
            },
        )

    return True


def _compute_angular_separation_robust(r1: Any, r2: Any) -> Tuple[float, float]:
    """
    Compute great-circle angular separation between two 3D vectors robustly:
        theta = atan2(||r1 x r2||, dot(r1, r2))
    Returns (theta_rad, theta_deg).
    """
    import numpy as np
    cross_v = np.cross(r1, r2)
    cross_norm = float(np.linalg.norm(cross_v))
    dot_val = float(np.dot(r1, r2))
    theta_rad = float(math.atan2(cross_norm, dot_val))
    if theta_rad < 0.0:
        theta_rad += 2.0 * math.pi
    theta_deg = float(math.degrees(theta_rad))
    return theta_rad, theta_deg


def _wrap_angle_180(angle_deg: float) -> float:
    """Wrap angular difference to [-180.0, +180.0] degrees."""
    return float((angle_deg + 180.0) % 360.0 - 180.0)



def build_vector_provenance_record(
    horizons_vector: Any,
    spice_state: Any,
    location: Any = None,
    requested_epoch_raw: Optional[str] = None,
    source_classification: str = SOURCE_CLASSIFICATION_UNVERIFIED,
    capture_id: Optional[str] = None,
    timestamp_utc: Optional[str] = None,
    http_status: Optional[int] = None,
    request_url: Optional[str] = None,
    request_url_sha256: Optional[str] = None,
    response_bytes_sha256: Optional[str] = None,
    raw_response_bytes: Optional[bytes] = None,
    request_parameters: Optional[Dict[str, str]] = None,
    loaded_kernels: Optional[List[Dict[str, str]]] = None,
    _capture_receipt: Optional[Any] = None,
) -> VectorProvenanceRecord:
    """
    Construct a formal VectorProvenanceRecord capturing cryptographic and operational lineage.
    """
    if location is not None:
        site_name = getattr(location, "site_name", getattr(location, "site_id", "UNKNOWN_SITE"))
        lat = getattr(location, "latitude_deg", 0.0)
        lon = getattr(location, "longitude_deg", getattr(location, "longitude_deg_east", 0.0))
        alt_m = getattr(location, "altitude_m", getattr(location, "elevation_m", 0.0))
    else:
        site_name = "APOLLO_11"
        lat = 0.67416
        lon = 23.47314
        alt_m = 0.0

    epoch_raw = requested_epoch_raw or getattr(spice_state, "requested_epoch_utc", "")
    target_id = getattr(spice_state, "target_id", 10)
    target_name = getattr(spice_state, "target_name", "Sun")
    spice_et = getattr(spice_state, "spice_et_sec", 0.0)

    # Format loaded kernels if not explicitly provided
    if loaded_kernels is None:
        loaded_kernels = []
        for name in ("lsk", "spk", "pck", "fk"):
            val = getattr(spice_state, f"{name}_sha256", None)
            if val:
                loaded_kernels.append({"file": name, "sha256": val})

    computed_bytes_sha256 = None
    if raw_response_bytes is not None:
        computed_bytes_sha256 = hashlib.sha256(raw_response_bytes).hexdigest()
    elif response_bytes_sha256 is not None:
        computed_bytes_sha256 = response_bytes_sha256

    computed_url_sha256 = None
    if request_url is not None:
        computed_url_sha256 = hashlib.sha256(request_url.encode("utf-8")).hexdigest()
    elif request_url_sha256 is not None:
        computed_url_sha256 = request_url_sha256

    actual_capture_id = capture_id or f"HORIZONS-VEC-{target_id}-{epoch_raw}"

    return VectorProvenanceRecord(
        capture_id=actual_capture_id,
        source_classification=source_classification,
        requested_epoch_raw=epoch_raw,
        requested_epoch_utc_label=getattr(spice_state, "requested_epoch_utc", epoch_raw),
        spice_et_sec=spice_et,
        target_id=target_id,
        target_name=target_name,
        observer_site_name=site_name,
        observer_body_code=301,
        observer_latitude_deg=lat,
        observer_longitude_deg=lon,
        observer_altitude_m=alt_m,
        coordinate_frame="ICRF",
        ephemeris_track=EPHEMERIS_TRACK_GEOMETRIC_VECTORS,
        returned_epoch_string=getattr(horizons_vector, "epoch_str", None),
        timestamp_utc=timestamp_utc,
        http_status=http_status,
        request_url=request_url,
        request_url_sha256=computed_url_sha256,
        response_bytes_sha256=computed_bytes_sha256,
        raw_response_bytes=raw_response_bytes,
        request_parameters=request_parameters,
        loaded_kernels=loaded_kernels,
        parser_version="2.0-B1",
        raw_header_line=getattr(horizons_vector, "raw_headers", None),
        _capture_receipt=_capture_receipt,
    )


# E1-R6 §8.1 JSON Schema for provenance validation
E1_R6_PROVENANCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "source_classification",
        "capture_id",
        "requested_epoch_raw",
        "requested_epoch_utc_label",
        "spice_et_sec",
        "target_id",
        "target_name",
        "observer_site_name",
        "spice_kernels",
        "verified_capture_metadata",
    ],
    "properties": {
        "source_classification": {
            "type": "string",
            "enum": [
                SOURCE_CLASSIFICATION_UNVERIFIED,
                SOURCE_CLASSIFICATION_SYNTHETIC,
                SOURCE_CLASSIFICATION_VERIFIED_PILOT,
            ],
        },
        "capture_id": {"type": "string"},
        "requested_epoch_raw": {"type": "string"},
        "requested_epoch_utc_label": {"type": "string"},
        "spice_et_sec": {"type": "number"},
        "target_id": {"type": "integer"},
        "target_name": {"type": "string"},
        "observer_site_name": {"type": "string"},
        "spice_kernels": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["file", "sha256"],
                "properties": {
                    "file": {"type": "string"},
                    "sha256": {"type": "string"},
                },
            },
        },
        "verified_capture_metadata": {
            "oneOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "required": [
                        "http_status",
                        "request_url",
                        "request_url_sha256",
                        "response_bytes_sha256",
                        "timestamp_utc",
                    ],
                    "properties": {
                        "http_status": {"type": "integer", "const": 200},
                        "request_url": {"type": "string"},
                        "request_url_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "response_bytes_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                        "timestamp_utc": {"type": "string"},
                    },
                },
            ]
        },
    },
}


def validate_provenance_record_dict(record_dict: Dict[str, Any]) -> bool:
    """
    Validate a serialized provenance record dictionary against E1-R6 §8.1.
    Uses jsonschema if installed; falls back to manual structural checks.
    """
    if HAS_JSONSCHEMA:
        jsonschema.validate(instance=record_dict, schema=E1_R6_PROVENANCE_SCHEMA)
        return True

    # Fallback validation if jsonschema not installed
    required = [
        "source_classification", "capture_id", "requested_epoch_raw",
        "requested_epoch_utc_label", "spice_et_sec", "target_id", "target_name",
        "observer_site_name", "spice_kernels", "verified_capture_metadata",
    ]
    for key in required:
        if key not in record_dict:
            raise ValueError(f"Missing required provenance field: {key}")

    sc = record_dict["source_classification"]
    if sc not in (SOURCE_CLASSIFICATION_UNVERIFIED, SOURCE_CLASSIFICATION_SYNTHETIC, SOURCE_CLASSIFICATION_VERIFIED_PILOT):
        raise ValueError(f"Invalid source_classification: {sc}")

    vcm = record_dict["verified_capture_metadata"]
    if sc == SOURCE_CLASSIFICATION_VERIFIED_PILOT:
        if not isinstance(vcm, dict):
            raise ValueError("verified_capture_metadata must be dict for verified pilot")
        for k in ("http_status", "request_url", "request_url_sha256", "response_bytes_sha256", "timestamp_utc"):
            if k not in vcm:
                raise ValueError(f"Missing verified_capture_metadata field: {k}")
        if vcm["http_status"] != 200:
            raise ValueError("http_status must be 200")
        if not SHA256_HEX_PATTERN.match(vcm["response_bytes_sha256"]):
            raise ValueError("Invalid response_bytes_sha256 format")
        if not SHA256_HEX_PATTERN.match(vcm["request_url_sha256"]):
            raise ValueError("Invalid request_url_sha256 format")
    else:
        if vcm is not None:
            raise ValueError("verified_capture_metadata must be null for unverified/synthetic")

    return True
