"""
LUNA-SCOPE Ephemeris and Celestial Mechanics Engine.

Provides:
- SPICE kernel management and topocentric observer geometry.
- Airless apparent Sun and Earth geometry (geometry.py).
- LOLA surface observers and ENU transformations (observer.py).
- Horizons–SPICE scientific validation subsystem (validation.py).
"""

from .kernels import _load, inventory, verified, KERNELS, BODY_FRAME, LOCK, KernelUnavailable
from .observer import Observer, resolve_observer, local_basis, azimuth_elevation
from .geometry import geometry_at, epochs, utc_datetime

from .geometric_state import (
    LunarSurfaceLocation,
    SpiceGeometricState,
    compute_spice_geometric_state,
)
from .horizons import (
    build_horizons_vector_url,
    build_horizons_observer_url,
    parse_horizons_vector_csv,
    parse_horizons_observer_response,
    capture_horizons_vector_pilot,
    HorizonsVectorCaptureResult,
    ParsedHorizonsVectorData,
)
from .comparison import (
    compare_geometric_vectors,
    GeometricVectorComparisonResult,
)
from .provenance import (
    VectorProvenanceRecord,
    build_vector_provenance_record,
    HorizonsQueryError,
    SOURCE_CLASSIFICATION_UNVERIFIED,
    SOURCE_CLASSIFICATION_SYNTHETIC,
    SOURCE_CLASSIFICATION_VERIFIED_PILOT,
    STATUS_WITHIN_PROVISIONAL_TOLERANCE,
    STATUS_EXCEEDS_PROVISIONAL_TOLERANCE,
    STATUS_NOT_ASSESSED,
)
from .validation import (
    validate_geometric_vectors,
    validate_horizons_catalog,
)

__all__ = [
    # Existing core
    "_load",
    "inventory",
    "verified",
    "KERNELS",
    "BODY_FRAME",
    "LOCK",
    "KernelUnavailable",
    "Observer",
    "resolve_observer",
    "local_basis",
    "azimuth_elevation",
    "geometry_at",
    "epochs",
    "utc_datetime",
    # Horizons-SPICE Validation
    "LunarSurfaceLocation",
    "SpiceGeometricState",
    "compute_spice_geometric_state",
    "build_horizons_vector_url",
    "build_horizons_observer_url",
    "parse_horizons_vector_csv",
    "parse_horizons_observer_response",
    "capture_horizons_vector_pilot",
    "HorizonsVectorCaptureResult",
    "ParsedHorizonsVectorData",
    "compare_geometric_vectors",
    "GeometricVectorComparisonResult",
    "VectorProvenanceRecord",
    "build_vector_provenance_record",
    "HorizonsQueryError",
    "SOURCE_CLASSIFICATION_UNVERIFIED",
    "SOURCE_CLASSIFICATION_SYNTHETIC",
    "SOURCE_CLASSIFICATION_VERIFIED_PILOT",
    "STATUS_WITHIN_PROVISIONAL_TOLERANCE",
    "STATUS_EXCEEDS_PROVISIONAL_TOLERANCE",
    "STATUS_NOT_ASSESSED",
    "validate_geometric_vectors",
    "validate_horizons_catalog",
]
