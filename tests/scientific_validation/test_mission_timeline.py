from dataclasses import replace

import pytest

from app.models.mission_timeline import MissionProfile
from app.scientific_engines.ephemeris.geometry import utc_datetime
from app.scientific_engines.ephemeris.observer import Observer
from app.scientific_engines.mission_timeline import Evidence, align, bracket_transitions, classify, intervals, summary
from app.scientific_engines.mission_service import refine

PROFILE = MissionProfile()
OBS = Observer("Site04",-89.7,-171,700,-1000,-7000,1600,1600,"","site04.tif","hash","native pixel centre")


@pytest.mark.parametrize("sun,earth,antenna,expected",[
    ("illuminated","visible","satisfied","favourable"),
    ("shadowed","visible","satisfied","unfavourable"),
    ("illuminated","obstructed","satisfied","unfavourable"),
    ("illuminated","unresolved","below_mask","unfavourable"),
    ("unresolved","visible","satisfied","unresolved"),
    ("illuminated","unresolved","satisfied","unresolved"),
    ("invalid","obstructed","satisfied","invalid"),
])
def test_classification_precedence(sun,earth,antenna,expected):
    assert classify(sun,earth,antenna,"unresolved",PROFILE) == expected


def test_optional_condition_and_minimum_duration_are_separate():
    profile = MissionProfile(prefer_full_disc=True)
    assert classify("illuminated","visible","satisfied","partially_visible",profile) == "conditional"
    assert classify("illuminated","visible","satisfied","invalid",profile) == "conditional"
    assert classify("illuminated","visible","satisfied","fully_visible",profile) == "favourable"
    assert classify("shadowed","visible","satisfied","fully_visible",MissionProfile(solar_required=False)) == "favourable"


def sun(time,state="illuminated"):
    return {"utc":time,"state":state}


def earth(time,state="visible",disc="fully_visible",eligible=True):
    return {"utc":time,"centre_state":state,"disc_state":disc,"antenna_eligible":eligible,
            "disc_probe_counts":{"obstructed":0,"visible":0}}


def evidence(samples,observer=OBS,stamp=("native",)):
    return Evidence(observer,stamp,samples)


def test_invalid_disc_does_not_invalidate_independent_earth_centre():
    label = "2026-01-01T00:00:00Z"
    date = utc_datetime(label)
    solar = evidence([sun(label)])
    world = evidence([earth(label,disc=None)])
    _, points = align(solar,world,[date],PROFILE)
    assert points[0]["tracks"]["earth_disc"] == "invalid"
    assert points[0]["tracks"]["mission"] == "favourable"
    _, points = align(solar,world,[date],MissionProfile(earth_requirement="full_disc"))
    assert points[0]["tracks"]["mission"] == "invalid"


def test_alignment_preserves_unequal_grids_and_conflicting_evidence():
    labels = ["2025-12-31T23:00:00Z","2026-01-01T00:00:00Z","2026-01-01T01:00:00Z","2026-01-01T02:00:00Z"]
    dates = list(map(utc_datetime,labels))
    s = evidence([sun(labels[0]),sun(labels[0].replace("Z","+00:00")),sun(labels[1]),sun(labels[3])])
    e = evidence([earth(labels[0]),earth(labels[2]),earth(labels[3])])
    times,points = align(s,e,[dates[0],dates[-1]],PROFILE)
    assert times == dates
    assert [p["tracks"]["mission"] for p in points] == ["favourable","unresolved","unresolved","favourable"]
    assert points[1]["earth_source_utc"] is None and points[2]["solar_source_utc"] is None
    assert summary(intervals(times,points,PROFILE),[],PROFILE)["duration_s"]["unresolved"] == 10800
    with pytest.raises(ValueError,match="versions"):
        align(s,evidence(e.samples,stamp=("other",)),dates,PROFILE)
    with pytest.raises(ValueError,match="observer"):
        align(s,evidence(e.samples,replace(OBS,elevation_m=901)),dates,PROFILE)
    with pytest.raises(ValueError,match="duplicate"):
        align(evidence([sun(labels[0]),sun(labels[0],"shadowed")]),e,dates,PROFILE)
    with pytest.raises(ValueError,match="outside"):
        align(s,e,dates[1:],PROFILE)


def test_switching_blockers_does_not_assign_favourable_or_unfavourable_time():
    labels = [f"2026-01-01T0{hour}:00:00Z" for hour in range(6)]
    dates = list(map(utc_datetime,labels))
    solar = ["illuminated","illuminated","shadowed","illuminated","illuminated","illuminated"]
    world = ["visible","visible","visible","obstructed","visible","visible"]
    profile = MissionProfile(minimum_window_s=3601)
    times,samples = align(evidence([sun(label,value) for label,value in zip(labels,solar)]),
                          evidence([earth(label,value) for label,value in zip(labels,world)]),dates,profile)
    transitions = bracket_transitions(times,samples)
    rows = intervals(times,samples,profile)
    assert rows[2]["tracks"]["mission"] == "unresolved"
    totals = summary(rows,transitions,profile)
    assert totals["duration_s"]["favourable"] == 7200
    assert totals["duration_s"]["unresolved"] == 10800
    assert len(totals["favourable_windows"]) == 2 and totals["qualifying_favourable_s"] == 0
    assert any(row["track"] == "solar" for row in transitions)
    with pytest.raises(ValueError,match="strictly increasing"):
        intervals([times[0],times[0]],samples[:2],profile)


def test_refinement_inserts_real_observations_with_a_fixed_budget():
    start,end = list(map(utc_datetime,["2026-01-01T00:00:00Z","2026-01-01T01:00:00Z"]))
    def read(time):
        state = "illuminated" if (time-start).total_seconds() < 1000 else "shadowed"
        _,points = align(evidence([sun(time.isoformat(),state)]),evidence([earth(time.isoformat())]),[time],PROFILE)
        return points[0]
    points = refine([start,end],read,4)
    assert len(points) == 4 and all(start < point < end for point in points)
