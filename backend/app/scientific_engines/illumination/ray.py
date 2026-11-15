"""Spherical, native-cell traversal for one lunar solar-centre ray."""
from math import acos, cos, degrees, hypot, radians, sin, tan

import numpy as np

from app.scientific_engines.ephemeris.observer import local_basis
from app.scientific_engines.terrain.lunar_context import RADIUS

GRAZE_DEG = 0.0001
# Conservative model ceiling, based on the published 10,792 m LOLA maximum.
CEILING_M = 12_000.0
# Exceeds the diameter of each catalogued native site footprint.
TRACE_M = 40_000
ANGLE_EPS = 1e-12


def _crossings(numerator, denominator, size, limit):
    """Roots of pixel_coordinate(u) = grid line, for u = tan(theta/2)."""
    a, b, c = numerator[:, None] - denominator[:, None] * np.arange(size + 1)
    linear = np.abs(a) <= 1e-13
    discriminant = b*b - 4*a*c
    with np.errstate(divide="ignore", invalid="ignore"):
        root = -0.5 * (b + np.copysign(np.sqrt(np.maximum(discriminant, 0)), b))
        first = np.where(linear, -c/b, root/a)
        second = np.where(~linear & (discriminant >= 0), c/root, np.nan)
    roots = np.concatenate((np.where(linear | (discriminant >= 0), first, np.nan), second))
    return roots[(roots > ANGLE_EPS) & (roots < limit)]


def cell_intervals(inverse, shape, basis, azimuth_deg, max_theta):
    """Traverse a great circle in exact south-polar stereographic pixel coordinates."""
    azimuth = radians(azimuth_deg)
    tangent = sin(azimuth) * basis[0] + cos(azimuth) * basis[1]
    up = basis[2]
    # Body-fixed XYZ times (1+u²), then x=2RY/(1-Z), y=2RX/(1-Z).
    coeff = np.stack((-up, 2*tangent, up), axis=1)
    denominator = np.array([1, 0, 1]) - coeff[2]
    y, x = 2*RADIUS * coeff[:2]
    column = inverse.a*x + inverse.b*y + inverse.c*denominator
    row = inverse.d*x + inverse.e*y + inverse.f*denominator
    limit = tan(max_theta/2)
    edges = np.sort(np.concatenate(([0, limit], _crossings(column, denominator, shape[1], limit),
                                    _crossings(row, denominator, shape[0], limit))))
    lo, hi = edges[:-1], edges[1:]
    keep = hi - lo > ANGLE_EPS
    lo, hi = lo[keep], hi[keep]
    middle = (lo + hi)/2
    divisor = np.polyval(denominator, middle)
    rows = np.floor(np.polyval(row, middle) / divisor).astype(int)
    cols = np.floor(np.polyval(column, middle) / divisor).astype(int)
    inside = (0 <= rows) & (rows < shape[0]) & (0 <= cols) & (cols < shape[1])
    first_outside = np.flatnonzero(~inside)
    count = int(first_outside[0]) if len(first_outside) else len(rows)
    return rows[:count], cols[:count], 2*np.arctan(lo[:count]), 2*np.arctan(hi[:count]), bool(len(first_outside))


def _horizon(heights, origin_height, start, end):
    """Maximum ray angle over each constant-radius cell interval."""
    target = RADIUS + heights
    observer = RADIUS + origin_height
    peak = np.arccos(np.clip(target/observer, -1, 1))
    theta = np.clip(peak, start, end)
    # Stable form of target*cos(theta)-observer for metre-scale distances.
    up = heights - origin_height - 2*target*np.sin(theta/2)**2
    return np.degrees(np.arctan2(up, target*np.sin(theta))), theta


def ceiling_angle(observer_height, elevation):
    e = radians(max(0, elevation - GRAZE_DEG))
    ratio = (RADIUS + observer_height)/(RADIUS + CEILING_M)
    return acos(min(1, ratio*cos(e))) - e


def trace_ray(terrain, observer, azimuth, elevation, *, inspect_below=False, rms=True):
    info = {"native_horizon_deg": None, "horizon_distance_m": None,
            "cells_traced": 0, "nodata_along_ray": 0, "traced_distance_m": 0.0,
            "rms_horizon_deg": None, "rms_sensitive": None}
    if elevation < -GRAZE_DEG and (not inspect_below or azimuth is None):
        return {**info, "state": "shadowed", "native_state": "shadowed", "reason": "below_horizontal"}
    if azimuth is None:
        return {**info, "state": "illuminated", "native_state": "clear", "reason": "zenith_ray"}

    basis = local_basis(observer.latitude_deg, observer.longitude_deg_east)
    # For outward rays r*cos(theta+elevation) = observer_radius*cos(elevation).
    to_ceiling = ceiling_angle(observer.elevation_m, elevation)
    max_theta = min(TRACE_M/RADIUS, to_ceiling)
    rows, cols, start, end, leaves_grid = cell_intervals(terrain.inverse, terrain.dem.shape, basis, azimuth, max_theta)
    height = terrain.dem[rows, cols]
    valid = np.isfinite(height)
    info.update(cells_traced=len(rows), nodata_along_ray=int(np.count_nonzero(~valid)),
                traced_distance_m=float(end[-1]*RADIUS) if len(end) else 0.0)
    away = valid & ((rows != observer.source_pixel_row) | (cols != observer.source_pixel_column))
    nominal, theta = _horizon(height[away], observer.elevation_m, start[away], end[away])
    horizon = max(0.0, float(nominal.max())) if nominal.size else 0.0
    info["native_horizon_deg"] = horizon
    if horizon > 0:
        info["horizon_distance_m"] = float(theta[nominal.argmax()]*RADIUS)
    sigma = terrain.rms if rms else None
    if sigma is not None:
        observer_sigma = sigma[observer.source_pixel_row, observer.source_pixel_column]
        cell_sigma = sigma[rows[away], cols[away]]
        if np.isfinite(observer_sigma) and np.isfinite(cell_sigma).all() and info["nodata_along_ray"] == 0:
            low, _ = _horizon(height[away]-cell_sigma, observer.elevation_m+observer_sigma, start[away], end[away])
            high, _ = _horizon(height[away]+cell_sigma, observer.elevation_m-observer_sigma, start[away], end[away])
            limits = [max(0.0, float(vals.max())) if vals.size else 0.0 for vals in (low, high)]
            info.update(rms_horizon_deg=limits, rms_sensitive=bool(limits[0]-GRAZE_DEG <= elevation <= limits[1]+GRAZE_DEG))

    if elevation < -GRAZE_DEG:
        return {**info, "state": "shadowed", "native_state": "shadowed", "reason": "below_horizontal"}
    if elevation < horizon - GRAZE_DEG:
        return {**info, "state": "shadowed", "native_state": "shadowed", "reason": "native_terrain_obstruction"}
    if abs(elevation-horizon) <= GRAZE_DEG:
        return {**info, "state": "unknown", "native_state": "unknown", "reason": "grazing"}
    if info["nodata_along_ray"]:
        return {**info, "state": "unknown", "native_state": "unknown", "reason": "nodata_along_ray"}
    if leaves_grid or max_theta < to_ceiling:
        return {**info, "state": "unknown", "native_state": "clear", "reason": "terrain_extent"}
    return {**info, "state": "illuminated", "native_state": "clear", "reason": "clears_model_ceiling"}


def trace(terrain, observer, sun):
    elevation, azimuth = sun["elevation_deg"], sun["azimuth_deg"]
    return {"solar_elevation_deg": elevation, "solar_azimuth_deg": azimuth,
            "solar_angular_radius_deg": sun["angular_diameter_deg"] / 2,
            "centre_above_horizontal": elevation > 0, "sun_enu_unit_vector": sun["enu_unit_vector"],
            **trace_ray(terrain, observer, azimuth, elevation)}
