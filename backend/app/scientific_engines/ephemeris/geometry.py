"""Airless apparent topocentric Sun and Earth geometry."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from math import asin, degrees
import re

import numpy as np
import spiceypy as spice
from spiceypy.utils.exceptions import SpiceyError

from app.scientific_engines.terrain.lunar_context import RADIUS
from .kernels import BODY_FRAME, LOCK, KernelUnavailable, _load
from .observer import azimuth_elevation, local_basis

MAX_SAMPLES = 241
MIN_STEP_S = 60
MAX_STEP_S = 604800
TIME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)")
CONVENTIONS = {
    "inertial_frame": "J2000 (ICRF)",
    "body_fixed_frame": BODY_FRAME,
    "local_frame": "East, North, Up (right-handed)",
    "azimuth": "Degrees clockwise from true north in [0, 360); undefined at zenith/nadir",
    "elevation": "Degrees above the plane perpendicular to the radial up vector",
    "latitude": "Planetocentric; longitude positive east",
    "input_time_scale": "UTC",
    "internal_time_scale": "SPICE ET, TDB seconds past J2000",
    "direction": "Airless apparent body-centre direction",
    "aberration_correction": "CN+S (converged reception light-time and stellar aberration)",
    "refraction": False,
    "gravitational_light_deflection": False,
    "angular_diameter": "Equatorial-radius spherical disk model",
}


class InvalidEpoch(ValueError):
    pass


def utc_datetime(value):
    if not TIME_PATTERN.fullmatch(value):
        raise InvalidEpoch("Use an ISO 8601 UTC timestamp including seconds and Z or +00:00.")
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except ValueError as exc:
        raise InvalidEpoch("Invalid UTC calendar time. Leap-second notation (:60) is unsupported.") from exc


def epochs(start, end, step_seconds):
    if end < start:
        raise InvalidEpoch("The time range end must be at or after the start.")
    step = timedelta(seconds=step_seconds)
    count = (end - start) // step + 1
    if count > MAX_SAMPLES:
        raise InvalidEpoch(f"Time series exceeds {MAX_SAMPLES} samples. Increase the increment or shorten the range.")
    return [start + index * step for index in range(count)]


def covered_et(timestamp):
    with LOCK:
        start, end = _load()
        et = spice.utc2et(timestamp.isoformat().replace("+00:00", ""))
        # Bound tiny round-trip differences for the published UTC endpoints.
        if et < start - 1e-6 or et > end + 1e-6:
            raise InvalidEpoch("Observation timestamp is outside the loaded ephemeris coverage.")
        return min(max(et, start), end)


@lru_cache(maxsize=4096)
def geometry_at(observer, timestamp):
    with LOCK:
        et = covered_et(timestamp)
        try:
            rotation = spice.pxform("J2000", BODY_FRAME, et)
            basis = local_basis(observer.latitude_deg, observer.longitude_deg_east)
            position = basis[2] * ((RADIUS + observer.elevation_m) / 1000)
            directions = {}
            for body in ("Sun", "Earth"):
                state, light_time = spice.spkcpo(body, et, "J2000", "OBSERVER", "CN+S",
                                                position, "MOON", BODY_FRAME)
                distance = float(np.linalg.norm(state[:3]))
                fixed = rotation @ (state[:3] / distance)
                enu = basis @ fixed
                azimuth, elevation = azimuth_elevation(enu)
                radius = float(spice.bodvrd(body.upper(), "RADII", 3)[1][0])
                directions[body.lower()] = {
                    "azimuth_deg": azimuth, "elevation_deg": elevation,
                    "body_fixed_unit_vector": fixed.tolist(), "enu_unit_vector": enu.tolist(),
                    "distance_km": distance, "angular_diameter_deg": degrees(2 * asin(radius / distance)),
                    "light_time_s": light_time,
                    "above_local_horizontal": elevation > 0,
                }
        except SpiceyError as exc:
            raise KernelUnavailable("SPICE could not compute geometry inside the published kernel coverage.") from exc
        return {"utc": timestamp.isoformat().replace("+00:00", "Z"), "et_tdb_s": et, **directions}
