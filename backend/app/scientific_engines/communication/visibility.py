"""Evidence-based centre and finite-disc Earth terrain visibility."""
from math import atan2, cos, degrees, hypot, radians, sin

import numpy as np

from app.scientific_engines.ephemeris.observer import azimuth_elevation
from app.scientific_engines.illumination.ray import GRAZE_DEG, TRACE_M, ceiling_angle, trace_ray
from app.scientific_engines.terrain.lunar_context import RADIUS

RIM_RAYS = 8
RAY_STATES = {"illuminated": "visible", "shadowed": "obstructed", "unknown": "unresolved"}


def disc_rim(centre, radius_deg):
    """Sample the angular small circle in ENU, with its vertical extrema first."""
    direction = np.asarray(centre, dtype=float)
    direction /= np.linalg.norm(direction)
    vertical = np.array([0., 0., 1.]) - direction * direction[2]
    if np.linalg.norm(vertical) < 1e-12:
        vertical = np.array([0., 1., 0.])
    vertical /= np.linalg.norm(vertical)
    across = np.cross(direction, vertical)
    radius = radians(radius_deg)
    phases = (0, 4, 2, 6, 1, 3, 5, 7)
    for phase in phases:
        angle = 2*np.pi*phase/RIM_RAYS
        yield azimuth_elevation(cos(radius)*direction + sin(radius)*(cos(angle)*vertical + sin(angle)*across))


def enclosing_blocker(terrain, observer):
    """A complete, elevated first ring gives a lower horizon bound for every bearing."""
    row, col = observer.source_pixel_row, observer.source_pixel_column
    if row < 1 or col < 1 or row+1 >= terrain.dem.shape[0] or col+1 >= terrain.dem.shape[1]:
        return 0.0
    neighborhood = terrain.dem[row-1:row+2, col-1:col+2].ravel()
    ring = neighborhood[[0, 1, 2, 3, 5, 6, 7, 8]]
    if not np.isfinite(ring).all() or ring.min() <= observer.elevation_m:
        return 0.0
    linear = terrain.transform
    # Projection scale is at least one, so projected corner distance bounds
    # the great-circle distance to the edge of the origin pixel.
    far = max(hypot(linear.a*x + linear.b*y, linear.d*x + linear.e*y)
              for x in (-.5, .5) for y in (-.5, .5))
    theta = far/RADIUS
    radius = RADIUS + float(ring.min())
    delta = float(ring.min()) - observer.elevation_m - 2*radius*sin(theta/2)**2
    return max(0.0, degrees(atan2(delta, radius*sin(theta))))


def clear_envelope(terrain, observer, lowest_elevation):
    """Prove clearance over the entire disc with a conservative height envelope."""
    if lowest_elevation <= GRAZE_DEG:
        return False
    theta = ceiling_angle(observer.elevation_m, lowest_elevation)
    if theta*RADIUS > TRACE_M:
        return False
    # Bound the stereographic scale throughout a spherical disk around the observer.
    northmost = min(90, observer.latitude_deg + degrees(theta))
    divisor = 1-sin(radians(northmost))
    if divisor <= 0:
        return False
    scale = 2/divisor
    inv = terrain.inverse
    row_norm, col_norm = hypot(inv.d, inv.e), hypot(inv.a, inv.b)
    row, col = observer.source_pixel_row, observer.source_pixel_column
    row_span = int(np.ceil(theta*RADIUS*scale*row_norm))
    col_span = int(np.ceil(theta*RADIUS*scale*col_norm))
    if (row-row_span < 0 or col-col_span < 0 or row+row_span >= terrain.dem.shape[0] or
            col+col_span >= terrain.dem.shape[1]):
        return False
    box = terrain.dem[row-row_span:row+row_span+1, col-col_span:col+col_span+1]
    if not np.isfinite(box).all():
        return False
    rise = max(0.0, float(box.max())-observer.elevation_m)
    # Lower bound on distance beyond the first cell, even for a skewed affine.
    near_theta = .5/(scale*max(row_norm, col_norm)*RADIUS)
    horizontal = (RADIUS+float(box.min()))*sin(near_theta)
    return degrees(atan2(rise, horizontal)) < lowest_elevation-GRAZE_DEG


def evaluate(terrain, observer, earth):
    azimuth, elevation = earth["azimuth_deg"], earth["elevation_deg"]
    radius = earth["angular_diameter_deg"]/2
    upper, lower = min(90.0, elevation+radius), max(-90.0, elevation-radius)
    centre = trace_ray(terrain, observer, azimuth, elevation, inspect_below=True)
    centre_state = RAY_STATES[centre["state"]]
    horizon = centre["native_horizon_deg"]
    clearance = {key: angle-horizon if horizon is not None else None
                 for key, angle in (("centre", elevation), ("upper_limb", upper), ("lower_limb", lower))}
    counts = dict.fromkeys(RAY_STATES.values(), 0)
    counts[centre_state] += 1
    native_visible = int(centre["native_state"] == "clear")
    native_obstructed = int(centre["native_state"] == "shadowed")
    missing_probes = int(centre["nodata_along_ray"] > 0)
    if upper < enclosing_blocker(terrain, observer)-GRAZE_DEG:
        disc, evidence = "fully_obscured", "all_bearings_below_horizon_bound"
    elif centre_state == "visible" and clear_envelope(terrain, observer, lower):
        disc, evidence = "fully_visible", "complete_terrain_envelope"
    else:
        for rim_azimuth, rim_elevation in disc_rim(earth["enu_unit_vector"], radius):
            probe = trace_ray(terrain, observer, rim_azimuth, rim_elevation, rms=False)
            counts[RAY_STATES[probe["state"]]] += 1
            native_visible += probe["native_state"] == "clear"
            native_obstructed += probe["native_state"] == "shadowed"
            missing_probes += probe["nodata_along_ray"] > 0
        if counts["visible"] and counts["obstructed"]:
            disc, evidence = "partially_visible", "confirmed_clear_and_blocked_directions"
        else:
            disc, evidence = "unresolved", "insufficient_whole_disc_evidence"
    return {"earth_azimuth_deg": azimuth, "earth_elevation_deg": elevation,
            "earth_angular_radius_deg": radius, "earth_enu_unit_vector": earth["enu_unit_vector"],
            "upper_limb_elevation_deg": upper, "lower_limb_elevation_deg": lower,
            "centre_above_horizontal": elevation > 0, "centre_state": centre_state,
            "centre_native_clear": centre["native_state"] == "clear",
            "centre_reason": centre["reason"], "native_horizon_deg": horizon,
            "horizon_distance_m": centre["horizon_distance_m"], "traced_distance_m": centre["traced_distance_m"],
            "centre_nodata_cells": centre["nodata_along_ray"], "clearance_deg": clearance,
            "rms_horizon_deg": centre["rms_horizon_deg"], "rms_sensitive": centre["rms_sensitive"],
            "disc_state": disc, "disc_evidence": evidence, "disc_probe_counts": counts,
            "native_clear_probes": native_visible, "native_obstructed_probes": native_obstructed,
            "probes_crossing_nodata": missing_probes}
