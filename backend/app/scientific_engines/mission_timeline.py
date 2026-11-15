"""Exact UTC alignment and conservative composition of measured conditions."""
from dataclasses import dataclass

from app.scientific_engines.communication.service import CENTRE_STATES, DISC_STATES, criterion_state
from app.scientific_engines.ephemeris.geometry import utc_datetime
from app.scientific_engines.ephemeris.observer import Observer

STATES = ("favourable", "unfavourable", "conditional", "unresolved", "invalid")
TRACKS = ("solar", "earth_centre", "earth_disc", "antenna", "mission")
RULES = [
    "Required invalid evidence takes precedence; otherwise a definite required failure is unfavourable.",
    "If no required condition fails, missing or unresolved required evidence leaves the result unresolved.",
    "After all required conditions pass, an enabled full-disc preference produces a conditional result unless full-disc visibility is established.",
    "Intervals use agreement of adjacent observations on each required condition. A change stays in a UTC bracket.",
    "The minimum duration qualifies continuous favourable windows separately from physical conditions.",
]


def utc(time):
    return time.isoformat().replace("+00:00", "Z")


@dataclass
class Evidence:
    observer: Observer
    terrain_version: tuple
    samples: list[dict]


def indexed(evidence, start, end):
    result = {}
    for sample in evidence.samples:
        stamp = utc_datetime(sample["utc"])
        if not start <= stamp <= end:
            raise ValueError("An upstream timestamp lies outside the requested window.")
        existing = result.get(stamp)
        if existing is not None:
            if {**existing, "utc": stamp} != {**sample, "utc": stamp}:
                raise ValueError("Conflicting duplicate upstream UTC observations.")
        else:
            result[stamp] = sample
    return result


def classify(solar, earth, antenna, disc, profile):
    required = [earth, antenna] + ([solar] if profile.solar_required else [])
    if "invalid" in required:
        return "invalid"
    if any(state in ("shadowed", "obstructed", "below_mask") for state in required):
        return "unfavourable"
    if "unresolved" in required:
        return "unresolved"
    if profile.prefer_full_disc and profile.earth_requirement != "full_disc":
        if disc != "fully_visible":
            return "conditional"
    return "favourable"


def observation(time, solar, earth, profile):
    flags = []
    solar_state = "unresolved"
    if solar is not None:
        solar_state = {"illuminated":"illuminated", "shadowed":"shadowed", "unknown":"unresolved"}.get(solar.get("state"), "invalid")
        if solar.get("rms_sensitive"):
            flags.append("solar_rms_sensitive")
    else:
        flags.append("solar_observation_missing_at_epoch")
    centre = disc = antenna = required_earth = "unresolved"
    if earth is not None:
        centre = earth.get("centre_state")
        centre = centre if centre in CENTRE_STATES else "invalid"
        disc = earth.get("disc_state")
        disc = disc if disc in DISC_STATES else "invalid"
        eligible = earth.get("antenna_eligible")
        antenna = "satisfied" if eligible is True else "below_mask" if eligible is False else "invalid"
        if profile.earth_requirement == "centre":
            required_earth = centre
        elif disc != "invalid":
            try:
                required_earth = criterion_state(earth, profile.earth_requirement)
            except (KeyError, TypeError):
                required_earth = "invalid"
        else:
            required_earth = "invalid"
        if earth.get("rms_sensitive"):
            flags.append("earth_rms_sensitive")
    else:
        flags.append("earth_observation_missing_at_epoch")
    mission = classify(solar_state, required_earth, antenna, disc, profile)
    return {"utc":utc(time), "solar_source_utc":solar["utc"] if solar else None, "earth_source_utc":earth["utc"] if earth else None,
            "tracks":{"solar":solar_state, "earth_centre":centre, "earth_disc":disc, "antenna":antenna, "mission":mission},
            "required_earth":required_earth, "solar_reason":solar.get("reason") if solar else None,
            "earth_reason":earth.get("centre_reason") if earth else None,
            "disc_evidence":earth.get("disc_evidence") if earth else None, "flags":flags}


def align(solar, earth, schedule, profile):
    if solar.observer != earth.observer or solar.terrain_version != earth.terrain_version:
        raise ValueError("Upstream observer or terrain versions do not match.")
    if not schedule or any(end <= start for start, end in zip(schedule,schedule[1:])):
        raise ValueError("The requested UTC schedule must be nonempty and strictly increasing.")
    start, end = schedule[0], schedule[-1]
    sun, world = indexed(solar,start,end), indexed(earth,start,end)
    times = sorted(set(schedule) | sun.keys() | world.keys())
    return times, [observation(time,sun.get(time),world.get(time),profile) for time in times]


def agreement(before, after):
    if "invalid" in (before, after):
        return "invalid"
    return before if before == after else "unresolved"


def bracket_transitions(times, samples):
    output = []
    for track in TRACKS:
        previous = None
        for time, sample in zip(times, samples, strict=True):
            state = sample["tracks"][track]
            if state == "invalid":
                previous = None
            elif state != "unresolved":
                if previous and previous[1] != state:
                    output.append({"track":track, "start_utc":utc(previous[0]), "end_utc":utc(time),
                                   "from_state":previous[1], "to_state":state})
                previous = (time,state)
    return sorted(output, key=lambda event: (event["start_utc"], event["end_utc"], TRACKS.index(event["track"])))


def intervals(times, samples, profile):
    if len(times) != len(samples) or any(b <= a for a,b in zip(times,times[1:])):
        raise ValueError("Interval timestamps must be strictly increasing and aligned.")
    result = []
    for start, end, before, after in zip(times, times[1:], samples, samples[1:]):
        tracks = {track:agreement(before["tracks"][track], after["tracks"][track]) for track in TRACKS[:-1]}
        required_earth = agreement(before["required_earth"], after["required_earth"])
        tracks["mission"] = classify(tracks["solar"],required_earth,tracks["antenna"],tracks["earth_disc"],profile)
        if (tracks["mission"] == "conditional" and
                (before["tracks"]["earth_disc"] == "fully_visible") != (after["tracks"]["earth_disc"] == "fully_visible")):
            tracks["mission"] = "unresolved"
        result.append({"start_utc":utc(start), "end_utc":utc(end), "duration_s":(end-start).total_seconds(),
                       "tracks":tracks, "requires_sampling":tracks["mission"] == "unresolved" or
                       any(before["tracks"][track] != after["tracks"][track] for track in TRACKS)})
    return result


def summary(rows, transitions, profile):
    totals = dict.fromkeys(STATES, 0.0)
    runs = []
    for row in rows:
        state = row["tracks"]["mission"]
        totals[state] += row["duration_s"]
        if runs and runs[-1]["state"] == state and runs[-1]["end_utc"] == row["start_utc"]:
            runs[-1]["end_utc"] = row["end_utc"]
            runs[-1]["duration_s"] += row["duration_s"]
        else:
            runs.append({key:row[key] for key in ("start_utc","end_utc","duration_s")} | {"state":state})
    favourable = [{key:value for key,value in run.items() if key != "state"} |
                  {"meets_minimum":run["duration_s"] >= profile.minimum_window_s}
                  for run in runs if run["state"] == "favourable"]
    return {"duration_s":totals, "longest_favourable_s":max((run["duration_s"] for run in favourable),default=0),
            "longest_unfavourable_s":max((run["duration_s"] for run in runs if run["state"] == "unfavourable"),default=0),
            "qualifying_favourable_s":sum(run["duration_s"] for run in favourable if run["meets_minimum"]),
            "transition_count":sum(row["track"] == "mission" for row in transitions), "favourable_windows":favourable}
