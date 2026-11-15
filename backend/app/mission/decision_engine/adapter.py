"""Scientific data adapter for Mission Intelligence.

Maps mission-domain site identifiers to terrain catalog IDs and retrieves
validated measurements from the existing scientific engines.

Data-status classifications
---------------------------
VERIFIED_SOURCE     – Retrieved from a named scientific engine with traceable
                      provenance (source file, SHA-256, frame tag).
PROVISIONAL         – Engine produced data but its quality flags indicate
                      known limitations (e.g. sampled-interval estimates,
                      solar-centre-only, geometric-visibility-only).
INSUFFICIENT_DATA   – The required engine raised ObserverUnavailable,
                      KernelUnavailable, or an equivalent; no measurement
                      was produced.

SYNTHETIC_EXAMPLE and UNVERIFIED_SOURCE are reserved for callers that
introduce those data classes; this adapter never produces them.

No measurement is fabricated. If a scientific engine is unavailable,
INSUFFICIENT_DATA is returned with the exception message recorded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.scientific_engines.communication.service import observer_analysis as comm_analysis
from app.scientific_engines.ephemeris.geometry import InvalidEpoch, epochs
from app.scientific_engines.ephemeris.kernels import KernelUnavailable
from app.scientific_engines.ephemeris.observer import ObserverUnavailable, UnsupportedObserver
from app.scientific_engines.illumination.service import epochs_with_end, observer_analysis
from app.scientific_engines.terrain.catalog import UnknownSiteError, get_site_config
from app.scientific_engines.terrain.service import TerrainService

# ---------------------------------------------------------------------------
# Site identifier registry
# ---------------------------------------------------------------------------

SITE_MAP: dict[str, str] = {
    "SHACKLETON_RIM": "Site04",
    "DE_GERLACHE_RIM": "Site11",
    "MALAPERT_MASSIF": "Site23",
}

# Reverse lookup (catalog ID → mission ID), useful for display.
CATALOG_TO_MISSION: dict[str, str] = {v: k for k, v in SITE_MAP.items()}

DATA_STATUS_VERIFIED = "VERIFIED_SOURCE"
DATA_STATUS_PROVISIONAL = "PROVISIONAL"
DATA_STATUS_INSUFFICIENT = "INSUFFICIENT_DATA"
DATA_STATUS_SYNTHETIC = "SYNTHETIC_EXAMPLE"
DATA_STATUS_UNVERIFIED = "UNVERIFIED_SOURCE"

# Quality flags produced by the illumination / communication engines that
# indicate the result is a geometric approximation, not a confirmed measurement.
_PROVISIONAL_FLAGS = frozenset({
    "sampled_interval_estimates",
    "solar_centre_only",
    "geometric_visibility_only",
    "earth_occultation_not_modelled",
    "finite_native_coverage",
    "finite_terrain_extent",
    "demonstration_assumptions",
})


def catalog_id(mission_site_id: str) -> str:
    """Convert a mission-domain site identifier to its terrain catalog ID.

    Raises
    ------
    UnknownSiteError
        If the mission site ID is not registered.
    """
    result = SITE_MAP.get(mission_site_id)
    if result is None:
        registered = ", ".join(SITE_MAP)
        raise UnknownSiteError(
            f"Unknown mission site '{mission_site_id}'. "
            f"Registered identifiers: {registered}."
        )
    return result


# ---------------------------------------------------------------------------
# Terrain data retrieval
# ---------------------------------------------------------------------------

@dataclass
class TerrainMeasurement:
    """Terrain attributes at the raster centre of a site, with provenance."""

    mission_site_id: str
    catalog_site_id: str
    data_status: str
    elevation_m: float | None
    slope_deg: float | None
    roughness_15m_m: float | None
    roughness_35m_m: float | None
    roughness_75m_m: float | None
    hazard: dict[str, Any] = field(default_factory=dict)
    uncertainty: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def get_terrain(mission_site_id: str, point: tuple[float, float] | None = None) -> TerrainMeasurement:
    """Retrieve terrain metrics at the raster centre of a site.

    Uses TerrainService.query_point at the raster midpoint
    (easting, northing derived from the raster bounds centre).

    Returns a TerrainMeasurement with INSUFFICIENT_DATA status if the
    terrain data files or the raster are unavailable.
    """
    site_id = catalog_id(mission_site_id)

    base = TerrainMeasurement(
        mission_site_id=mission_site_id,
        catalog_site_id=site_id,
        data_status=DATA_STATUS_INSUFFICIENT,
        elevation_m=None,
        slope_deg=None,
        roughness_15m_m=None,
        roughness_35m_m=None,
        roughness_75m_m=None,
    )

    try:
        service = TerrainService.get_instance(site_id)
        # Use the raster centre as the query point.
        meta = service._meta  # type: ignore[attr-defined]
        if meta is None:
            # Trigger load.
            service._ensure_loaded()
            meta = service._meta
        coordinates = point if point is not None else (
            (meta.bounds[0] + meta.bounds[2]) / 2.0,
            (meta.bounds[1] + meta.bounds[3]) / 2.0,
        )
        result = service.query_point(*coordinates)
    except (FileNotFoundError, ObserverUnavailable, UnsupportedObserver, ValueError) as exc:
        base.error = str(exc)
        return base
    except Exception as exc:
        base.error = f"Unexpected error retrieving terrain: {exc}"
        return base

    if not result.get("is_valid"):
        base.error = result.get("error", "Centre pixel is not valid.")
        return base

    hazard = result.get("hazard_classification", {})
    uncertainty = result.get("uncertainty_and_observation", {})
    roughness = result.get("roughness", {})
    provenance = result.get("provenance", {})

    return TerrainMeasurement(
        mission_site_id=mission_site_id,
        catalog_site_id=site_id,
        data_status=DATA_STATUS_VERIFIED,
        elevation_m=result.get("elevation_m"),
        slope_deg=result.get("slope_deg"),
        roughness_15m_m=roughness.get("roughness_15m_m"),
        roughness_35m_m=roughness.get("roughness_35m_m"),
        roughness_75m_m=roughness.get("roughness_75m_m"),
        hazard=hazard,
        uncertainty=uncertainty,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Illumination and communication data retrieval
# ---------------------------------------------------------------------------

@dataclass
class TemporalMeasurement:
    """Illumination or Earth-communication summary over a time window."""

    mission_site_id: str
    catalog_site_id: str
    data_status: str
    start_utc: str | None
    end_utc: str | None
    summary: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    quality_flags: list[str] = field(default_factory=list)
    error: str | None = None


def _has_provisional_flags(flags: list[str]) -> bool:
    return bool(frozenset(flags) & _PROVISIONAL_FLAGS)


def get_illumination(
    mission_site_id: str,
    start: datetime,
    end: datetime,
    step_seconds: int = 3600,
    point: tuple[float, float] | None = None,
    include_end: bool = False,
) -> TemporalMeasurement:
    """Retrieve solar illumination summary over a time window.

    Parameters
    ----------
    mission_site_id:
        Mission-domain site identifier.
    start, end:
        UTC datetimes (timezone-aware).
    step_seconds:
        Sampling interval.

    Returns a TemporalMeasurement; status is PROVISIONAL because the
    illumination engine uses solar-centre-only geometric ray casting.
    Status is INSUFFICIENT_DATA if real LOLA data or SPICE kernels are absent.
    """
    site_id = catalog_id(mission_site_id)
    _start_utc = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    _end_utc = end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    base = TemporalMeasurement(
        mission_site_id=mission_site_id,
        catalog_site_id=site_id,
        data_status=DATA_STATUS_INSUFFICIENT,
        start_utc=_start_utc,
        end_utc=_end_utc,
    )

    try:
        schedule = epochs_with_end if include_end else epochs
        times = schedule(start.astimezone(timezone.utc), end.astimezone(timezone.utc), step_seconds)
        result = observer_analysis(site_id, point, times)
    except (ObserverUnavailable, KernelUnavailable) as exc:
        base.error = str(exc)
        return base
    except (InvalidEpoch, ValueError) as exc:
        base.error = str(exc)
        return base
    except Exception as exc:
        base.error = f"Unexpected error retrieving illumination: {exc}"
        return base

    flags: list[str] = result.get("quality_flags", [])
    status = DATA_STATUS_PROVISIONAL if _has_provisional_flags(flags) else DATA_STATUS_VERIFIED

    return TemporalMeasurement(
        mission_site_id=mission_site_id,
        catalog_site_id=site_id,
        data_status=status,
        start_utc=_start_utc,
        end_utc=_end_utc,
        summary=result.get("summary", {}),
        provenance={
            "terrain": result.get("terrain"),
            "celestial": result.get("celestial"),
            "method": result.get("method"),
            "observer": result.get("observer"),
        },
        quality_flags=flags,
    )


def get_communication(
    mission_site_id: str,
    start: datetime,
    end: datetime,
    step_seconds: int = 3600,
    antenna_min_elevation_deg: float = 0.0,
    criterion: str = "centre",
    point: tuple[float, float] | None = None,
) -> TemporalMeasurement:
    """Retrieve Earth communication visibility summary over a time window.

    Returns PROVISIONAL (geometric visibility only, no link budget).
    Returns INSUFFICIENT_DATA if real LOLA data or SPICE kernels are absent.
    """
    site_id = catalog_id(mission_site_id)
    _start_utc = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    _end_utc = end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    base = TemporalMeasurement(
        mission_site_id=mission_site_id,
        catalog_site_id=site_id,
        data_status=DATA_STATUS_INSUFFICIENT,
        start_utc=_start_utc,
        end_utc=_end_utc,
    )

    try:
        times = epochs_with_end(
            start.astimezone(timezone.utc),
            end.astimezone(timezone.utc),
            step_seconds,
        )
        result = comm_analysis(
            site_id, point, times,
            antenna_min_elevation_deg, criterion,
        )
    except (ObserverUnavailable, KernelUnavailable) as exc:
        base.error = str(exc)
        return base
    except (InvalidEpoch, ValueError) as exc:
        base.error = str(exc)
        return base
    except Exception as exc:
        base.error = f"Unexpected error retrieving communication data: {exc}"
        return base

    flags: list[str] = result.get("quality_flags", [])
    status = DATA_STATUS_PROVISIONAL if _has_provisional_flags(flags) else DATA_STATUS_VERIFIED

    return TemporalMeasurement(
        mission_site_id=mission_site_id,
        catalog_site_id=site_id,
        data_status=status,
        start_utc=_start_utc,
        end_utc=_end_utc,
        summary=result.get("summary", {}),
        provenance={
            "terrain": result.get("terrain"),
            "celestial": result.get("celestial"),
            "method": result.get("method"),
            "antenna_min_elevation_deg": antenna_min_elevation_deg,
            "criterion": criterion,
            "observer": result.get("observer"),
        },
        quality_flags=flags,
    )
