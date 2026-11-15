"""
LUNA-SCOPE — SPICE Geometric State Engine.

Implements E1-R6 §6.3:
- Instantaneous geometric state calculation in J2000 and MOON_ME.
- Rigorous rotating-frame transport velocity handling via full 6x6 sxform.
- Local topocentric East-North-Up (ENU) coordinates.
- Topocentric observables (azimuth, elevation, range, range-rate).
- Integration with LUNA-SCOPE kernel inventory.
"""

from __future__ import annotations

import dataclasses
from hashlib import sha256
import math
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import spiceypy as spice

from .kernels import _load, KERNELS, DEFAULT_DIRECTORY
from .provenance import HorizonsQueryError

# Canonical mean lunar radius (E1-R6 §2.1)
LUNAR_RADIUS_MEAN_KM: float = 1737.4
FRAME_MOON_ME: str = "MOON_ME"
FRAME_J2000: str = "J2000"


@dataclasses.dataclass(frozen=True)
class LunarSurfaceLocation:
    """
    Observer position on the lunar surface.
    Coordinates defined in lunar Mean Earth / Polar Axis frame (MOON_ME).
    """
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    site_name: str = ""
    radius_km: float = LUNAR_RADIUS_MEAN_KM

    @property
    def altitude_km(self) -> float:
        return self.altitude_m / 1000.0

    @classmethod
    def from_observer(cls, observer: Any) -> LunarSurfaceLocation:
        """Create a LunarSurfaceLocation from an existing LUNA-SCOPE Observer instance."""
        site_id = getattr(observer, "site_id", "OBSERVER")
        lat = getattr(observer, "latitude_deg", 0.0)
        lon = getattr(observer, "longitude_deg_east", getattr(observer, "longitude_deg", 0.0))
        elev = getattr(observer, "elevation_m", getattr(observer, "altitude_m", 0.0))
        return cls(latitude_deg=lat, longitude_deg=lon, altitude_m=elev, site_name=site_id)


@dataclasses.dataclass(frozen=True)
class SpiceGeometricState:
    """
    Immutable structured geometric state produced by SPICE DE440/MOON_ME ephemeris.
    All vectors are 3-element numpy arrays or tuples.
    """
    target_id: int
    target_name: str
    requested_epoch_utc: str
    spice_et_sec: float

    pos_j2000_km: np.ndarray
    vel_j2000_kms: np.ndarray
    pos_me_km: np.ndarray
    vel_me_kms: np.ndarray
    pos_enu_km: np.ndarray
    vel_enu_kms: np.ndarray

    azimuth_deg: float
    elevation_deg: float
    range_km: float
    range_rate_kms: float

    lsk_sha256: Optional[str] = None
    spk_sha256: Optional[str] = None
    pck_sha256: Optional[str] = None
    fk_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert state vectors and topocentric observables to JSON-serializable dictionary."""
        return {
            "target_id": self.target_id,
            "target_name": self.target_name,
            "requested_epoch_utc": self.requested_epoch_utc,
            "spice_et_sec": self.spice_et_sec,
            "pos_j2000_km": self.pos_j2000_km.tolist() if isinstance(self.pos_j2000_km, np.ndarray) else list(self.pos_j2000_km),
            "vel_j2000_kms": self.vel_j2000_kms.tolist() if isinstance(self.vel_j2000_kms, np.ndarray) else list(self.vel_j2000_kms),
            "pos_me_km": self.pos_me_km.tolist() if isinstance(self.pos_me_km, np.ndarray) else list(self.pos_me_km),
            "vel_me_kms": self.vel_me_kms.tolist() if isinstance(self.vel_me_kms, np.ndarray) else list(self.vel_me_kms),
            "pos_enu_km": self.pos_enu_km.tolist() if isinstance(self.pos_enu_km, np.ndarray) else list(self.pos_enu_km),
            "vel_enu_kms": self.vel_enu_kms.tolist() if isinstance(self.vel_enu_kms, np.ndarray) else list(self.vel_enu_kms),
            "azimuth_deg": self.azimuth_deg,
            "elevation_deg": self.elevation_deg,
            "range_km": self.range_km,
            "range_rate_kms": self.range_rate_kms,
            "kernels": {
                "lsk_sha256": self.lsk_sha256,
                "spk_sha256": self.spk_sha256,
                "pck_sha256": self.pck_sha256,
                "fk_sha256": self.fk_sha256,
            },
        }


def lunar_to_cartesian_me(
    latitude_deg: float,
    longitude_deg: float,
    altitude_m: float,
    radius_km: float = LUNAR_RADIUS_MEAN_KM,
) -> np.ndarray:
    """
    Convert spherical lunar selenographic coordinates (MOON_ME) to 3D Cartesian coordinates.
    radius = radius_km + altitude_m / 1000.0.
    """
    lat_rad = math.radians(latitude_deg)
    lon_rad = math.radians(longitude_deg)
    r = radius_km + (altitude_m / 1000.0)

    x = r * math.cos(lat_rad) * math.cos(lon_rad)
    y = r * math.cos(lat_rad) * math.sin(lon_rad)
    z = r * math.sin(lat_rad)
    return np.array([x, y, z], dtype=np.float64)


def enu_basis(latitude_deg: float, longitude_deg: float) -> np.ndarray:
    """
    Compute 3x3 orthonormal basis matrix whose rows are East, North, Up unit vectors in MOON_ME.
    Row 0: East
    Row 1: North
    Row 2: Up
    """
    lat = math.radians(latitude_deg)
    lon = math.radians(longitude_deg)

    east = np.array([-math.sin(lon), math.cos(lon), 0.0], dtype=np.float64)
    north = np.array([-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)], dtype=np.float64)
    up = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)], dtype=np.float64)

    return np.vstack([east, north, up])


def vector_me_to_azel(
    pos_enu: np.ndarray,
    vel_enu: Optional[np.ndarray] = None,
) -> Tuple[float, float, float, float]:
    """
    Compute Azimuth (deg clockwise from North [0, 360)), Elevation (deg above horizontal plane [-90, +90]),
    Range (km), and radial Range-rate (km/s) from an ENU position and optional velocity vector.
    """
    e, n, u = float(pos_enu[0]), float(pos_enu[1]), float(pos_enu[2])
    rng = math.sqrt(e * e + n * n + u * u)
    if rng < 1e-12:
        return 0.0, 0.0, 0.0, 0.0

    # Azimuth: clockwise from North in [0, 360)
    az_rad = math.atan2(e, n)
    az_deg = math.degrees(az_rad) % 360.0

    # Elevation: above horizon plane
    horiz = math.hypot(e, n)
    el_rad = math.atan2(u, horiz)
    el_deg = math.degrees(el_rad)

    # Range rate = (r . v) / ||r||
    range_rate = 0.0
    if vel_enu is not None:
        range_rate = float(np.dot(pos_enu, vel_enu) / rng)

    return az_deg, el_deg, rng, range_rate


def _parse_time_to_et(iso_utc: str) -> float:
    """Parse ISO UTC timestamp to SPICE Ephemeris Time (ET)."""
    # Clean input timestamp
    clean = iso_utc.strip()
    if clean.endswith("Z"):
        clean = clean[:-1]
    if "T" in clean and not clean.endswith(" UTC"):
        clean = clean.replace("T", " ") + " UTC"
    try:
        return float(spice.str2et(clean))
    except Exception as e:
        # Retry with direct string
        try:
            return float(spice.str2et(iso_utc.strip()))
        except Exception:
            raise HorizonsQueryError(
                f"Failed to convert UTC string '{iso_utc}' to SPICE ET: {e}",
                classification="TIME_CONVERSION_ERROR",
                details={"iso_utc": iso_utc, "error": str(e)},
            )


def compute_spice_geometric_state(
    target_id: Union[int, str],
    location: Union[LunarSurfaceLocation, Any],
    iso_utc: str,
    spice_manager: Optional[Any] = None,
) -> SpiceGeometricState:
    """
    Calculate the instantaneous geometric state (position, velocity, and topocentric observables)
    of a target celestial body relative to a lunar surface observer using NASA SPICE (DE440 / MOON_ME).

    Strictly compliant with E1-R6 §6.3 kinematics:
    1. Converts UTC epoch to SPICE ET via spice.str2et using loaded leapseconds kernel.
    2. Retrieves target state and Moon center state relative to Solar System Barycenter (SSB) in J2000.
    3. Evaluates observer site state in MOON_ME (v_site_me = 0 relative to lunar surface).
    4. Transforms site state to J2000 using full 6x6 state transformation sxform('MOON_ME', 'J2000', et).
    5. Constructs observer SSB state: observer_ssb = moon_ssb + site_ssb.
    6. Constructs geometric target-relative-to-observer state in J2000: rel_j2000 = target_ssb - observer_ssb.
    7. Transforms relative state into MOON_ME via sxform('J2000', 'MOON_ME', et), rigorously accounting
       for rotating-frame transport velocity: v_me = R v_j2000 - omega x (R r_j2000).
    8. Transforms relative state into local topocentric East-North-Up (ENU) coordinates.
    9. Computes geometric Azimuth, Elevation, Range, and radial Range-rate.
    """
    # 1. Ensure SPICE kernels are loaded
    if spice_manager is not None and hasattr(spice_manager, "load_kernels"):
        spice_manager.load_kernels()
    else:
        _load()

    # 2. Normalize target ID and name
    if isinstance(target_id, int):
        tid = target_id
        target_name = "Sun" if tid == 10 else ("Earth" if tid == 399 else f"Target_{tid}")
    else:
        t_clean = str(target_id).strip().upper()
        if t_clean in ("10", "SUN"):
            tid = 10
            target_name = "Sun"
        elif t_clean in ("399", "EARTH"):
            tid = 399
            target_name = "Earth"
        else:
            try:
                tid = int(t_clean)
                target_name = f"Target_{tid}"
            except ValueError:
                raise HorizonsQueryError(
                    f"Unknown target identifier '{target_id}'. Use 10 (Sun) or 399 (Earth).",
                    classification="INPUT_VALIDATION_ERROR",
                )

    # 3. Normalize observer location
    if not isinstance(location, LunarSurfaceLocation):
        loc = LunarSurfaceLocation.from_observer(location)
    else:
        loc = location

    # 4. Convert UTC to SPICE ET
    et = _parse_time_to_et(iso_utc)

    # 5. Retrieve target SSB state and Moon SSB state in J2000
    try:
        target_ssb_state, _ = spice.spkgeo(targ=tid, et=et, ref=FRAME_J2000, obs=0)
        target_ssb_pos = np.array(target_ssb_state[0:3], dtype=np.float64)
        target_ssb_vel = np.array(target_ssb_state[3:6], dtype=np.float64)

        moon_ssb_state, _ = spice.spkgeo(targ=301, et=et, ref=FRAME_J2000, obs=0)
        moon_ssb_pos = np.array(moon_ssb_state[0:3], dtype=np.float64)
        moon_ssb_vel = np.array(moon_ssb_state[3:6], dtype=np.float64)
    except Exception as e:
        raise HorizonsQueryError(
            f"SPICE ephemeris evaluation failed at ET {et}: {e}",
            classification="SPICE_CALCULATION_ERROR",
            details={"et": et, "target_id": tid, "error": str(e)},
        )

    # 6. Evaluate site state in MOON_ME (zero surface velocity)
    site_me_pos = lunar_to_cartesian_me(
        latitude_deg=loc.latitude_deg,
        longitude_deg=loc.longitude_deg,
        altitude_m=loc.altitude_m,
        radius_km=loc.radius_km,
    )
    site_me_vel = np.zeros(3, dtype=np.float64)
    site_me_state = np.hstack([site_me_pos, site_me_vel])

    # 7. Transform site state from MOON_ME to J2000 via 6x6 sxform
    try:
        sxform_me_to_j2000 = spice.sxform(FRAME_MOON_ME, FRAME_J2000, et)
        site_j2000_state = np.dot(sxform_me_to_j2000, site_me_state)
    except Exception as e:
        raise HorizonsQueryError(
            f"SPICE sxform from {FRAME_MOON_ME} to {FRAME_J2000} failed at ET {et}: {e}",
            classification="SPICE_CALCULATION_ERROR",
            details={"error": str(e)},
        )

    site_j2000_pos = site_j2000_state[0:3]
    site_j2000_vel = site_j2000_state[3:6]

    # 8. Observer SSB state in J2000
    obs_ssb_pos = moon_ssb_pos + site_j2000_pos
    obs_ssb_vel = moon_ssb_vel + site_j2000_vel

    # 9. Target relative to observer in J2000 (geometric)
    rel_j2000_pos = target_ssb_pos - obs_ssb_pos
    rel_j2000_vel = target_ssb_vel - obs_ssb_vel
    rel_j2000_state = np.hstack([rel_j2000_pos, rel_j2000_vel])

    # 10. Transform relative state from J2000 to MOON_ME via 6x6 sxform
    try:
        sxform_j2000_to_me = spice.sxform(FRAME_J2000, FRAME_MOON_ME, et)
        rel_me_state = np.dot(sxform_j2000_to_me, rel_j2000_state)
    except Exception as e:
        raise HorizonsQueryError(
            f"SPICE sxform from {FRAME_J2000} to {FRAME_MOON_ME} failed at ET {et}: {e}",
            classification="SPICE_CALCULATION_ERROR",
            details={"error": str(e)},
        )

    rel_me_pos = rel_me_state[0:3]
    rel_me_vel = rel_me_state[3:6]

    # 11. Project into local topocentric East-North-Up (ENU)
    basis = enu_basis(loc.latitude_deg, loc.longitude_deg)
    pos_enu = np.dot(basis, rel_me_pos)
    vel_enu = np.dot(basis, rel_me_vel)

    # 12. Compute topocentric observables
    az_deg, el_deg, rng_km, range_rate_kms = vector_me_to_azel(pos_enu, vel_enu)

    # 13. Gather kernel hashes
    kernel_hashes = {}
    for rel_path, digest in KERNELS.items():
        if "tls" in rel_path:
            kernel_hashes["lsk"] = digest
        elif "bsp" in rel_path:
            kernel_hashes["spk"] = digest
        elif "tpc" in rel_path or "bpc" in rel_path:
            kernel_hashes["pck"] = digest
        elif "tf" in rel_path:
            kernel_hashes["fk"] = digest

    return SpiceGeometricState(
        target_id=tid,
        target_name=target_name,
        requested_epoch_utc=iso_utc,
        spice_et_sec=et,
        pos_j2000_km=rel_j2000_pos,
        vel_j2000_kms=rel_j2000_vel,
        pos_me_km=rel_me_pos,
        vel_me_kms=rel_me_vel,
        pos_enu_km=pos_enu,
        vel_enu_kms=vel_enu,
        azimuth_deg=az_deg,
        elevation_deg=el_deg,
        range_km=rng_km,
        range_rate_kms=range_rate_kms,
        lsk_sha256=kernel_hashes.get("lsk"),
        spk_sha256=kernel_hashes.get("spk"),
        pck_sha256=kernel_hashes.get("pck"),
        fk_sha256=kernel_hashes.get("fk"),
    )
