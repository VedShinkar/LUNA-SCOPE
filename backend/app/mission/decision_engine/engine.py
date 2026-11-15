"""Mission Intelligence Decision Engine.

Provides site assessment, feasibility scoring, and multi-site comparison
using validated measurements from the scientific engines via the adapter.

Design principles
-----------------
- Assessment is explicitly labelled as PRELIMINARY. No claim of mission
  readiness is made based on geometric approximations alone.
- Scoring weights and thresholds are externally configurable; none are
  hidden in this module.
- Where a required input has INSUFFICIENT_DATA status, scoring for that
  criterion is withheld and the overall assessment reflects the data gap.
- SYNTHETIC_EXAMPLE values never enter a real-data assessment.
- Earth visibility is never equated with confirmed communication availability:
  it is treated as geometric line-of-sight only.

Data-status propagation
-----------------------
A site assessment carries the minimum (least-certain) data status across
its constituent measurements. If any input is INSUFFICIENT_DATA, the
assessment records which criteria are unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.mission.decision_engine.adapter import (
    DATA_STATUS_INSUFFICIENT,
    DATA_STATUS_PROVISIONAL,
    DATA_STATUS_SYNTHETIC,
    DATA_STATUS_UNVERIFIED,
    DATA_STATUS_VERIFIED,
    TerrainMeasurement,
    TemporalMeasurement,
    catalog_id,
    get_communication,
    get_illumination,
    get_terrain,
)

DataStatus = Literal[
    "VERIFIED_SOURCE",
    "PROVISIONAL",
    "UNVERIFIED_SOURCE",
    "SYNTHETIC_EXAMPLE",
    "INSUFFICIENT_DATA",
]

# Status precedence (lower index = higher certainty). The assessment carries
# the minimum certainty across all its inputs.
_STATUS_RANK: list[str] = [
    DATA_STATUS_VERIFIED,
    DATA_STATUS_PROVISIONAL,
    DATA_STATUS_UNVERIFIED,
    DATA_STATUS_SYNTHETIC,
    DATA_STATUS_INSUFFICIENT,
]


def _aggregate_status(*statuses: str) -> str:
    """Return the least-certain status across the supplied values."""
    max_rank = max(
        (_STATUS_RANK.index(s) if s in _STATUS_RANK else len(_STATUS_RANK) - 1)
        for s in statuses
    )
    return _STATUS_RANK[min(max_rank, len(_STATUS_RANK) - 1)]


# ---------------------------------------------------------------------------
# Scoring parameters (preliminary, configurable)
# ---------------------------------------------------------------------------

@dataclass
class AssessmentWeights:
    """Relative weights for each criterion in the preliminary score [0, 1]."""
    terrain_slope: float = 0.30
    terrain_roughness: float = 0.20
    illumination_fraction: float = 0.30
    communication_fraction: float = 0.20

    def __post_init__(self) -> None:
        total = (
            self.terrain_slope
            + self.terrain_roughness
            + self.illumination_fraction
            + self.communication_fraction
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"AssessmentWeights must sum to 1.0; got {total:.6f}."
            )


@dataclass
class AssessmentThresholds:
    """Thresholds used to map raw measurements to [0, 1] criterion scores."""
    # Slope: 0 deg → score 1.0; threshold_max_slope_deg → score 0.0 (linear)
    max_slope_deg: float = 15.0
    # Roughness (15 m scale): 0 m → 1.0; max_roughness_m → 0.0 (linear)
    max_roughness_m: float = 0.5
    # Illumination: fraction of time illuminated; 1.0 → 1.0 (direct mapping)
    # Communication: fraction of classified time visible; 1.0 → 1.0


DEFAULT_WEIGHTS = AssessmentWeights()
DEFAULT_THRESHOLDS = AssessmentThresholds()


def _slope_score(slope_deg: float | None, thresholds: AssessmentThresholds) -> float | None:
    if slope_deg is None:
        return None
    return max(0.0, 1.0 - slope_deg / thresholds.max_slope_deg)


def _roughness_score(roughness_m: float | None, thresholds: AssessmentThresholds) -> float | None:
    if roughness_m is None:
        return None
    return max(0.0, 1.0 - roughness_m / thresholds.max_roughness_m)


def _illumination_score(summary: dict[str, Any]) -> float | None:
    fraction = summary.get("fraction_known_time_clear")
    if fraction is None:
        return None
    return float(fraction)


def _communication_score(summary: dict[str, Any]) -> float | None:
    fraction = summary.get("fraction_classified_time_visible")
    if fraction is None:
        return None
    return float(fraction)


# ---------------------------------------------------------------------------
# Assessment result types
# ---------------------------------------------------------------------------

@dataclass
class CriterionResult:
    """Score and status for one assessment criterion."""
    criterion: str
    score: float | None          # [0.0, 1.0]; None = INSUFFICIENT_DATA
    weight: float
    data_status: str
    value: Any                   # Raw measurement value used to compute score
    units: str | None
    notes: list[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float | None:
        if self.score is None:
            return None
        return self.score * self.weight


@dataclass
class SiteAssessment:
    """Preliminary mission assessment for a single landing site."""

    mission_site_id: str
    catalog_site_id: str
    assessment_label: str = "PRELIMINARY"   # Always preliminary; never drop this label.
    overall_data_status: str = DATA_STATUS_INSUFFICIENT

    terrain: TerrainMeasurement | None = None
    illumination: TemporalMeasurement | None = None
    communication: TemporalMeasurement | None = None

    criteria: list[CriterionResult] = field(default_factory=list)

    # Weighted sum across criteria with available scores; None if no criterion
    # has data.
    preliminary_score: float | None = None

    missing_criteria: list[str] = field(default_factory=list)
    quality_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Assessment builder
# ---------------------------------------------------------------------------

def assess_site(
    mission_site_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    step_seconds: int = 3600,
    weights: AssessmentWeights = DEFAULT_WEIGHTS,
    thresholds: AssessmentThresholds = DEFAULT_THRESHOLDS,
    antenna_min_elevation_deg: float = 0.0,
    *,
    point: tuple[float, float] | None = None,
    earth_criterion: str = "centre",
    match_endpoint: bool = False,
) -> SiteAssessment:
    """Build a preliminary site assessment from real scientific engine outputs.

    Parameters
    ----------
    mission_site_id:
        One of SHACKLETON_RIM, DE_GERLACHE_RIM, MALAPERT_MASSIF.
    start, end:
        UTC datetimes for temporal analyses (illumination, communication).
        If None, temporal criteria are skipped (INSUFFICIENT_DATA).
    step_seconds:
        Temporal sampling interval.
    weights:
        Criterion weights; must sum to 1.0.
    thresholds:
        Score mapping thresholds.
    antenna_min_elevation_deg:
        Minimum Earth elevation for communication eligibility.

    Returns
    -------
    SiteAssessment
        Always returned; never raises for data-availability reasons.
    """
    site_id = catalog_id(mission_site_id)
    criteria: list[CriterionResult] = []
    missing: list[str] = []
    notes: list[str] = ["Scores are PRELIMINARY; based on geometric approximations."]

    # --- Terrain ---
    terrain = get_terrain(mission_site_id) if point is None else get_terrain(mission_site_id, point)

    slope_score = _slope_score(terrain.slope_deg, thresholds)
    criteria.append(CriterionResult(
        criterion="terrain_slope",
        score=slope_score,
        weight=weights.terrain_slope,
        data_status=terrain.data_status,
        value=terrain.slope_deg,
        units="deg",
        notes=([] if terrain.data_status != DATA_STATUS_INSUFFICIENT
               else [terrain.error or "Terrain data unavailable."]),
    ))
    if slope_score is None:
        missing.append("terrain_slope")

    roughness_score = _roughness_score(terrain.roughness_15m_m, thresholds)
    criteria.append(CriterionResult(
        criterion="terrain_roughness_15m",
        score=roughness_score,
        weight=weights.terrain_roughness,
        data_status=terrain.data_status,
        value=terrain.roughness_15m_m,
        units="m",
        notes=([] if terrain.data_status != DATA_STATUS_INSUFFICIENT
               else [terrain.error or "Terrain data unavailable."]),
    ))
    if roughness_score is None:
        missing.append("terrain_roughness_15m")

    # --- Illumination ---
    illum: TemporalMeasurement | None = None
    if start is not None and end is not None:
        solar_options = {"point": point} if point is not None else {}
        if match_endpoint:
            solar_options["include_end"] = True
        illum = get_illumination(mission_site_id, start, end, step_seconds, **solar_options)
        illum_score = _illumination_score(illum.summary)
        illum_notes = []
        if illum.data_status == DATA_STATUS_PROVISIONAL:
            illum_notes.append("Solar illumination: geometric solar-centre-only. Not a measured power budget.")
        elif illum.data_status == DATA_STATUS_INSUFFICIENT:
            illum_notes.append(illum.error or "Illumination data unavailable.")
        criteria.append(CriterionResult(
            criterion="illumination_fraction",
            score=illum_score,
            weight=weights.illumination_fraction,
            data_status=illum.data_status,
            value=illum.summary.get("fraction_known_time_clear"),
            units="fraction [0, 1]",
            notes=illum_notes,
        ))
        if illum_score is None:
            missing.append("illumination_fraction")
    else:
        criteria.append(CriterionResult(
            criterion="illumination_fraction",
            score=None,
            weight=weights.illumination_fraction,
            data_status=DATA_STATUS_INSUFFICIENT,
            value=None,
            units="fraction [0, 1]",
            notes=["No time window supplied; illumination analysis skipped."],
        ))
        missing.append("illumination_fraction")

    # --- Communication ---
    comm: TemporalMeasurement | None = None
    if start is not None and end is not None:
        earth_options = {"point": point} if point is not None else {}
        if earth_criterion != "centre":
            earth_options["criterion"] = earth_criterion
        comm = get_communication(mission_site_id, start, end, step_seconds,
                                 antenna_min_elevation_deg, **earth_options)
        comm_score = _communication_score(comm.summary)
        comm_notes = []
        if comm.data_status == DATA_STATUS_PROVISIONAL:
            comm_notes.append(
                "Earth visibility: geometric line-of-sight only. "
                "Does not confirm link budget or DSN coverage."
            )
        elif comm.data_status == DATA_STATUS_INSUFFICIENT:
            comm_notes.append(comm.error or "Communication data unavailable.")
        criteria.append(CriterionResult(
            criterion="communication_visibility_fraction",
            score=comm_score,
            weight=weights.communication_fraction,
            data_status=comm.data_status,
            value=comm.summary.get("fraction_classified_time_visible"),
            units="fraction [0, 1]",
            notes=comm_notes,
        ))
        if comm_score is None:
            missing.append("communication_visibility_fraction")
    else:
        criteria.append(CriterionResult(
            criterion="communication_visibility_fraction",
            score=None,
            weight=weights.communication_fraction,
            data_status=DATA_STATUS_INSUFFICIENT,
            value=None,
            units="fraction [0, 1]",
            notes=["No time window supplied; communication analysis skipped."],
        ))
        missing.append("communication_visibility_fraction")

    # --- Aggregate score ---
    weighted_contributions = [
        c.weighted_score for c in criteria if c.weighted_score is not None
    ]
    if weighted_contributions:
        # Re-normalise across available weights only.
        available_weight = sum(
            c.weight for c in criteria if c.score is not None
        )
        preliminary = sum(weighted_contributions) / available_weight if available_weight else None
    else:
        preliminary = None

    overall_status = _aggregate_status(*[c.data_status for c in criteria])

    return SiteAssessment(
        mission_site_id=mission_site_id,
        catalog_site_id=site_id,
        assessment_label="PRELIMINARY",
        overall_data_status=overall_status,
        terrain=terrain,
        illumination=illum,
        communication=comm,
        criteria=criteria,
        preliminary_score=preliminary,
        missing_criteria=missing,
        quality_notes=notes,
    )


def compare_sites(
    mission_site_ids: list[str],
    start: datetime | None = None,
    end: datetime | None = None,
    step_seconds: int = 3600,
    weights: AssessmentWeights = DEFAULT_WEIGHTS,
    thresholds: AssessmentThresholds = DEFAULT_THRESHOLDS,
    antenna_min_elevation_deg: float = 0.0,
) -> dict[str, SiteAssessment]:
    """Assess multiple sites using the same real-data pipeline.

    Returns a dict keyed by mission site ID; order matches the input list.
    """
    return {
        sid: assess_site(
            sid, start, end, step_seconds, weights, thresholds, antenna_min_elevation_deg
        )
        for sid in mission_site_ids
    }
