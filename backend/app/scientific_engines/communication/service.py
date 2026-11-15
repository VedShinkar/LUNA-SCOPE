"""Bounded observer, time-series, and native-window Earth visibility."""
from dataclasses import asdict

import numpy as np

from app.scientific_engines.ephemeris.geometry import MAX_SAMPLES, covered_et, geometry_at
from app.scientific_engines.ephemeris.observer import UnsupportedObserver
from app.scientific_engines.illumination.service import load_terrain, native_region, provenance, summarize
from .visibility import RIM_RAYS, evaluate

MAX_SIDE = 12
REFINEMENT_BUDGET = 24
REFINEMENT_TARGET_S = 60
CRITERIA = ("centre", "any_disc", "full_disc", "centre_with_mask")
DISC_STATES = ("fully_obscured", "partially_visible", "fully_visible", "unresolved")
CENTRE_STATES = ("visible", "obstructed", "unresolved")


def utc(time):
    return time.isoformat().replace("+00:00", "Z")


def physical_sample(terrain, observer, time):
    key = ("earth", observer.source_pixel_row, observer.source_pixel_column, time)
    with terrain.lock:
        cached = terrain.samples.get(key)
        if cached is not None:
            terrain.samples.move_to_end(key)
            return cached
    epoch = geometry_at(observer, time)
    value = {"utc": epoch["utc"], **evaluate(terrain, observer, epoch["earth"])}
    with terrain.lock:
        terrain.samples[key] = value
        if len(terrain.samples) > 2048:
            terrain.samples.popitem(last=False)
    return value


def criterion_state(sample, criterion):
    if criterion == "centre":
        return sample["centre_state"]
    if criterion == "centre_with_mask":
        return sample["centre_state"] if sample["antenna_eligible"] else "obstructed"
    state = sample["disc_state"]
    if state == "fully_visible" or (criterion == "any_disc" and state == "partially_visible"):
        return "visible"
    if state == "fully_obscured" or (criterion == "full_disc" and state == "partially_visible"):
        return "obstructed"
    # A visible or blocked witness is sufficient for some criteria even with
    # the complete disc still unresolved.
    witnesses = sample["disc_probe_counts"]
    if criterion == "any_disc" and witnesses["visible"]:
        return "visible"
    if criterion == "full_disc" and witnesses["obstructed"]:
        return "obstructed"
    return "unresolved"


def with_mask(sample, mask, criterion):
    result = {**sample, "antenna_eligible": sample["earth_elevation_deg"] >= mask}
    return {**result, "criterion_state": criterion_state(result, criterion)}


def refine(times, samples, calculate):
    """Bisect observed opposite-state brackets without assuming monotonic visibility."""
    budget = min(REFINEMENT_BUDGET, MAX_SAMPLES-len(times))
    known = lambda item: item["criterion_state"] != "unresolved"
    observations = dict(zip(times, samples, strict=True))
    for start, end in zip(times, times[1:]):
        left, right = observations[start], observations[end]
        while (budget and (end-start).total_seconds() > REFINEMENT_TARGET_S and
               known(left) and known(right) and left["criterion_state"] != right["criterion_state"]):
            middle = start+(end-start)/2
            sample = calculate(middle)
            observations[middle] = sample
            budget -= 1
            if not known(sample):
                break
            if sample["criterion_state"] == left["criterion_state"]:
                start, left = middle, sample
            else:
                end, right = middle, sample
    ordered = sorted(observations)
    return ordered, [observations[time] for time in ordered]


def temporal_summary(times, values):
    solar = {"visible":"illuminated", "obstructed":"shadowed", "unresolved":"unknown"}
    states = [sample["criterion_state"] for sample in values]
    model = summarize(times, [{"state":solar[state]} for state in states])
    reverse = {v:k for k,v in solar.items()}
    known = [(time, state) for time, state in zip(times, states) if state != "unresolved"]
    transitions = [{"start_utc":utc(start), "end_utc":utc(end), "from_state":before, "to_state":after}
                   for (start,before), (end,after) in zip(known, known[1:]) if before != after]
    return {"duration_s": {reverse[key]:value for key,value in model["duration_s"].items()},
            "longest_visible_s": model["longest_clear_s"], "longest_interruption_s": model["longest_shadow_s"],
            "fraction_classified_time_visible": model["fraction_known_time_clear"], "transitions": transitions,
            "intervals": [{**row, "state":reverse[row["state"]]} for row in model["intervals"]]}


def provenance_for_earth(terrain, mask, criterion):
    shared = provenance(terrain)
    return {"site_id":shared["site_id"], "terrain":shared["terrain"], "celestial":shared["celestial"],
            "method":{"name":"Native LOLA spherical cell Earth visibility", "grazing_tolerance_deg":shared["method"]["grazing_tolerance_deg"],
                      "radial_ceiling_m":shared["method"]["radial_ceiling_m"], "maximum_trace_distance_m":shared["method"]["maximum_trace_distance_m"],
                      "rim_rays":RIM_RAYS, "rms":shared["method"]["rms"]},
            "antenna_min_elevation_deg":mask, "criterion":criterion,
            "quality_flags":["geometric_visibility_only", "finite_terrain_extent", "spherical_earth_disc",
                             "nominal_native_cell_model", "rms_sensitivity_only" if terrain.rms is not None else "elevation_rms_unavailable"]}


def observer_analysis(site_id, point, times, mask, criterion, adaptive=False):
    covered_et(times[0])
    covered_et(times[-1])
    terrain = load_terrain(site_id)
    row, col = terrain.point_cell(point)
    if not np.isfinite(terrain.dem[row, col]):
        raise UnsupportedObserver(f"The selected {site_id} observation pixel has no valid native elevation.")
    observer = terrain.cell_observer(row, col)
    def calculate(time):
        return with_mask(physical_sample(terrain, observer, time), mask, criterion)
    requested_count = len(times)
    samples = [calculate(time) for time in times]
    if adaptive:
        times, samples = refine(times, samples, calculate)
    return {**provenance_for_earth(terrain, mask, criterion), "observer":asdict(observer), "requested_point_m":point,
            "samples":samples, "summary":temporal_summary(times, samples), "requested_sample_count":requested_count,
            "refinement_sample_count":len(times)-requested_count}


def spatial_counts(cells):
    counts = {"invalid":cells.count(None), "valid":sum(cell is not None for cell in cells)}
    valid = [cell for cell in cells if cell is not None]
    counts.update({f"centre_{state}":sum(cell["centre_state"] == state for cell in valid) for state in CENTRE_STATES})
    counts.update({f"disc_{state}":sum(cell["disc_state"] == state for cell in valid) for state in DISC_STATES})
    counts["geometric_above_horizontal"] = sum(cell["centre_above_horizontal"] for cell in valid)
    counts["antenna_eligible"] = sum(cell["antenna_eligible"] for cell in valid)
    counts["centre_native_clear"] = sum(cell["centre_native_clear"] for cell in valid)
    counts["rms_sensitive"] = sum(cell["rms_sensitive"] is True for cell in valid)
    return counts, {key:100*count/counts["valid"] if counts["valid"] else None
                    for key, count in counts.items() if key not in ("invalid","valid")}


def region_analysis(site_id, point, timestamp, side, mask, criterion):
    covered_et(timestamp)
    terrain = load_terrain(site_id)
    left, top, affine, observers = native_region(terrain, point, side)
    cells = [with_mask(physical_sample(terrain, observer, timestamp), mask, criterion) if observer else None
             for observer in observers]
    counts, percentages = spatial_counts(cells)
    return {**provenance_for_earth(terrain, mask, criterion), "utc":utc(timestamp),
            "region":{"left":left, "top":top, "width":side, "height":side, "affine":list(affine)[:6],
                      "requested_point_m":point, "observers":[asdict(observer) if observer else None for observer in observers]},
            "cells":cells, "counts":counts, "percent_of_valid":percentages}
