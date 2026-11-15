from datetime import timedelta
from math import cos, radians, sin

import numpy as np
import pytest
from rasterio.transform import Affine

from app.scientific_engines.communication.service import refine, spatial_counts, temporal_summary, with_mask
from app.scientific_engines.communication.visibility import GRAZE_DEG, disc_rim, evaluate
from app.scientific_engines.ephemeris.geometry import utc_datetime
from app.scientific_engines.ephemeris.observer import Observer
from app.scientific_engines.illumination.service import Terrain


def fixture(ridge=False, missing=False):
    height = 11990.0
    dem = np.full((101,101), height)
    if ridge:
        dem[50,51] += 0.20
    if missing:
        dem[50,51] = np.nan
    affine = Affine(5,0,-252.5,0,-5,30252.5)
    source = Observer("Synthetic",0,0,0,0,0,0,0,"","","","")
    terrain = Terrain(dem,None,affine,~affine,source,(5,5),(),None)
    return terrain, terrain.cell_observer(50,50)


def earth(elevation, radius=1, azimuth=90):
    a,e = radians(azimuth),radians(elevation)
    return {"azimuth_deg":azimuth, "elevation_deg":elevation, "angular_diameter_deg":2*radius,
            "enu_unit_vector":[sin(a)*cos(e),cos(a)*cos(e),sin(e)]}


def test_full_disc_envelope_and_independent_mask_boundary():
    terrain, observer = fixture()
    sample = evaluate(terrain,observer,earth(4))
    assert sample["centre_state"] == "visible" and sample["disc_state"] == "fully_visible"
    assert sample["clearance_deg"] == {"centre":4, "lower_limb":3, "upper_limb":5}
    assert with_mask(sample,4,"centre_with_mask")["criterion_state"] == "visible"
    raised = with_mask(sample,4.0001,"centre_with_mask")
    assert not raised["antenna_eligible"] and raised["centre_state"] == "visible"
    assert raised["criterion_state"] == "obstructed"


def test_ridge_blocks_centre_while_upper_disc_ray_is_visible():
    terrain, observer = fixture(ridge=True)
    sample = evaluate(terrain,observer,earth(4))
    assert sample["centre_state"] == "obstructed" and sample["disc_state"] == "partially_visible"
    assert sample["clearance_deg"]["centre"] < 0 < sample["clearance_deg"]["upper_limb"]
    assert sample["disc_probe_counts"]["visible"] and sample["disc_probe_counts"]["obstructed"]
    assert with_mask(sample,1,"any_disc")["criterion_state"] == "visible"
    assert with_mask(sample,1,"full_disc")["criterion_state"] == "obstructed"
    horizon = sample["native_horizon_deg"]
    grazing = evaluate(terrain,observer,earth(horizon+GRAZE_DEG/10))
    assert grazing["centre_state"] == "unresolved"


def test_lower_than_horizontal_or_enclosed_disc_is_obscured():
    terrain, observer = fixture()
    assert evaluate(terrain,observer,earth(-2))["disc_state"] == "fully_obscured"
    terrain.dem[49:52,49:52] += 1
    terrain.dem[50,50] = observer.elevation_m
    assert evaluate(terrain,observer,earth(5))["disc_state"] == "fully_obscured"
    assert evaluate(terrain,observer,earth(-1))["upper_limb_elevation_deg"] == 0


def test_nodata_and_raster_edge_leave_clearance_unresolved():
    grid, observer = fixture(missing=True)
    result = evaluate(grid,observer,earth(4))
    assert result["centre_state"] == "unresolved" and result["disc_state"] == "unresolved"
    assert result["centre_nodata_cells"] == 1
    grid, _ = fixture()
    edge = grid.cell_observer(50,100)
    result = evaluate(grid,edge,earth(2))
    assert result["centre_state"] == "unresolved" and result["centre_native_clear"]
    assert result["disc_state"] != "fully_visible"


def test_disc_rim_lies_at_angular_radius_across_azimuth_wrap():
    direction = earth(3, azimuth=359.9)["enu_unit_vector"]
    rim = list(disc_rim(direction,1))
    assert rim[0][1] == pytest.approx(4) and rim[1][1] == pytest.approx(2)
    assert any(azimuth < 1.5 for azimuth,_ in rim)
    for azimuth,elevation in rim:
        ray = earth(elevation,azimuth=azimuth)["enu_unit_vector"]
        assert np.dot(direction,ray) == pytest.approx(cos(radians(1)), abs=1e-13)


def test_bracket_refinement_and_unresolved_time_accounting():
    start = utc_datetime("2026-01-01T00:00:00Z")
    times = [start+timedelta(hours=i) for i in range(4)]
    def calculate(time):
        elapsed = (time-start).total_seconds()
        state = "visible" if elapsed < 2400 or elapsed >= 8400 else "obstructed"
        return {"criterion_state":state}
    refined, values = refine(times,[calculate(time) for time in times],calculate)
    report = temporal_summary(refined,values)
    assert 4 < len(refined) <= 28
    assert len(report["transitions"]) == 2
    assert 0 < report["duration_s"]["unresolved"] <= 120
    assert sum(report["duration_s"].values()) == 10800
    for state in ("visible","obstructed","unresolved"):
        output = temporal_summary(times,[{"criterion_state":state}]*4)
        assert output["duration_s"][state] == 10800
    values = [{"criterion_state":state} for state in ("visible","unresolved","obstructed","obstructed")]
    output = temporal_summary(times,values)
    assert output["duration_s"]["unresolved"] == 7200
    assert output["transitions"][0]["end_utc"] == "2026-01-01T02:00:00Z"


def test_spatial_percentages_exclude_invalid_keep_unresolved():
    grid,observer = fixture()
    cells = [with_mask(evaluate(grid,observer,earth(4)),4,"centre"),
             with_mask(evaluate(grid,observer,earth(-2)),4,"centre"),None]
    cells.append({**cells[0],"centre_state":"unresolved","disc_state":"unresolved"})
    counts, percentages = spatial_counts(cells)
    assert counts["invalid"] == 1 and counts["valid"] == 3
    assert counts["centre_unresolved"] == 1 and counts["disc_fully_visible"] == 1
    assert percentages["centre_visible"] == pytest.approx(100/3)
