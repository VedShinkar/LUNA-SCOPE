"""AI Mission Copilot — structured routing for natural-language mission queries.

The copilot routes queries to the real-data Mission Intelligence pipeline.
It does not independently calculate scientific measurements; all numbers
come from the existing scientific engines via the decision engine.

Responses include provenance, data quality, limitations, and missing inputs.
No measurement is invented or silently substituted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.mission.decision_engine.adapter import (
    DATA_STATUS_INSUFFICIENT,
    SITE_MAP,
    catalog_id,
    get_communication,
    get_illumination,
    get_terrain,
)
from app.mission.decision_engine.engine import (
    AssessmentThresholds,
    AssessmentWeights,
    SiteAssessment,
    assess_site,
    compare_sites,
)


@dataclass
class CopilotResponse:
    """Structured copilot response with provenance and data-quality metadata."""

    query_type: str
    mission_site_ids: list[str]
    assessments: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    data_statuses: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    copilot_note: str = (
        "All measurements are retrieved from validated scientific engines. "
        "The copilot does not independently calculate terrain, illumination, "
        "or communication data."
    )


def _assessment_dict(assessment: SiteAssessment) -> dict[str, Any]:
    """Serialise a SiteAssessment to a plain dict."""
    return {
        "mission_site_id": assessment.mission_site_id,
        "catalog_site_id": assessment.catalog_site_id,
        "assessment_label": assessment.assessment_label,
        "overall_data_status": assessment.overall_data_status,
        "preliminary_score": assessment.preliminary_score,
        "criteria": [
            {
                "criterion": c.criterion,
                "score": c.score,
                "weight": c.weight,
                "data_status": c.data_status,
                "value": c.value,
                "units": c.units,
                "notes": c.notes,
            }
            for c in assessment.criteria
        ],
        "missing_criteria": assessment.missing_criteria,
        "quality_notes": assessment.quality_notes,
    }


def site_assessment_response(
    mission_site_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    step_seconds: int = 3600,
    weights: AssessmentWeights = AssessmentWeights(),
    thresholds: AssessmentThresholds = AssessmentThresholds(),
    antenna_min_elevation_deg: float = 0.0,
) -> CopilotResponse:
    """Run the real-data Mission Intelligence pipeline for one site.

    The same assess_site() call used by the decision engine is invoked;
    no separate calculation path exists in the copilot.
    """
    assessment = assess_site(
        mission_site_id, start, end, step_seconds,
        weights, thresholds, antenna_min_elevation_deg,
    )
    return explain_assessment(assessment)


def explain_assessment(assessment: SiteAssessment) -> CopilotResponse:
    mission_site_id = assessment.mission_site_id
    limitations = list(assessment.quality_notes)
    if assessment.terrain and assessment.terrain.data_status == DATA_STATUS_INSUFFICIENT:
        limitations.append(
            f"Real terrain data for {mission_site_id} is unavailable on this deployment."
        )

    return CopilotResponse(
        query_type="site_assessment",
        mission_site_ids=[mission_site_id],
        assessments={mission_site_id: _assessment_dict(assessment)},
        evidence={
            "terrain": (
                asdict(assessment.terrain)
                if assessment.terrain is not None else None
            ),
            "illumination": (
                asdict(assessment.illumination)
                if assessment.illumination is not None else None
            ),
            "communication": (
                asdict(assessment.communication)
                if assessment.communication is not None else None
            ),
        },
        data_statuses={mission_site_id: assessment.overall_data_status},
        limitations=limitations,
        missing_inputs=assessment.missing_criteria,
    )


def multi_site_comparison_response(
    mission_site_ids: list[str],
    start: datetime | None = None,
    end: datetime | None = None,
    step_seconds: int = 3600,
    weights: AssessmentWeights = AssessmentWeights(),
    thresholds: AssessmentThresholds = AssessmentThresholds(),
    antenna_min_elevation_deg: float = 0.0,
) -> CopilotResponse:
    """Compare multiple sites using the same real-data pipeline.

    Every site uses the same weights, thresholds, and time window for
    a fair comparison. No separate calculation path exists for the copilot.
    """
    assessments = compare_sites(
        mission_site_ids, start, end, step_seconds,
        weights, thresholds, antenna_min_elevation_deg,
    )
    return explain_comparison(assessments)


def explain_comparison(assessments: dict[str, SiteAssessment]) -> CopilotResponse:
    all_missing: list[str] = []
    all_limitations: list[str] = []
    for sid, a in assessments.items():
        for note in a.quality_notes:
            if note not in all_limitations:
                all_limitations.append(note)
        for m in a.missing_criteria:
            entry = f"{sid}: {m}"
            if entry not in all_missing:
                all_missing.append(entry)

    return CopilotResponse(
        query_type="multi_site_comparison",
        mission_site_ids=list(assessments),
        assessments={sid: _assessment_dict(a) for sid, a in assessments.items()},
        evidence={
            sid: {
                "terrain": asdict(a.terrain) if a.terrain is not None else None,
                "illumination": asdict(a.illumination) if a.illumination is not None else None,
                "communication": asdict(a.communication) if a.communication is not None else None,
            }
            for sid, a in assessments.items()
        },
        data_statuses={sid: a.overall_data_status for sid, a in assessments.items()},
        limitations=all_limitations,
        missing_inputs=all_missing,
    )


def terrain_query_response(mission_site_id: str, *, point=None) -> CopilotResponse:
    """Retrieve terrain evidence for one site."""
    terrain = get_terrain(mission_site_id) if point is None else get_terrain(mission_site_id, point)
    limitations: list[str] = []
    if terrain.data_status == DATA_STATUS_INSUFFICIENT:
        limitations.append(terrain.error or "Terrain data unavailable.")

    return CopilotResponse(
        query_type="terrain_query",
        mission_site_ids=[mission_site_id],
        evidence={"terrain": asdict(terrain)},
        data_statuses={mission_site_id: terrain.data_status},
        limitations=limitations,
    )


def illumination_query_response(
    mission_site_id: str,
    start: datetime,
    end: datetime,
    step_seconds: int = 3600,
    *,
    point=None,
    include_end=False,
) -> CopilotResponse:
    """Retrieve illumination evidence for one site."""
    options = {} if point is None else {"point": point}
    if include_end:
        options["include_end"] = True
    illum = get_illumination(mission_site_id, start, end, step_seconds, **options)
    limitations: list[str] = []
    if illum.data_status == DATA_STATUS_INSUFFICIENT:
        limitations.append(illum.error or "Illumination data unavailable.")
    elif illum.data_status == "PROVISIONAL":
        limitations.append(
            "Solar illumination values are geometric solar-centre-only estimates. "
            "They are not a measured power budget."
        )

    return CopilotResponse(
        query_type="illumination_query",
        mission_site_ids=[mission_site_id],
        evidence={"illumination": asdict(illum)},
        data_statuses={mission_site_id: illum.data_status},
        limitations=limitations,
        missing_inputs=["classified illumination duration"] if illum.summary.get("fraction_known_time_clear") is None else [],
    )


def communication_query_response(
    mission_site_id: str,
    start: datetime,
    end: datetime,
    step_seconds: int = 3600,
    antenna_min_elevation_deg: float = 0.0,
    *,
    point=None,
    criterion="centre",
) -> CopilotResponse:
    """Retrieve Earth communication visibility evidence for one site.

    Explicitly labelled as geometric line-of-sight; not a link budget.
    """
    options = {} if point is None else {"point": point}
    if criterion != "centre":
        options["criterion"] = criterion
    comm = get_communication(mission_site_id, start, end, step_seconds, antenna_min_elevation_deg, **options)
    limitations: list[str] = []
    if comm.data_status == DATA_STATUS_INSUFFICIENT:
        limitations.append(comm.error or "Communication data unavailable.")
    elif comm.data_status == "PROVISIONAL":
        limitations.append(
            "Earth visibility is geometric line-of-sight only. "
            "It does not confirm DSN link availability, signal margin, "
            "or confirmed communication availability."
        )

    return CopilotResponse(
        query_type="communication_query",
        mission_site_ids=[mission_site_id],
        evidence={"communication": asdict(comm)},
        data_statuses={mission_site_id: comm.data_status},
        limitations=limitations,
        missing_inputs=["classified Earth visibility duration"] if comm.summary.get("fraction_classified_time_visible") is None else [],
    )
