"""
LUNA-SCOPE — NASA JPL Horizons Query Construction, Response Parsing, and Hardened Capture Pipeline.

Complies with E1-R6 §5, §6.2, §7, and Phase C0 Hardened Bounded Capture:
- Canonical observer query construction (EPHEM_TYPE=OBSERVER, QUANTITIES=4,20).
- Canonical geometric vector query construction (EPHEM_TYPE=VECTORS, VEC_TABLE=2).
- Dynamic CSV header parser for geometric vectors without positional fallback.
- Hardened HTTP capture pipeline:
  - 5 MiB maximum response limit.
  - Upfront Content-Length header check.
  - 64 KiB chunked stream reading with cumulative size enforcement.
  - Equivalent size bounds on HTTPError bodies.
  - Structured RESPONSE_TOO_LARGE error classification.
  - Post-read retrieval timestamp.
  - Redirect final URL and URL hash consistency.
  - Sensitive header redaction and network timeouts.
"""

from __future__ import annotations

import csv
import dataclasses
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import re
import socket
import ssl
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

from .geometric_state import (
    LunarSurfaceLocation,
    SpiceGeometricState,
    compute_spice_geometric_state,
)
from .provenance import (
    _CAPTURE_TOKEN,
    _CaptureReceipt,
    _create_capture_receipt,
    HorizonsQueryError,
    SOURCE_CLASSIFICATION_VERIFIED_PILOT,
    VectorProvenanceRecord,
    build_vector_provenance_record,
)

HORIZONS_API_BASE_URL: str = "https://ssd.jpl.nasa.gov/api/horizons.api"

# Hardened capture limits (Phase C0)
MAX_CAPTURE_BYTES: int = 5 * 1024 * 1024  # 5 MiB
READ_CHUNK_SIZE: int = 64 * 1024          # 64 KiB


@dataclasses.dataclass(frozen=True)
class ParsedHorizonsVectorData:
    """Structured geometric Cartesian state vector extracted from Horizons CSV table (VEC_TABLE=2)."""
    x_km: float
    y_km: float
    z_km: float
    vx_kms: float
    vy_kms: float
    vz_kms: float
    epoch_str: str
    raw_headers: str


@dataclasses.dataclass(frozen=True)
class HorizonsVectorCaptureResult:
    """Outcome of a Horizons geometric vector capture attempt."""
    success: bool
    target_id: int
    target_name: str
    requested_epoch_utc: str
    request_url: str
    request_url_sha256: str
    http_status: Optional[int] = None
    response_headers: Dict[str, str] = dataclasses.field(default_factory=dict)
    timestamp_utc: Optional[str] = None
    raw_response_bytes: Optional[bytes] = None
    response_bytes_sha256: Optional[str] = None
    parsed_vector: Optional[ParsedHorizonsVectorData] = None
    provenance: Optional[VectorProvenanceRecord] = None
    error: Optional[str] = None
    error_classification: Optional[str] = None
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.success

    def to_dict(self) -> Dict[str, Any]:
        """Serialize capture result cleanly separated into http_outcome, parsed_vector, and provenance."""
        return {
            "http_outcome": {
                "success": self.success,
                "http_status": self.http_status,
                "request_url": self.request_url,
                "request_url_sha256": self.request_url_sha256,
                "response_bytes_sha256": self.response_bytes_sha256,
                "timestamp_utc": self.timestamp_utc,
                "response_headers": self.response_headers,
                "has_response_bytes": self.raw_response_bytes is not None,
                "response_bytes_length": len(self.raw_response_bytes) if self.raw_response_bytes else 0,
                "error": self.error,
                "error_classification": self.error_classification,
            },
            "parsed_vector": {
                "x_km": self.parsed_vector.x_km,
                "y_km": self.parsed_vector.y_km,
                "z_km": self.parsed_vector.z_km,
                "vx_kms": self.parsed_vector.vx_kms,
                "vy_kms": self.parsed_vector.vy_kms,
                "vz_kms": self.parsed_vector.vz_kms,
                "epoch_str": self.parsed_vector.epoch_str,
            } if self.parsed_vector else None,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


def _format_coord(val: float) -> str:
    """Format floating point coordinate cleanly without unnecessary trailing zeros."""
    s = f"{val:.6f}".rstrip("0").rstrip(".")
    return s if s else "0.0"


def build_horizons_observer_url(
    target_id: Union[int, str],
    location: Union[LunarSurfaceLocation, Any],
    iso_utc: str,
) -> str:
    """
    Construct the canonical NASA JPL Horizons API URL for an apparent observer ephemeris query (E1-R6 §5.1).
    """
    if isinstance(target_id, int):
        tid_str = str(target_id)
    else:
        t_clean = str(target_id).strip().upper()
        if t_clean in ("10", "SUN"):
            tid_str = "10"
        elif t_clean in ("399", "EARTH"):
            tid_str = "399"
        else:
            tid_str = t_clean

    lat = getattr(location, "latitude_deg", 0.0)
    lon = getattr(location, "longitude_deg", getattr(location, "longitude_deg_east", 0.0))
    alt_m = getattr(location, "altitude_m", getattr(location, "elevation_m", 0.0))

    clean_time = iso_utc.replace("T", " ").replace("Z", "").strip()
    site_coord_str = f"{_format_coord(lon)},{_format_coord(lat)},{_format_coord(alt_m / 1000.0)}"

    params = {
        "format": "json",
        "COMMAND": f"'{tid_str}'",
        "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{site_coord_str}'",
        "EPHEM_TYPE": "'OBSERVER'",
        "QUANTITIES": "'4,20'",
        "APPARENT": "'AIRLESS'",
        "RANGE_UNITS": "'KM'",
        "TIME_TYPE": "'UT'",
        "TIME_ZONE": "'+00:00'",
        "TIME_DIGITS": "'SECONDS'",
        "TLIST": f"'{clean_time}'",
        "CSV_FORMAT": "'YES'",
    }
    return f"{HORIZONS_API_BASE_URL}?{urllib.parse.urlencode(params)}"


def build_horizons_vector_url(
    target_id: Union[int, str],
    location: Union[LunarSurfaceLocation, Any],
    iso_utc: str,
) -> str:
    """
    Construct the canonical NASA JPL Horizons API URL for a geometric Cartesian vector query (E1-R6 §6.2).
    """
    if isinstance(target_id, int):
        tid_str = str(target_id)
    else:
        t_clean = str(target_id).strip().upper()
        if t_clean in ("10", "SUN"):
            tid_str = "10"
        elif t_clean in ("399", "EARTH"):
            tid_str = "399"
        else:
            tid_str = t_clean

    lat = getattr(location, "latitude_deg", 0.0)
    lon = getattr(location, "longitude_deg", getattr(location, "longitude_deg_east", 0.0))
    alt_m = getattr(location, "altitude_m", getattr(location, "elevation_m", 0.0))

    clean_time = iso_utc.replace("T", " ").replace("Z", "").strip()
    site_coord_str = f"{_format_coord(lon)},{_format_coord(lat)},{_format_coord(alt_m / 1000.0)}"

    params = {
        "format": "json",
        "COMMAND": f"'{tid_str}'",
        "CENTER": "'coord@301'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{site_coord_str}'",
        "EPHEM_TYPE": "'VECTORS'",
        "VEC_TABLE": "'2'",
        "VEC_CORR": "'NONE'",
        "REF_SYSTEM": "'ICRF'",
        "REF_PLANE": "'FRAME'",
        "TIME_TYPE": "'UT'",
        "TIME_DIGITS": "'SECONDS'",
        "TLIST": f"'{clean_time}'",
        "TLIST_TYPE": "'CAL'",
        "CSV_FORMAT": "'YES'",
    }
    return f"{HORIZONS_API_BASE_URL}?{urllib.parse.urlencode(params)}"


def parse_horizons_vector_csv(result_text: str) -> ParsedHorizonsVectorData:
    """
    Parse a NASA JPL Horizons geometric Cartesian state-vector table CSV response (VEC_TABLE=2).
    Extracts data block between $$SOE and $$EOE and dynamically maps columns without positional indexing.
    """
    text_to_parse = result_text
    if isinstance(result_text, str) and result_text.strip().startswith("{"):
        try:
            payload = json.loads(result_text)
            if isinstance(payload, dict) and "result" in payload:
                text_to_parse = payload["result"]
        except Exception:
            pass

    if "$$SOE" not in text_to_parse or "$$EOE" not in text_to_parse:
        raise HorizonsQueryError(
            "Horizons vector response did not contain $$SOE/$$EOE data block.",
            classification="RESPONSE_ERROR",
            details={"raw_length": len(text_to_parse)},
        )

    parts_soe = text_to_parse.split("$$SOE", 1)
    pre_soe = parts_soe[0]
    parts_eoe = parts_soe[1].split("$$EOE", 1)
    data_block = parts_eoe[0].strip()

    if not data_block:
        raise HorizonsQueryError(
            "Empty data block between $$SOE and $$EOE in vector response.",
            classification="RESPONSE_ERROR",
        )

    raw_lines = [l.strip() for l in data_block.splitlines() if l.strip()]
    if not raw_lines:
        raise HorizonsQueryError(
            "No data lines found between $$SOE and $$EOE in vector response.",
            classification="RESPONSE_ERROR",
        )

    header_line: Optional[str] = None
    data_lines = raw_lines

    # Search backwards from $$SOE for CSV header row
    pre_lines = [l.strip() for l in pre_soe.splitlines() if l.strip()]
    for line in reversed(pre_lines):
        if line.startswith("*****") or line.startswith("-----") or line.startswith("====="):
            continue
        if "," in line:
            tokens = [t.strip().lower() for t in line.split(",") if t.strip()]
            if any(t in {"x", "y", "z", "vx", "vy", "vz", "x_km", "vx_kms"} for t in tokens):
                header_line = line
                break

    # Check if first line of data block is header
    if header_line is None:
        first_line = raw_lines[0]
        if "," in first_line:
            tokens = [t.strip().lower() for t in first_line.split(",") if t.strip()]
            if any(t in {"x", "y", "z", "vx", "vy", "vz", "x_km", "vx_kms"} for t in tokens):
                header_line = first_line
                data_lines = raw_lines[1:]

    if header_line is None:
        raise HorizonsQueryError(
            "Could not locate dynamic CSV header row preceding $$SOE or in data block for vector response.",
            classification="PARSE_ERROR",
        )

    if not data_lines:
        raise HorizonsQueryError(
            "No data rows found following CSV header in Horizons vector response.",
            classification="RESPONSE_ERROR",
        )

    reader = csv.reader(io.StringIO(header_line))
    try:
        header_cols = [c.strip() for c in next(reader)]
    except Exception as e:
        raise HorizonsQueryError(
            f"Failed to parse CSV header row: {e}",
            classification="PARSE_ERROR",
            details={"header_line": header_line},
        )

    matches: Dict[str, List[int]] = {
        "x": [], "y": [], "z": [], "vx": [], "vy": [], "vz": [], "date": []
    }

    for idx, raw_col in enumerate(header_cols):
        norm = raw_col.lower().replace('"', '').replace("'", "").strip()
        if not norm:
            continue
        if norm in {"x", "x_km", "x(km)", "x (km)"}:
            matches["x"].append(idx)
        elif norm in {"y", "y_km", "y(km)", "y (km)"}:
            matches["y"].append(idx)
        elif norm in {"z", "z_km", "z(km)", "z (km)"}:
            matches["z"].append(idx)
        elif norm in {"vx", "vx_kms", "vx(km/s)", "vx (km/s)", "vx_km/s", "vx_km_s", "vx (km/sec)"}:
            matches["vx"].append(idx)
        elif norm in {"vy", "vy_kms", "vy(km/s)", "vy (km/s)", "vy_km/s", "vy_km_s", "vy (km/sec)"}:
            matches["vy"].append(idx)
        elif norm in {"vz", "vz_kms", "vz(km/s)", "vz (km/s)", "vz_km/s", "vz_km_s", "vz (km/sec)"}:
            matches["vz"].append(idx)
        elif "date" in norm or "calendar" in norm or "jd" in norm or norm in {"time", "datetime"}:
            matches["date"].append(idx)

    # Check for ambiguity
    ambiguous = {f: idxs for f, idxs in matches.items() if len(idxs) > 1 and f in {"x", "y", "z", "vx", "vy", "vz"}}
    if ambiguous:
        raise HorizonsQueryError(
            f"Ambiguous vector column header: multiple columns matched required field(s): {ambiguous}.",
            classification="PARSE_ERROR",
        )

    # Check for missing columns
    missing = [f for f in ["x", "y", "z", "vx", "vy", "vz"] if not matches[f]]
    if missing:
        raise HorizonsQueryError(
            f"Missing required vector column(s): {missing}. Found columns: {header_cols}",
            classification="PARSE_ERROR",
        )

    first_row_text = data_lines[0]
    row_reader = csv.reader(io.StringIO(first_row_text))
    try:
        row_cols = [c.strip() for c in next(row_reader)]
    except Exception as e:
        raise HorizonsQueryError(
            f"Failed to parse CSV data row: {e}",
            classification="PARSE_ERROR",
        )

    max_idx = max(matches[k][0] for k in ["x", "y", "z", "vx", "vy", "vz"])
    if len(row_cols) <= max_idx:
        raise HorizonsQueryError(
            f"Data row has {len(row_cols)} columns, required index {max_idx}.",
            classification="PARSE_ERROR",
        )

    def _parse_val(field_name: str) -> float:
        col_idx = matches[field_name][0]
        val_str = row_cols[col_idx]
        try:
            val = float(val_str)
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Value is {val}")
            return val
        except Exception:
            raise HorizonsQueryError(
                f"Numerical value for vector component '{field_name}' is NaN or Inf: {val_str}",
                classification="PARSE_ERROR",
            )

    x_val = _parse_val("x")
    y_val = _parse_val("y")
    z_val = _parse_val("z")
    vx_val = _parse_val("vx")
    vy_val = _parse_val("vy")
    vz_val = _parse_val("vz")

    epoch_val = ""
    if matches["date"]:
        d_idx = matches["date"][0]
        if d_idx < len(row_cols):
            epoch_val = row_cols[d_idx]

    return ParsedHorizonsVectorData(
        x_km=x_val,
        y_km=y_val,
        z_km=z_val,
        vx_kms=vx_val,
        vy_kms=vy_val,
        vz_kms=vz_val,
        epoch_str=epoch_val,
        raw_headers=header_line,
    )


def parse_horizons_observer_response(response_text: str) -> Dict[str, Any]:
    """
    Parse a NASA JPL Horizons apparent observer table CSV response (Stage A).
    """
    text = response_text
    if isinstance(response_text, str) and response_text.strip().startswith("{"):
        try:
            payload = json.loads(response_text)
            if isinstance(payload, dict) and "result" in payload:
                text = payload["result"]
        except Exception:
            pass

    if "$$SOE" not in text or "$$EOE" not in text:
        raise HorizonsQueryError(
            "Horizons observer response did not contain $$SOE/$$EOE markers.",
            classification="RESPONSE_ERROR",
        )

    parts_soe = text.split("$$SOE", 1)
    parts_eoe = parts_soe[1].split("$$EOE", 1)
    data_lines = [l.strip() for l in parts_eoe[0].strip().splitlines() if l.strip()]

    if not data_lines:
        raise HorizonsQueryError("Empty data block in observer response.", classification="RESPONSE_ERROR")

    row = list(csv.reader(io.StringIO(data_lines[0])))[0]
    row = [c.strip() for c in row]

    # Typical observer CSV: Date, (blanks), Azimuth, Elevation, Range, Range-rate
    return {
        "raw_row": row,
        "date": row[0] if len(row) > 0 else "",
        "azimuth_deg": float(row[3]) if len(row) > 3 else 0.0,
        "elevation_deg": float(row[4]) if len(row) > 4 else 0.0,
        "range_km": float(row[5]) if len(row) > 5 else 0.0,
    }


def _read_bounded(
    stream: Any,
    max_bytes: int = MAX_CAPTURE_BYTES,
    chunk_size: int = READ_CHUNK_SIZE,
) -> bytes:
    """
    Read an HTTP response stream in bounded chunks, enforcing a strict maximum size.
    Raises HorizonsQueryError(classification="RESPONSE_TOO_LARGE") if bytes exceed max_bytes.
    """
    chunks: List[bytes] = []
    total = 0

    while True:
        # Request up to chunk_size or remaining allowed bytes + 1 to detect overflow
        to_read = min(chunk_size, (max_bytes - total) + 1)
        if hasattr(stream, "read"):
            try:
                chunk = stream.read(to_read)
            except TypeError:
                # Mock client read without arguments
                chunk = stream.read()
        else:
            chunk = b""

        if not chunk:
            break

        total += len(chunk)
        if total > max_bytes:
            raise HorizonsQueryError(
                f"Response body exceeded maximum allowed size of {max_bytes} bytes ({max_bytes // (1024 * 1024)} MiB).",
                classification="RESPONSE_TOO_LARGE",
                details={"max_bytes": max_bytes, "bytes_read": total},
            )

        chunks.append(chunk)
        if len(chunk) < to_read:
            break

    return b"".join(chunks)


def capture_horizons_vector_pilot(
    target_id: Union[int, str],
    location: Union[LunarSurfaceLocation, Any],
    iso_utc: str,
    timeout_sec: float = 15.0,
    http_client: Optional[Callable[..., Any]] = None,
    spice_manager: Optional[Any] = None,
    spice_state: Optional[SpiceGeometricState] = None,
    max_bytes: int = MAX_CAPTURE_BYTES,
) -> HorizonsVectorCaptureResult:
    """
    Execute a controlled, hardened, auditable HTTP capture operation for NASA JPL Horizons
    geometric Cartesian state-vector responses, complying strictly with E1-R6 §6.2, §7, §8.

    Hardened Safeguards:
    1. Maximum 5 MiB response ceiling.
    2. Content-Length header verification upfront.
    3. 64 KiB chunked stream reading with cumulative size bound.
    4. Size bounds applied to HTTP error bodies.
    5. Structured RESPONSE_TOO_LARGE classification.
    6. Post-read retrieval timestamp.
    7. Redirect final URL and URL hash consistency.
    8. Sensitive header redaction.
    """
    # 1. Normalize target_id
    if isinstance(target_id, int):
        tid_int = target_id
        target_name = "Sun" if tid_int == 10 else ("Earth" if tid_int == 399 else f"Target_{tid_int}")
    else:
        t_clean = str(target_id).strip().upper()
        if t_clean in ("10", "SUN"):
            tid_int = 10
            target_name = "Sun"
        elif t_clean in ("399", "EARTH"):
            tid_int = 399
            target_name = "Earth"
        else:
            try:
                tid_int = int(t_clean)
                target_name = f"Target_{tid_int}"
            except ValueError:
                return HorizonsVectorCaptureResult(
                    success=False,
                    target_id=-1,
                    target_name=str(target_id),
                    requested_epoch_utc=iso_utc,
                    request_url="",
                    request_url_sha256="",
                    error=f"INPUT_VALIDATION_ERROR: Invalid target_id '{target_id}'.",
                    error_classification="INPUT_VALIDATION_ERROR",
                )

    # 2. Build canonical request URL
    try:
        url = build_horizons_vector_url(target_id=tid_int, location=location, iso_utc=iso_utc)
    except Exception as e:
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url="",
            request_url_sha256="",
            error=f"INPUT_VALIDATION_ERROR: {e}",
            error_classification="INPUT_VALIDATION_ERROR",
        )

    initial_url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

    # 3. Perform HTTP GET through injectable client (or urllib)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 LUNA-SCOPE/2.0"})
    ctx = ssl.create_default_context()
    opener = http_client if http_client is not None else urllib.request.urlopen

    raw_bytes: Optional[bytes] = None
    bytes_hash: Optional[str] = None
    retrieval_timestamp_utc: Optional[str] = None
    status_code: Optional[int] = None
    headers: Dict[str, str] = {}
    final_url = url

    try:
        with opener(req, context=ctx, timeout=timeout_sec) as response:
            status_code = getattr(response, "status", getattr(response, "code", 200))
            if hasattr(response, "geturl"):
                final_url = response.geturl() or url

            # Capture and sanitize headers
            raw_hdrs = getattr(response, "headers", None)
            if raw_hdrs:
                sensitive = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
                headers = {k: v for k, v in dict(raw_hdrs).items() if k.lower() not in sensitive}

            # Check Content-Length upfront if declared
            cl_val = headers.get("Content-Length", headers.get("content-length"))
            if cl_val:
                try:
                    content_length = int(cl_val)
                    if content_length > max_bytes:
                        return HorizonsVectorCaptureResult(
                            success=False,
                            target_id=tid_int,
                            target_name=target_name,
                            requested_epoch_utc=iso_utc,
                            request_url=final_url,
                            request_url_sha256=hashlib.sha256(final_url.encode("utf-8")).hexdigest(),
                            http_status=status_code,
                            response_headers=headers,
                            error=f"RESPONSE_TOO_LARGE: Declared Content-Length {content_length} exceeds limit of {max_bytes} bytes.",
                            error_classification="RESPONSE_TOO_LARGE",
                            details={"content_length": content_length, "max_bytes": max_bytes},
                        )
                except ValueError:
                    pass

            # Read stream in bounded chunks
            raw_bytes = _read_bounded(response, max_bytes=max_bytes)

            # Record timestamp strictly AFTER complete successful read
            retrieval_timestamp_utc = datetime.now(timezone.utc).isoformat()

    except HorizonsQueryError as e:
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=final_url,
            request_url_sha256=hashlib.sha256(final_url.encode("utf-8")).hexdigest(),
            http_status=status_code,
            response_headers=headers,
            error=e.message,
            error_classification=e.classification,
            details=e.details,
        )
    except urllib.error.HTTPError as e:
        status_code = e.code
        err_bytes = None
        if hasattr(e, "read"):
            try:
                err_bytes = _read_bounded(e, max_bytes=max_bytes)
            except HorizonsQueryError as qe:
                return HorizonsVectorCaptureResult(
                    success=False,
                    target_id=tid_int,
                    target_name=target_name,
                    requested_epoch_utc=iso_utc,
                    request_url=url,
                    request_url_sha256=initial_url_hash,
                    http_status=status_code,
                    error=f"RESPONSE_TOO_LARGE: Error response body exceeded limit of {max_bytes} bytes: {qe.message}",
                    error_classification="RESPONSE_TOO_LARGE",
                    details={"status_code": status_code, "max_bytes": max_bytes},
                )
        err_hash = hashlib.sha256(err_bytes).hexdigest() if err_bytes else None
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=url,
            request_url_sha256=initial_url_hash,
            http_status=status_code,
            raw_response_bytes=err_bytes,
            response_bytes_sha256=err_hash,
            error=f"HTTP_ERROR: HTTP status {status_code} {e.reason}",
            error_classification="HTTP_ERROR",
            details={"status_code": status_code, "reason": str(e.reason)},
        )
    except urllib.error.URLError as e:
        reason_str = str(e.reason)
        is_timeout = ("timed out" in reason_str.lower()) or isinstance(e.reason, socket.timeout)
        cls_name = "TIMEOUT_ERROR" if is_timeout else "NETWORK_ERROR"
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=url,
            request_url_sha256=initial_url_hash,
            error=f"{cls_name}: {reason_str}",
            error_classification=cls_name,
            details={"reason": reason_str},
        )
    except (socket.timeout, TimeoutError):
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=url,
            request_url_sha256=initial_url_hash,
            error=f"TIMEOUT_ERROR: Request timed out after {timeout_sec}s.",
            error_classification="TIMEOUT_ERROR",
            details={"timeout_sec": timeout_sec},
        )
    except Exception as e:
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=url,
            request_url_sha256=initial_url_hash,
            error=f"UNEXPECTED_ERROR: {type(e).__name__}: {e}",
            error_classification="UNEXPECTED_ERROR",
            details={"exception": str(e)},
        )

    # 4. Check status code and empty body
    final_url_hash = hashlib.sha256(final_url.encode("utf-8")).hexdigest()
    if raw_bytes is not None:
        bytes_hash = hashlib.sha256(raw_bytes).hexdigest()

    if status_code != 200:
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=final_url,
            request_url_sha256=final_url_hash,
            http_status=status_code,
            response_headers=headers,
            timestamp_utc=retrieval_timestamp_utc,
            raw_response_bytes=raw_bytes,
            response_bytes_sha256=bytes_hash,
            error=f"HTTP_ERROR: Non-200 HTTP status {status_code} received from Horizons API.",
            error_classification="HTTP_ERROR",
            details={"status_code": status_code},
        )

    if not raw_bytes or len(raw_bytes) == 0:
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=final_url,
            request_url_sha256=final_url_hash,
            http_status=200,
            response_headers=headers,
            timestamp_utc=retrieval_timestamp_utc,
            raw_response_bytes=b"",
            response_bytes_sha256=bytes_hash,
            error="EMPTY_RESPONSE_ERROR: Received zero response bytes from Horizons API.",
            error_classification="RESPONSE_ERROR",
            details={"raw_bytes_len": 0},
        )

    # 5. Parse response CSV payload
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    try:
        parsed_vector = parse_horizons_vector_csv(raw_text)
    except HorizonsQueryError as e:
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=final_url,
            request_url_sha256=final_url_hash,
            http_status=200,
            response_headers=headers,
            timestamp_utc=retrieval_timestamp_utc,
            raw_response_bytes=raw_bytes,
            response_bytes_sha256=bytes_hash,
            error=e.message,
            error_classification=e.classification,
            details=e.details,
        )

    # 6. Evaluate SPICE geometric state
    if spice_state is None:
        try:
            spice_state = compute_spice_geometric_state(
                target_id=tid_int,
                location=location,
                iso_utc=iso_utc,
                spice_manager=spice_manager,
            )
        except Exception as e:
            return HorizonsVectorCaptureResult(
                success=False,
                target_id=tid_int,
                target_name=target_name,
                requested_epoch_utc=iso_utc,
                request_url=final_url,
                request_url_sha256=final_url_hash,
                http_status=200,
                response_headers=headers,
                timestamp_utc=retrieval_timestamp_utc,
                raw_response_bytes=raw_bytes,
                response_bytes_sha256=bytes_hash,
                parsed_vector=parsed_vector,
                error=f"SPICE_EVALUATION_ERROR: {e}",
                error_classification="SPICE_CALCULATION_ERROR",
                details={"exception": str(e)},
            )

    # 7. Create capture receipt and verified provenance record
    try:
        receipt = _create_capture_receipt(
            request_url=final_url,
            raw_response_bytes=raw_bytes,
            http_status=200,
            timestamp_utc=retrieval_timestamp_utc,
            headers=headers,
        )

        provenance = build_vector_provenance_record(
            horizons_vector=parsed_vector,
            spice_state=spice_state,
            location=location,
            requested_epoch_raw=iso_utc,
            source_classification=SOURCE_CLASSIFICATION_VERIFIED_PILOT,
            capture_id=f"HORIZONS-PILOT-{tid_int}-{iso_utc}",
            timestamp_utc=retrieval_timestamp_utc,
            http_status=200,
            request_url=final_url,
            request_url_sha256=final_url_hash,
            response_bytes_sha256=bytes_hash,
            raw_response_bytes=raw_bytes,
            _capture_receipt=receipt,
        )
    except Exception as e:
        return HorizonsVectorCaptureResult(
            success=False,
            target_id=tid_int,
            target_name=target_name,
            requested_epoch_utc=iso_utc,
            request_url=final_url,
            request_url_sha256=final_url_hash,
            http_status=200,
            response_headers=headers,
            timestamp_utc=retrieval_timestamp_utc,
            raw_response_bytes=raw_bytes,
            response_bytes_sha256=bytes_hash,
            parsed_vector=parsed_vector,
            error=f"PROVENANCE_CONSTRUCTION_ERROR: {e}",
            error_classification="PROVENANCE_ERROR",
            details={"exception": str(e)},
        )

    return HorizonsVectorCaptureResult(
        success=True,
        target_id=tid_int,
        target_name=target_name,
        requested_epoch_utc=iso_utc,
        request_url=final_url,
        request_url_sha256=final_url_hash,
        http_status=200,
        response_headers=headers,
        timestamp_utc=retrieval_timestamp_utc,
        raw_response_bytes=raw_bytes,
        response_bytes_sha256=bytes_hash,
        parsed_vector=parsed_vector,
        provenance=provenance,
    )
