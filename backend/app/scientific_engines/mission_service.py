"""Orchestrate the solar and Earth engines against the same terrain snapshot."""
from collections import deque
from functools import lru_cache

import numpy as np

from app.models.mission_timeline import MissionProfile
from app.scientific_engines.communication.service import physical_sample, provenance_for_earth, with_mask
from app.scientific_engines.ephemeris.geometry import MAX_SAMPLES, covered_et, utc_datetime
from app.scientific_engines.ephemeris.kernels import inventory
from app.scientific_engines.ephemeris.observer import ObserverUnavailable, UnsupportedObserver
from app.scientific_engines.illumination.service import epochs_with_end, load_terrain, provenance, sample
from app.scientific_engines.terrain.catalog import get_site_config
from app.scientific_engines.terrain.explorer import ROOT, _path, site_elevation_path
from .mission_timeline import Evidence, RULES, TRACKS, align, bracket_transitions, intervals, observation, summary, utc

REFINEMENT_BUDGET = 24
REFINEMENT_TARGET_S = 60


def fingerprint(site_id):
    config = get_site_config(site_id)
    dem = site_elevation_path(site_id)
    rms = _path(ROOT,"raw","elevation_uncertainty",config)
    try:
        stamp = dem.stat()
        uncertainty = rms.stat() if rms.is_file() else None
    except OSError as exc:
        raise ObserverUnavailable(f"Native LOLA terrain is unavailable for {site_id}.") from exc
    return (str(dem),stamp.st_mtime_ns,stamp.st_size,str(rms),
            (uncertainty.st_mtime_ns,uncertainty.st_size) if uncertainty else None)


def observer_at(terrain, point):
    row,col = terrain.point_cell(point)
    if not np.isfinite(terrain.dem[row,col]):
        raise UnsupportedObserver(f"The selected {terrain.reference.site_id} observation pixel has no valid native elevation.")
    return terrain.cell_observer(row,col)


def actionable_transition(left, right):
    return any(a != b and not {"unresolved","invalid"} & {a,b}
               for a,b in [(left["tracks"][key],right["tracks"][key]) for key in TRACKS] +
               [(left["required_earth"],right["required_earth"])])


def refine(schedule, read, budget):
    """Evaluate bounded midpoints only when a sampled condition changes."""
    added = []
    candidates = deque(zip(schedule,schedule[1:]))
    while candidates and len(added) < budget:
        start,end = candidates.popleft()
        if (end-start).total_seconds() <= REFINEMENT_TARGET_S or not actionable_transition(read(start),read(end)):
            continue
        middle = start+(end-start)/2
        read(middle)
        added.append(middle)
        candidates.extend(((start,middle),(middle,end)))
    return added


def collect(terrain, observer, time, profile):
    return sample(terrain,observer,time), with_mask(physical_sample(terrain,observer,time),
                                                     profile.minimum_antenna_elevation_deg,profile.earth_requirement)


@lru_cache(maxsize=8)
def _calculate(sites, start, end, step, profile_json, adaptive, stamps, ephemeris_version):
    profile = MissionProfile.model_validate_json(profile_json)
    nominal = epochs_with_end(start,end,step)
    covered_et(start)
    covered_et(end)
    budget = min(REFINEMENT_BUDGET,MAX_SAMPLES-len(nominal)) if adaptive else 0
    union = set(nominal)
    prepared = []
    for index,(site,point) in enumerate(sites):
        terrain = load_terrain(site)
        observer = observer_at(terrain,point)
        solar,earth = {},{}

        def read(time):
            if time not in solar:
                solar[time],earth[time] = collect(terrain,observer,time,profile)
            return observation(time,solar[time],earth[time],profile)

        for time in nominal:
            read(time)
        allotted = budget//(len(sites)-index)
        added = refine(nominal,read,allotted)
        new = set(added)-union
        union.update(new)
        budget -= len(new)
        solar_meta = provenance(terrain)
        earth_meta = provenance_for_earth(terrain,profile.minimum_antenna_elevation_deg,profile.earth_requirement)
        prepared.append((observer,solar,earth,solar_meta,earth_meta))

    schedule = sorted(union)
    results = []
    for (site,point),stamp,(observer,solar,earth,solar_meta,earth_meta) in zip(sites,stamps,prepared,strict=True):
        missing = union-solar.keys()
        if missing:
            terrain = load_terrain(site)
            if observer_at(terrain,point) != observer:
                raise ObserverUnavailable("The native observer changed during timeline analysis. Retry the calculation.")
            for time in missing:
                solar[time],earth[time] = collect(terrain,observer,time,profile)
        if fingerprint(site) != stamp:
            raise ObserverUnavailable("Terrain data changed during timeline analysis. Retry the calculation.")
        times,observations = align(Evidence(observer,stamp,list(solar.values())),Evidence(observer,stamp,list(earth.values())),
                                   schedule,profile)
        rows = intervals(times,observations,profile)
        transitions = bracket_transitions(times,observations)
        results.append({"site_id":site,"observer":observer,"start_utc":utc(start),"end_utc":utc(end),"step_seconds":step,
                        "profile":profile,"samples":observations,"intervals":rows,"transitions":transitions,
                        "summary":summary(rows,transitions,profile),"nominal_sample_count":len(nominal),
                        "refinement_sample_count":len(schedule)-len(nominal),"terrain":solar_meta["terrain"],
                        "solar_engine":{"method":solar_meta["method"],"flags":solar_meta["quality_flags"]},
                        "earth_engine":{"method":earth_meta["method"],"flags":earth_meta["quality_flags"]},
                        "celestial":solar_meta["celestial"],"classification_rules":RULES,
                        "quality_flags":["sampled_interval_estimates","finite_native_coverage","solar_centre_only",
                                         "demonstration_assumptions", "geometric_visibility_only"]})
    return results


def timelines(sites, start, end, step, profile, adaptive):
    if end <= start:
        raise ValueError("Analysis end must be after its start.")
    stamps = tuple(fingerprint(site) for site,_ in sites)
    kernels = tuple(item["sha256"] for item in inventory())
    return _calculate(tuple(sites),start,end,step,profile.model_dump_json(),adaptive,stamps,kernels)


def inspect(timeline, time):
    timestamp = utc(time)
    if time < utc_datetime(timeline["start_utc"]) or time > utc_datetime(timeline["end_utc"]):
        raise ValueError("Inspection time lies outside the analysis interval.")
    for index,row in enumerate(timeline["intervals"]):
        a,b = utc_datetime(row["start_utc"]),utc_datetime(row["end_utc"])
        if a <= time < b or timestamp == timeline["end_utc"] and time == b:
            return {"site_id":timeline["site_id"],"observer":timeline["observer"],"interval":row,
                    "start_sample":timeline["samples"][index],"end_sample":timeline["samples"][index+1],
                    "transition_brackets":[event for event in timeline["transitions"]
                        if utc_datetime(event["start_utc"]) < b and utc_datetime(event["end_utc"]) > a]}
