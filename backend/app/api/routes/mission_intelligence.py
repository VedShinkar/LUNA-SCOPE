"""HTTP orchestration for the existing decision engine, timeline and Copilot."""
from dataclasses import asdict
import logging
from threading import BoundedSemaphore

from fastapi import APIRouter, HTTPException

from app.ai_copilot import copilot
from app.mission.decision_engine import engine
from app.mission.decision_engine.adapter import CATALOG_TO_MISSION
from app.models.mission_intelligence import (
    AssessmentRequest, AssessmentResult, ComparisonRequest, ComparisonResult,
    CopilotRequest, CopilotResult, NamedScenario, ScenarioDifference, ScenarioResult, Thresholds, Weights,
)
from app.scientific_engines import mission_service
from app.scientific_engines.ephemeris.geometry import utc_datetime
from app.scientific_engines.ephemeris.kernels import KernelUnavailable
from app.scientific_engines.ephemeris.observer import ObserverUnavailable
from app.scientific_engines.illumination.service import load_terrain, provenance
from app.scientific_engines.mission_timeline import observation

router = APIRouter(prefix="/terrain/explorer/mission-intelligence", tags=["Mission Intelligence"])
workers = BoundedSemaphore(2)
logger = logging.getLogger(__name__)


def checked(call, request):
    if not workers.acquire(blocking=False):
        raise HTTPException(503, "Mission analysis workers are busy. Retry shortly.")
    try:
        return call(request)
    except (KernelUnavailable, ObserverUnavailable) as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("Mission analysis failed")
        raise HTTPException(503, "Mission analysis could not retrieve the required evidence.") from exc
    finally:
        workers.release()


def native_observer(request):
    return mission_service.observer_at(load_terrain(request.site_id), request.point.coordinates() if request.point else None)


def snapshot(request, point, profile):
    instant = utc_datetime(request.utc)
    terrain = load_terrain(request.site_id)
    observer = mission_service.observer_at(terrain, point)
    sun, earth = mission_service.collect(terrain, observer, instant, profile)
    source = provenance(terrain)
    return {"observer": asdict(observer), "sample": observation(instant, sun, earth, profile),
            "solar": sun, "earth": earth, "terrain": source["terrain"], "celestial": source["celestial"]}


def assess(request):
    observer = native_observer(request)
    point = observer.easting_m, observer.northing_m
    profile = request.effective_profile()
    window = request.window()
    result = engine.assess_site(
        CATALOG_TO_MISSION[request.site_id], *(window or (None, None)), request.step_seconds,
        engine.AssessmentWeights(**request.weights.model_dump()),
        engine.AssessmentThresholds(**request.thresholds.model_dump()),
        profile.minimum_antenna_elevation_deg, point=point, earth_criterion=profile.earth_requirement,
        match_endpoint=True,
    )
    notes = [
        "The existing engine re-normalizes scores across available criteria.",
        "Operational screening evaluates the configured window. It does not establish mission feasibility.",
        "Antenna elevation eligibility is applied to the operational window independently of the geometric Earth score.",
    ]
    if window is None:
        notes.append("Temporal fractions and operational windows require a UTC range.")
    timeline = None
    sample = None
    screen = "unavailable"
    try:
        if window:
            timeline = mission_service.timelines([(request.site_id, point)], *window, request.step_seconds, profile, False)[0]
            summary = timeline["summary"]
            duration = summary["duration_s"]
            if any(item["meets_minimum"] for item in summary["favourable_windows"]):
                screen = "met"
            elif duration["conditional"] or duration["unresolved"] or duration["invalid"]:
                screen = "unresolved"
            else:
                screen = "not_met"
        elif request.utc:
            sample = snapshot(request, point, profile)
    except (KernelUnavailable, ObserverUnavailable) as exc:
        notes.append(f"Operational evidence unavailable: {exc}")
    return AssessmentResult(
        request=request, observer=observer, effective_profile=profile, assessment=result,
        contributions={criterion.criterion: criterion.weighted_score for criterion in result.criteria},
        operational_screen=screen, timeline=timeline, snapshot=sample, limitations=notes,
    )


def compare(request):
    """Compose existing assessments without comparing unsupported scores."""
    settings = request.model_dump(exclude={"scenarios"})
    rows = []
    for scenario in request.scenarios:
        item = AssessmentRequest(**settings, **scenario.model_dump(exclude={"name"}))
        try:
            rows.append(ScenarioResult(name=scenario.name, result=assess(item)))
        except (KernelUnavailable, ObserverUnavailable, ValueError) as exc:
            rows.append(ScenarioResult(name=scenario.name, unavailable=str(exc)))

    explanations = ["All scenarios use the same UTC selection, nominal step, weights and thresholds.",
                    "Site-specific terrain is sampled at the selected native pixel. Equipment changes the timeline's antenna mask."]
    supported = all(row.result and row.result.timeline and not row.result.assessment.missing_criteria and
                    row.result.assessment.preliminary_score is not None and
                    row.result.operational_screen != "unavailable" and
                    all(not source.summary.get("duration_s", {}).get("unknown", 0) and
                        not source.summary.get("duration_s", {}).get("unresolved", 0)
                        for source in (row.result.assessment.illumination, row.result.assessment.communication) if source)
                    for row in rows)
    comparable_profiles = len({row.profile.earth_requirement for row in request.scenarios}) == 1
    groups = []
    if supported and comparable_profiles:
        previous = None
        for row in sorted(rows, key=lambda item: item.result.assessment.preliminary_score, reverse=True):
            score = row.result.assessment.preliminary_score
            if previous is None or score != previous:
                groups.append([])
            groups[-1].append(row.name)
            previous = score
        explanations.append("Ordering uses the existing preliminary scores. Equal scores share a group.")
    else:
        explanations.append("Ranking withheld because a complete, compatible set of classified criteria is unavailable.")
    baseline, *other_rows = rows
    original, *other_inputs = request.scenarios
    differences = []
    for row, item in zip(other_rows, other_inputs, strict=True):
        changes = []
        for label, previous, current in (
            ("Site", original.site_id, item.site_id),
            ("Projected point", original.point, item.point),
            ("Profile", original.profile.name, item.profile.name),
            ("Earth criterion", original.profile.earth_requirement, item.profile.earth_requirement),
            ("Solar requirement", original.profile.solar_required, item.profile.solar_required),
            ("Full-disc preference", original.profile.prefer_full_disc, item.profile.prefer_full_disc),
            ("Minimum window (s)", original.profile.minimum_window_s, item.profile.minimum_window_s),
            ("Antenna mask (degrees)", original.effective_profile().minimum_antenna_elevation_deg,
             item.effective_profile().minimum_antenna_elevation_deg),
        ):
            if previous != current:
                changes.append(f"{label} changed from {previous} to {current}.")
        delta = row.result.assessment.preliminary_score - baseline.result.assessment.preliminary_score if groups else None
        differences.append(ScenarioDifference(baseline=baseline.name, scenario=row.name, changes=changes, score_delta=delta))
    return ComparisonResult(scenarios=rows, ranked_groups=groups, explanations=explanations, differences=differences)


def answer(request):
    context = AssessmentRequest(**request.model_dump(exclude={"action"}))
    action = request.action
    if action == "compare_sites":
        scenarios = [NamedScenario(name=site, site_id=site, point=request.point if site == request.site_id else None,
                                   profile=request.profile, equipment=request.equipment) for site in CATALOG_TO_MISSION]
        options = context.model_dump(exclude={"site_id", "point", "profile", "equipment"})
        comparison = compare(ComparisonRequest(**options, scenarios=scenarios))
        assessments = {row.result.assessment.mission_site_id: row.result.assessment for row in comparison.scenarios if row.result}
        return CopilotResult(action=action, context=context, comparison=comparison,
                             response=asdict(copilot.explain_comparison(assessments)),
                             missing_inputs=[row.name for row in comparison.scenarios if row.unavailable])

    if action == "timeline" and request.window() is None:
        return CopilotResult(action=action, context=context, missing_inputs=["UTC start and end"])
    if action in ("assessment", "timeline") or (action in ("solar", "earth") and request.utc):
        result = assess(context)
        if action in ("solar", "earth"):
            return CopilotResult(action=action, context=context, observer=result.observer,
                                 response=result.snapshot, missing_inputs=[] if result.snapshot else ["point evidence"])
        return CopilotResult(action=action, context=context, observer=result.observer, assessment=result,
                             response=asdict(copilot.explain_assessment(result.assessment)),
                             missing_inputs=["operational evidence"] if action == "timeline" and not result.timeline else [])

    if action in ("solar", "earth") and request.window() is None:
        return CopilotResult(action=action, context=context, missing_inputs=["UTC instant or range"])
    observer = native_observer(context)
    point = observer.easting_m, observer.northing_m
    site = CATALOG_TO_MISSION[request.site_id]
    profile = request.effective_profile()
    if action == "terrain":
        result = copilot.terrain_query_response(site, point=point)
    elif action == "solar":
        result = copilot.illumination_query_response(site, *request.window(), request.step_seconds, point=point, include_end=True)
    else:
        result = copilot.communication_query_response(site, *request.window(), request.step_seconds,
                                                      profile.minimum_antenna_elevation_deg,
                                                      point=point, criterion=profile.earth_requirement)
    return CopilotResult(action=action, context=context, observer=observer, response=asdict(result),
                         missing_inputs=result.missing_inputs)


@router.get("/defaults")
def defaults():
    return {"weights": Weights(), "thresholds": Thresholds(), "site_ids": list(CATALOG_TO_MISSION),
            "equipment_controls": ["minimum_antenna_elevation_deg"]}


@router.post("/assessment", response_model=AssessmentResult)
def site_assessment(request: AssessmentRequest):
    return checked(assess, request)


@router.post("/compare", response_model=ComparisonResult)
def scenario_comparison(request: ComparisonRequest):
    return checked(compare, request)


@router.post("/copilot", response_model=CopilotResult)
def copilot_action(request: CopilotRequest):
    return checked(answer, request)
