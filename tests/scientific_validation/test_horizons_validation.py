"""
Deterministic offline pytest suite for Horizons–SPICE Scientific Validation Subsystem.

Complies with E1-R6 §5, §6, §7, §8, and Phase C0 Hardened Bounded Capture:
- Zero live network requests (100% offline).
- Horizons observer and geometric vector URL construction.
- Dynamic CSV header parsing without positional fallback.
- SPICE geometric state kinematics, 6x6 sxform, and ENU projections.
- Vector comparison engine residuals and provisional threshold evaluation.
- Provenance anti-forgery, receipt token identity check, and E1-R6 §8.1 schema.
- Hardened C0 capture: 5 MiB ceiling, 64 KiB chunked reads, Content-Length checks,
  error body limits, redirect URL consistency, and header redaction.
- Benchmark catalog verification.
"""

from datetime import datetime, timezone
import hashlib
import io
import json
import math
import urllib.error
import pytest
import numpy as np

from app.scientific_engines.ephemeris import (
    LunarSurfaceLocation,
    SpiceGeometricState,
    compute_spice_geometric_state,
    build_horizons_vector_url,
    build_horizons_observer_url,
    parse_horizons_vector_csv,
    parse_horizons_observer_response,
    capture_horizons_vector_pilot,
    HorizonsVectorCaptureResult,
    ParsedHorizonsVectorData,
    compare_geometric_vectors,
    GeometricVectorComparisonResult,
    VectorProvenanceRecord,
    build_vector_provenance_record,
    HorizonsQueryError,
    SOURCE_CLASSIFICATION_UNVERIFIED,
    SOURCE_CLASSIFICATION_SYNTHETIC,
    SOURCE_CLASSIFICATION_VERIFIED_PILOT,
    STATUS_WITHIN_PROVISIONAL_TOLERANCE,
    STATUS_EXCEEDS_PROVISIONAL_TOLERANCE,
    validate_horizons_catalog,
)
from app.scientific_engines.ephemeris.provenance import (
    _CAPTURE_TOKEN,
    _CaptureReceipt,
    _create_capture_receipt,
    E1_R6_PROVENANCE_SCHEMA,
    validate_provenance_record_dict,
)
from app.scientific_engines.ephemeris.horizons import (
    MAX_CAPTURE_BYTES,
    READ_CHUNK_SIZE,
)
from tests.scientific_validation.fixtures.horizons_vector_fixtures import (
    SYNTHETIC_SUN_JSON_PAYLOAD,
    SYNTHETIC_SUN_VECTOR_CSV,
    SYNTHETIC_EARTH_JSON_PAYLOAD,
    SYNTHETIC_EARTH_VECTOR_CSV,
)

# Apollo 11 Reference Location (E1-R6 §2.1)
APOLLO_11_LOC = LunarSurfaceLocation(
    latitude_deg=0.67416,
    longitude_deg=23.47314,
    altitude_m=0.0,
    site_name="Apollo 11",
)
PILOT_EPOCH_ISO = "2026-01-01T00:00:00Z"


class _MockChunkedResponse:
    """Mock HTTP response supporting read(size) bounded/chunked reads."""

    def __init__(
        self,
        data: bytes,
        status: int = 200,
        headers: dict = None,
        url: str = "https://ssd.jpl.nasa.gov/api/horizons.api",
    ):
        self._data = data
        self._pos = 0
        self.status = status
        self.code = status
        self.headers = headers or {"Content-Type": "application/json"}
        self._url = url

    def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""
        if size is None or size < 0:
            result = self._data[self._pos:]
            self._pos = len(self._data)
            return result
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class _MockChunkedHttpError(urllib.error.HTTPError):
    """Mock HTTPError with bounded chunked read support."""

    def __init__(self, url: str, code: int, msg: str, headers: dict, body: bytes):
        super().__init__(url, code, msg, headers, None)
        self._body = body
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._body):
            return b""
        if size is None or size < 0:
            result = self._body[self._pos:]
            self._pos = len(self._body)
            return result
        chunk = self._body[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


# =============================================================================
# 1. Horizons Query URL Construction Tests (E1-R6 §5.1, §6.2)
# =============================================================================

def test_observer_query_url_parameters():
    """Verify observer query URL contains all required E1-R6 parameters including TIME_ZONE."""
    url = build_horizons_observer_url(10, APOLLO_11_LOC, PILOT_EPOCH_ISO)
    assert "https://ssd.jpl.nasa.gov/api/horizons.api?" in url
    assert "EPHEM_TYPE=%27OBSERVER%27" in url or "EPHEM_TYPE='OBSERVER'" in url
    assert "QUANTITIES=%274%2C20%27" in url or "QUANTITIES='4,20'" in url
    assert "CENTER=%27coord%40301%27" in url or "CENTER='coord@301'" in url
    assert "APPARENT=%27AIRLESS%27" in url or "APPARENT='AIRLESS'" in url
    assert "RANGE_UNITS=%27KM%27" in url or "RANGE_UNITS='KM'" in url
    assert "TIME_TYPE=%27UT%27" in url or "TIME_TYPE='UT'" in url
    assert "TIME_ZONE=%27%2B00%3A00%27" in url or "TIME_ZONE='+00:00'" in url


def test_vector_query_url_parameters():
    """Verify vector query URL contains required parameters and strictly omits TIME_ZONE."""
    url = build_horizons_vector_url(10, APOLLO_11_LOC, PILOT_EPOCH_ISO)
    assert "https://ssd.jpl.nasa.gov/api/horizons.api?" in url
    assert "EPHEM_TYPE=%27VECTORS%27" in url or "EPHEM_TYPE='VECTORS'" in url
    assert "VEC_TABLE=%272%27" in url or "VEC_TABLE='2'" in url
    assert "VEC_CORR=%27NONE%27" in url or "VEC_CORR='NONE'" in url
    assert "REF_SYSTEM=%27ICRF%27" in url or "REF_SYSTEM='ICRF'" in url
    assert "REF_PLANE=%27FRAME%27" in url or "REF_PLANE='FRAME'" in url
    assert "TIME_TYPE=%27UT%27" in url or "TIME_TYPE='UT'" in url
    assert "TIME_ZONE" not in url  # Strict E1-R6 vector requirement


# =============================================================================
# 2. Dynamic CSV Header Parser Tests (E1-R6 §7)
# =============================================================================

def test_parse_horizons_vector_csv_synthetic_payload():
    """Verify parsing of valid synthetic Horizons vector response."""
    parsed = parse_horizons_vector_csv(SYNTHETIC_SUN_VECTOR_CSV)
    assert isinstance(parsed, ParsedHorizonsVectorData)
    assert parsed.x_km == pytest.approx(1.45e8)
    assert parsed.y_km == pytest.approx(2.5e7)
    assert parsed.z_km == pytest.approx(1.0e7)
    assert parsed.vx_kms == pytest.approx(-5.0)
    assert parsed.vy_kms == pytest.approx(28.0)
    assert parsed.vz_kms == pytest.approx(12.0)
    assert "2026-Jan-01" in parsed.epoch_str


def test_dynamic_header_reordering():
    """Verify columns mapped by name without positional fallback."""
    csv_text = (
        "VZ, VY, VX, Z, Y, X, Date\n"
        "$$SOE\n"
        "12.0, 28.0, -5.0, 1.0e7, 2.5e7, 1.45e8, 2026-Jan-01 00:00:00.0000\n"
        "$$EOE\n"
    )
    parsed = parse_horizons_vector_csv(csv_text)
    assert parsed.x_km == pytest.approx(1.45e8)
    assert parsed.vz_kms == pytest.approx(12.0)


def test_parser_rejects_missing_columns():
    """Verify error when required vector column is missing."""
    csv_missing_x = (
        "Date, Y, Z, VX, VY, VZ\n"
        "$$SOE\n"
        "2026-Jan-01, 2.0, 3.0, 4.0, 5.0, 6.0\n"
        "$$EOE\n"
    )
    with pytest.raises(HorizonsQueryError) as exc_info:
        parse_horizons_vector_csv(csv_missing_x)
    assert exc_info.value.classification == "PARSE_ERROR"
    assert "Missing required vector column" in exc_info.value.message


def test_parser_rejects_ambiguous_columns():
    """Verify error on duplicate column headers."""
    csv_duplicate_x = (
        "X, X, Y, Z, VX, VY, VZ\n"
        "$$SOE\n"
        "1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0\n"
        "$$EOE\n"
    )
    with pytest.raises(HorizonsQueryError) as exc_info:
        parse_horizons_vector_csv(csv_duplicate_x)
    assert exc_info.value.classification == "PARSE_ERROR"
    assert "Ambiguous" in exc_info.value.message


def test_parser_rejects_nan_values():
    """Verify error on NaN or non-finite values."""
    csv_nan = (
        "Date, X, Y, Z, VX, VY, VZ\n"
        "$$SOE\n"
        "2026-Jan-01, NaN, 2.0, 3.0, 4.0, 5.0, 6.0\n"
        "$$EOE\n"
    )
    with pytest.raises(HorizonsQueryError) as exc_info:
        parse_horizons_vector_csv(csv_nan)
    assert exc_info.value.classification == "PARSE_ERROR"
    assert "NaN or Inf" in exc_info.value.message


def test_parser_rejects_missing_delimiters():
    """Verify error when $$SOE or $$EOE is absent."""
    csv_no_delimiters = "Date, X, Y, Z, VX, VY, VZ\n1, 2, 3, 4, 5, 6, 7\n"
    with pytest.raises(HorizonsQueryError) as exc_info:
        parse_horizons_vector_csv(csv_no_delimiters)
    assert exc_info.value.classification == "RESPONSE_ERROR"


# =============================================================================
# 3. SPICE Geometric State Kinematics Tests (E1-R6 §6.3)
# =============================================================================

def test_spice_geometric_state_kinematics():
    """Verify SPICE geometric state construction, 6x6 sxform, and topocentric observables."""
    state = compute_spice_geometric_state(10, APOLLO_11_LOC, PILOT_EPOCH_ISO)
    assert isinstance(state, SpiceGeometricState)
    assert state.target_id == 10
    assert state.target_name == "Sun"
    assert state.requested_epoch_utc == PILOT_EPOCH_ISO

    # Check 3D vectors
    assert len(state.pos_j2000_km) == 3
    assert len(state.vel_j2000_kms) == 3
    assert len(state.pos_me_km) == 3
    assert len(state.vel_me_kms) == 3
    assert len(state.pos_enu_km) == 3
    assert len(state.vel_enu_kms) == 3

    # Physical reasonableness (Sun distance ~ 1 AU)
    assert 1.45e8 < state.range_km < 1.55e8
    assert 0.0 <= state.azimuth_deg < 360.0
    assert -90.0 <= state.elevation_deg <= 90.0

    # Range-rate consistency: (r . v) / ||r||
    expected_rr = float(np.dot(state.pos_enu_km, state.vel_enu_kms) / state.range_km)
    assert state.range_rate_kms == pytest.approx(expected_rr, rel=1e-6)

    # Kernel digests populated
    assert state.spk_sha256 is not None
    assert state.lsk_sha256 is not None


# =============================================================================
# 4. Horizons–SPICE Comparison Engine Tests (E1-R6 §6.4)
# =============================================================================

def test_compare_geometric_vectors_evaluation():
    """Verify comparison residuals calculation and provisional tolerance classification."""
    spice_state = compute_spice_geometric_state(10, APOLLO_11_LOC, PILOT_EPOCH_ISO)

    # Construct matching Horizons data with slight synthetic offset (< 1 km)
    x = float(spice_state.pos_j2000_km[0]) + 0.1
    y = float(spice_state.pos_j2000_km[1]) - 0.2
    z = float(spice_state.pos_j2000_km[2]) + 0.1
    vx = float(spice_state.vel_j2000_kms[0])
    vy = float(spice_state.vel_j2000_kms[1])
    vz = float(spice_state.vel_j2000_kms[2])

    data = ParsedHorizonsVectorData(
        x_km=x, y_km=y, z_km=z, vx_kms=vx, vy_kms=vy, vz_kms=vz,
        epoch_str="2026-Jan-01 00:00:00.0000",
        raw_headers="X, Y, Z, VX, VY, VZ, Date",
    )

    res = compare_geometric_vectors(data, spice_state, location=APOLLO_11_LOC)
    assert isinstance(res, GeometricVectorComparisonResult)
    assert res.pos_delta_norm_km < 1.0
    assert res.position_status == STATUS_WITHIN_PROVISIONAL_TOLERANCE
    assert res.range_status == STATUS_WITHIN_PROVISIONAL_TOLERANCE
    assert res.angular_status == STATUS_WITHIN_PROVISIONAL_TOLERANCE
    assert res.overall_status == STATUS_WITHIN_PROVISIONAL_TOLERANCE


def test_compare_geometric_vectors_detects_out_of_tolerance():
    """Verify threshold classification when position residual exceeds 1 km."""
    spice_state = compute_spice_geometric_state(10, APOLLO_11_LOC, PILOT_EPOCH_ISO)

    # Offset by 10 km
    x = float(spice_state.pos_j2000_km[0]) + 10.0
    y = float(spice_state.pos_j2000_km[1])
    z = float(spice_state.pos_j2000_km[2])

    data = ParsedHorizonsVectorData(
        x_km=x, y_km=y, z_km=z,
        vx_kms=float(spice_state.vel_j2000_kms[0]),
        vy_kms=float(spice_state.vel_j2000_kms[1]),
        vz_kms=float(spice_state.vel_j2000_kms[2]),
        epoch_str="2026-Jan-01 00:00:00.0000",
        raw_headers="X, Y, Z, VX, VY, VZ",
    )

    res = compare_geometric_vectors(data, spice_state, location=APOLLO_11_LOC)
    assert res.pos_delta_norm_km == pytest.approx(10.0, rel=1e-3)
    assert res.position_status == STATUS_EXCEEDS_PROVISIONAL_TOLERANCE
    assert res.overall_status == STATUS_EXCEEDS_PROVISIONAL_TOLERANCE


# =============================================================================
# 5. Provenance Record & E1-R6 Schema Tests (E1-R6 §8.1)
# =============================================================================

def test_provenance_schema_validation():
    """Verify VectorProvenanceRecord serialization conforms to E1-R6 §8.1 schema."""
    receipt = _create_capture_receipt(
        request_url="https://ssd.jpl.nasa.gov/api/horizons.api?cmd=10",
        raw_response_bytes=SYNTHETIC_SUN_JSON_PAYLOAD,
        http_status=200,
        timestamp_utc="2026-01-01T00:00:05Z",
    )

    rec = VectorProvenanceRecord(
        capture_id="TEST-PILOT-01",
        source_classification=SOURCE_CLASSIFICATION_VERIFIED_PILOT,
        requested_epoch_raw=PILOT_EPOCH_ISO,
        requested_epoch_utc_label=PILOT_EPOCH_ISO,
        spice_et_sec=100.0,
        target_id=10,
        target_name="Sun",
        observer_site_name="Apollo 11",
        http_status=200,
        request_url="https://ssd.jpl.nasa.gov/api/horizons.api?cmd=10",
        request_url_sha256=hashlib.sha256("https://ssd.jpl.nasa.gov/api/horizons.api?cmd=10".encode()).hexdigest(),
        raw_response_bytes=SYNTHETIC_SUN_JSON_PAYLOAD,
        response_bytes_sha256=hashlib.sha256(SYNTHETIC_SUN_JSON_PAYLOAD).hexdigest(),
        timestamp_utc="2026-01-01T00:00:05Z",
        loaded_kernels=[{"file": "de440s.bsp", "sha256": "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"}],
        _capture_receipt=receipt,
    )

    d = rec.to_dict()
    assert validate_provenance_record_dict(d) is True


def test_anti_forgery_rejects_verified_without_receipt():
    """Anti-forgery invariant: VERIFIED_HORIZONS_PILOT without receipt is strictly rejected."""
    with pytest.raises(HorizonsQueryError) as exc_info:
        VectorProvenanceRecord(
            capture_id="FORGERY-ATTEMPT",
            source_classification=SOURCE_CLASSIFICATION_VERIFIED_PILOT,
            requested_epoch_raw=PILOT_EPOCH_ISO,
            requested_epoch_utc_label=PILOT_EPOCH_ISO,
            spice_et_sec=100.0,
            target_id=10,
            target_name="Sun",
            observer_site_name="Apollo 11",
            raw_response_bytes=b"authentic payload",
            http_status=200,
            request_url="https://url",
            request_url_sha256=hashlib.sha256(b"https://url").hexdigest(),
            timestamp_utc="2026-01-01T00:00:00Z",
            _capture_receipt=None,  # Missing receipt!
        )
    assert exc_info.value.classification == "PROVENANCE_ERROR"
    assert "without an authorized capture receipt" in exc_info.value.message


def test_anti_forgery_rejects_invalid_token():
    """Anti-forgery invariant: receipt with invalid token sentinel is rejected."""
    fake_receipt = _CaptureReceipt(
        token="counterfeit_token",
        timestamp_utc="2026-01-01T00:00:00Z",
        request_url="https://url",
        request_url_sha256=hashlib.sha256(b"https://url").hexdigest(),
        http_status=200,
        raw_response_bytes=b"test",
        response_bytes_sha256=hashlib.sha256(b"test").hexdigest(),
    )
    with pytest.raises(HorizonsQueryError) as exc_info:
        VectorProvenanceRecord(
            capture_id="FAKE-TOKEN",
            source_classification=SOURCE_CLASSIFICATION_VERIFIED_PILOT,
            requested_epoch_raw=PILOT_EPOCH_ISO,
            requested_epoch_utc_label=PILOT_EPOCH_ISO,
            spice_et_sec=100.0,
            target_id=10,
            target_name="Sun",
            observer_site_name="Apollo 11",
            raw_response_bytes=b"test",
            http_status=200,
            request_url="https://url",
            request_url_sha256=hashlib.sha256(b"https://url").hexdigest(),
            timestamp_utc="2026-01-01T00:00:00Z",
            _capture_receipt=fake_receipt,
        )
    assert exc_info.value.classification == "PROVENANCE_ERROR"
    assert "forged capture receipt token" in exc_info.value.message


# =============================================================================
# 6. Hardened C0 Bounded Capture Pipeline Tests (Phase C0 Hardening)
# =============================================================================

def test_successful_bounded_capture_offline():
    """Verify complete successful capture pipeline using chunked offline response."""
    def mock_client(req, context=None, timeout=None):
        return _MockChunkedResponse(
            SYNTHETIC_SUN_JSON_PAYLOAD,
            status=200,
            headers={"Content-Type": "application/json", "Server": "NASA-SSD/1.0", "Set-Cookie": "secret"},
            url=req.full_url,
        )

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is True
    assert res.http_status == 200
    assert res.raw_response_bytes == SYNTHETIC_SUN_JSON_PAYLOAD
    assert res.response_bytes_sha256 == hashlib.sha256(SYNTHETIC_SUN_JSON_PAYLOAD).hexdigest()
    assert res.provenance is not None
    assert res.provenance.source_classification == SOURCE_CLASSIFICATION_VERIFIED_PILOT
    # Sensitive header redacted
    assert "Set-Cookie" not in res.response_headers
    assert "Server" in res.response_headers


def test_capture_rejects_declared_oversized_response():
    """Verify rejection upfront when Content-Length header exceeds 5 MiB."""
    oversized_len = MAX_CAPTURE_BYTES + 1024

    def mock_client(req, context=None, timeout=None):
        return _MockChunkedResponse(
            b"small body but declared large",
            status=200,
            headers={"Content-Length": str(oversized_len)},
            url=req.full_url,
        )

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is False
    assert res.error_classification == "RESPONSE_TOO_LARGE"
    assert "exceeds limit" in res.error
    assert res.provenance is None


def test_capture_rejects_missing_content_length_oversized():
    """Verify rejection during 64 KiB chunked read when response exceeds 5 MiB without header."""
    oversized_data = b"X" * (MAX_CAPTURE_BYTES + 1024)

    def mock_client(req, context=None, timeout=None):
        # No Content-Length header
        return _MockChunkedResponse(oversized_data, status=200, headers={}, url=req.full_url)

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is False
    assert res.error_classification == "RESPONSE_TOO_LARGE"
    assert "exceeded maximum allowed size" in res.error
    assert res.provenance is None


def test_capture_rejects_understated_content_length_oversized():
    """Verify rejection during chunked read when Content-Length is understated but stream exceeds 5 MiB."""
    oversized_data = b"Y" * (MAX_CAPTURE_BYTES + 500)

    def mock_client(req, context=None, timeout=None):
        # Understated Content-Length
        return _MockChunkedResponse(oversized_data, status=200, headers={"Content-Length": "100"}, url=req.full_url)

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is False
    assert res.error_classification == "RESPONSE_TOO_LARGE"
    assert res.provenance is None


def test_capture_rejects_oversized_http_error():
    """Verify equivalent 5 MiB bound enforced on HTTP error bodies."""
    oversized_err_data = b"E" * (MAX_CAPTURE_BYTES + 1024)

    def mock_client(req, context=None, timeout=None):
        raise _MockChunkedHttpError(req.full_url, 500, "Internal Server Error", {}, oversized_err_data)

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is False
    assert res.error_classification == "RESPONSE_TOO_LARGE"
    assert res.provenance is None


def test_capture_redirect_url_hash_consistency():
    """Verify consistent final redirected URL and URL SHA-256 in receipt and provenance."""
    redirect_url = "https://ssd.jpl.nasa.gov/api/horizons_redirected.api?cmd=10"
    redirect_url_hash = hashlib.sha256(redirect_url.encode("utf-8")).hexdigest()

    def mock_client(req, context=None, timeout=None):
        return _MockChunkedResponse(
            SYNTHETIC_SUN_JSON_PAYLOAD,
            status=200,
            url=redirect_url,  # Redirected target
        )

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is True
    assert res.request_url == redirect_url
    assert res.request_url_sha256 == redirect_url_hash
    assert res.provenance.request_url == redirect_url
    assert res.provenance.request_url_sha256 == redirect_url_hash


def test_capture_http_500_error_handling():
    """Verify HTTP 500 server error produces HTTP_ERROR result with body preserved and no provenance."""
    err_body = b"500 Internal Error Body"

    def mock_client(req, context=None, timeout=None):
        raise _MockChunkedHttpError(req.full_url, 500, "Internal Server Error", {}, err_body)

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is False
    assert res.http_status == 500
    assert res.raw_response_bytes == err_body
    assert res.error_classification == "HTTP_ERROR"
    assert res.provenance is None


def test_capture_timeout_error_handling():
    """Verify socket timeout produces TIMEOUT_ERROR result without provenance."""
    def mock_client(req, context=None, timeout=None):
        raise urllib.error.URLError("timed out")

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is False
    assert res.error_classification == "TIMEOUT_ERROR"
    assert res.provenance is None


def test_capture_empty_body_error_handling():
    """Verify HTTP 200 with zero bytes produces RESPONSE_ERROR without provenance."""
    def mock_client(req, context=None, timeout=None):
        return _MockChunkedResponse(b"", status=200, url=req.full_url)

    res = capture_horizons_vector_pilot(
        target_id=10,
        location=APOLLO_11_LOC,
        iso_utc=PILOT_EPOCH_ISO,
        http_client=mock_client,
    )

    assert res.success is False
    assert res.error_classification == "RESPONSE_ERROR"
    assert "zero response bytes" in res.error
    assert res.provenance is None


# =============================================================================
# 7. Benchmark Catalog Verification Test
# =============================================================================

def test_validate_horizons_catalog_execution():
    """Verify 25-case frozen benchmark catalog validation runs cleanly and reports metrics."""
    result = validate_horizons_catalog()
    assert result["total_cases"] == 25
    assert result["passed_cases"] == 25
    assert result["all_passed"] is True
    assert result["sun_rms_angular_error_deg"] < 0.05
    assert result["earth_rms_angular_error_deg"] < 0.05
