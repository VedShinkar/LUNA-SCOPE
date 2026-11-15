"""Native LOLA data and Phase 3.1 solar geometry for terrain illumination."""
from collections import OrderedDict
from dataclasses import asdict, dataclass, field, replace
from functools import lru_cache
from threading import Lock

import numpy as np
import rasterio
from rasterio.transform import Affine

from app.scientific_engines.ephemeris.geometry import CONVENTIONS, MAX_SAMPLES, InvalidEpoch, covered_et, epochs, geometry_at
from app.scientific_engines.ephemeris.kernels import inventory
from app.scientific_engines.ephemeris.observer import Observer, ObserverUnavailable, UnsupportedObserver
from app.scientific_engines.terrain.catalog import get_site_config
from app.scientific_engines.terrain.explorer import ROOT, _band, _path, _same_crs, site_elevation_path
from app.scientific_engines.terrain.lunar_context import RADIUS, polar_lonlat
from .ray import CEILING_M, GRAZE_DEG, TRACE_M, trace

MAX_REGION_SIDE = 16
MAX_REGION_EPOCHS = 6
MAX_REGION_RAYS = 768
SEMANTICS = {
    "illuminated": "Solar centre clears known terrain and reaches the adopted radial ceiling within covered terrain, or lies at zenith.",
    "shadowed": "Solar centre is below the cell's geometric horizontal or blocked by known native terrain.",
    "unknown": "No definitive centre-ray classification because of terrain coverage, missing terrain, or a grazing ray.",
    "invalid": "Observer cell has no valid native elevation.",
    "clear": "Solar centre clears sampled terrain within the native raster; missing terrain beyond it can still obstruct the Sun.",
}
PROJECTION = {"proj": "stere", "lat_0": -90, "lat_ts": -90, "lon_0": 0,
              "x_0": 0, "y_0": 0, "R": RADIUS, "units": "m"}


@dataclass(eq=False, frozen=True)
class Terrain:
    dem: np.ndarray
    rms: np.ndarray | None
    transform: Affine
    inverse: Affine
    reference: Observer
    resolution: tuple[float, float]
    bounds: tuple[float, float, float, float]
    rms_source_url: str | None
    samples: OrderedDict = field(default_factory=OrderedDict)
    lock: Lock = field(default_factory=Lock)

    def cell_observer(self, row, col):
        x, y = self.transform @ (col + 0.5, row + 0.5)
        longitude, latitude = polar_lonlat(x, y)
        return replace(self.reference, easting_m=x, northing_m=y, latitude_deg=latitude,
                       longitude_deg_east=longitude, elevation_m=float(self.dem[row, col]),
                       source_pixel_row=row, source_pixel_column=col, placement="native pixel centre")

    def point_cell(self, point):
        if point is None:
            return self.dem.shape[0]//2, self.dem.shape[1]//2
        col, row = map(int, np.floor(self.inverse @ point))
        if not (0 <= row < self.dem.shape[0] and 0 <= col < self.dem.shape[1]):
            raise UnsupportedObserver(f"Observer location lies outside the {self.reference.site_id} terrain raster.")
        return row, col


def _read_band(source):
    data, valid = _band(source)
    result = np.where(valid, data.astype(np.float32, copy=False), np.nan)
    result.setflags(write=False)
    return result


@lru_cache(maxsize=1)
def _load(site_id, elevation_path, elevation_stamp, rms_path, rms_stamp):
    config = get_site_config(site_id)
    try:
        with rasterio.open(elevation_path) as source:
            definition = source.crs.to_dict() if source.crs else {}
            tags = source.tags()
            if (any(definition.get(k) != v for k, v in PROJECTION.items()) or
                    tags.get("LUNAR_REFERENCE_FRAME") != "MOON_ME associated with DE421 ephemeris" or
                    tags.get("UNITS") != "metre" or not tags.get("SOURCE_DEM_SHA256") or
                    source.scales != (1.0,) or source.offsets != (0.0,) or
                    source.width * source.height > 18_000_000 or
                    np.hypot(source.bounds.right-source.bounds.left, source.bounds.top-source.bounds.bottom) >= TRACE_M):
                raise ObserverUnavailable(f"{site_id} elevation does not match the supported native terrain model.")
            dem = _read_band(source)
            if not np.isfinite(dem).any() or np.nanmax(dem) >= CEILING_M or np.nanmin(dem) <= -RADIUS:
                raise ObserverUnavailable(f"{site_id} elevation is incompatible with the lunar radial envelope.")
            rms = None
            if rms_stamp is not None:
                try:
                    with rasterio.open(rms_path) as uncertainty:
                        if (uncertainty.shape == source.shape and uncertainty.transform == source.transform and
                                _same_crs(uncertainty.crs, source.crs) and
                                uncertainty.scales == (1.0,) and uncertainty.offsets == (0.0,)):
                            data = _read_band(uncertainty)
                            if np.isfinite(data).any() and np.nanmin(data) >= 0:
                                rms = data
                except (OSError, rasterio.errors.RasterioIOError):
                    pass  # RMS is optional; provenance and per-ray sensitivity expose its absence.
            # A reference contains only shared site/provenance fields. Each request
            # fills in coordinates and height at the validated native pixel.
            reference = Observer(site_id, 0, 0, 0, 0, 0, 0, 0, config["rasters"]["elevation"]["url"],
                                 elevation_path.name, tags["SOURCE_DEM_SHA256"], "native pixel centre")
            return Terrain(dem, rms, source.transform, ~source.transform, reference, source.res, tuple(source.bounds),
                           config["rasters"]["elevation_uncertainty"]["url"] if rms is not None else None)
    except (OSError, rasterio.errors.RasterioIOError) as exc:
        raise ObserverUnavailable(f"Native LOLA terrain is unavailable for {site_id}.") from exc


def load_terrain(site_id):
    config = get_site_config(site_id)
    path = site_elevation_path(site_id)
    rms = _path(ROOT, "raw", "elevation_uncertainty", config)
    try:
        stamp = path.stat().st_mtime_ns
    except OSError as exc:
        raise ObserverUnavailable(f"Native LOLA terrain is unavailable for {site_id}.") from exc
    return _load(site_id, path, stamp, rms, rms.stat().st_mtime_ns if rms.is_file() else None)


def provenance(terrain):
    observer = terrain.reference
    return {
        "site_id": observer.site_id,
        "terrain": {"file": observer.source_file, "source_url": observer.source_url,
                    "source_dem_sha256": observer.source_dem_sha256, "resolution_m": terrain.resolution,
                    "datum": observer.datum, "frame": observer.source_frame, "bounds_m": terrain.bounds,
                    "affine": list(terrain.transform)[:6], "shape": terrain.dem.shape,
                    "rms_source_url": terrain.rms_source_url},
        "celestial": {"source": "Phase 3.1 JPL DE440s", "conventions": CONVENTIONS, "kernels": inventory()},
        "method": {"name": "Great-circle native LOLA radial-cell solar centre ray", "grazing_tolerance_deg": GRAZE_DEG,
                   "radial_ceiling_m": CEILING_M, "maximum_trace_distance_m": TRACE_M,
                   "solar_disc": "Solar angular radius reported; centre ray only.",
                   "rms": "Opposite ±1 RMS height scenarios; sensitivity indicator, not confidence bounds."},
        "classification": SEMANTICS,
        "quality_flags": ["finite_terrain_extent", "solar_centre_only", "native_raster_model", "earth_occultation_not_modelled",
                          "rms_sensitivity_only" if terrain.rms is not None else "elevation_rms_unavailable"],
    }


def sample(terrain, observer, time):
    key = (observer.source_pixel_row, observer.source_pixel_column, time)
    with terrain.lock:
        cached = terrain.samples.get(key)
        if cached is not None:
            terrain.samples.move_to_end(key)
            return cached
    epoch = geometry_at(observer, time)
    result = {"utc": epoch["utc"], **trace(terrain, observer, epoch["sun"])}
    with terrain.lock:
        terrain.samples[key] = result
        if len(terrain.samples) > 2048:
            terrain.samples.popitem(last=False)
    return result


def epochs_with_end(start, end, step):
    values = epochs(start, end, step)
    if values[-1] != end:
        if len(values) == MAX_SAMPLES:
            raise InvalidEpoch(f"Time series exceeds {MAX_SAMPLES} samples including its endpoint.")
        values.append(end)
    return values


def classify_counts(states):
    counts = {state: states.count(state) for state in ("illuminated", "shadowed", "unknown", "invalid")}
    counts["valid_cells"] = len(states) - counts["invalid"]
    counts["classified"] = counts["illuminated"] + counts["shadowed"]
    return counts


def _utc(time):
    return time.isoformat().replace("+00:00", "Z")


def summarize(times, values, native=False):
    runs, transitions = [], []
    states = [sample["native_state" if native else "state"] for sample in values]
    clear = "clear" if native else "illuminated"
    totals = {clear: 0.0, "shadowed": 0.0, "unknown": 0.0}
    for start, end, before, after in zip(times, times[1:], states, states[1:]):
        duration = (end-start).total_seconds()
        if before != after and "unknown" not in (before, after):
            transitions.append({"start_utc": _utc(start), "end_utc": _utc(end), "from": before, "to": after})
        state = before if before == after else "unknown"
        totals[state] += duration
        if runs and runs[-1]["state"] == state:
            runs[-1]["end_utc"] = _utc(end)
            runs[-1]["duration_s"] += duration
        else:
            runs.append({"state": state, "start_utc": _utc(start), "end_utc": _utc(end), "duration_s": duration})
    known = totals[clear] + totals["shadowed"]
    gaps = []
    first_shadow = None
    for index, state in enumerate(states):
        if state == "shadowed":
            if first_shadow is None:
                first_shadow = index
            continue
        if first_shadow is not None and first_shadow > 0 and states[first_shadow-1] == state == clear:
            gaps.append({"first_shadow_utc": _utc(times[first_shadow]), "last_shadow_utc": _utc(times[index-1]),
                         "duration_s": (times[index-1]-times[first_shadow]).total_seconds(),
                         "bracket_s": (times[index]-times[first_shadow-1]).total_seconds()})
        first_shadow = None
    return {
        "duration_s": totals,
        "longest_clear_s": max((run["duration_s"] for run in runs if run["state"] == clear), default=0),
        "longest_shadow_s": max((run["duration_s"] for run in runs if run["state"] == "shadowed"), default=0),
        "fraction_known_time_clear": totals[clear]/known if known else None,
        "transitions": transitions, "gap_count": len(gaps), "gaps": gaps, "intervals": runs,
    }


def observer_analysis(site_id, point, times):
    covered_et(times[0])
    covered_et(times[-1])
    terrain = load_terrain(site_id)
    row, col = terrain.point_cell(point)
    if not np.isfinite(terrain.dem[row, col]):
        raise UnsupportedObserver(f"The selected {site_id} observer cell has no valid native elevation.")
    observer = terrain.cell_observer(row, col)
    values = [sample(terrain, observer, time) for time in times]
    counts = classify_counts([value["state"] for value in values])
    counts["valid_samples"] = counts.pop("valid_cells")
    return {**provenance(terrain), "observer": asdict(observer), "requested_point_m": point, "samples": values,
            "counts": counts,
            "summary": summarize(times, values), "native_summary": summarize(times, values, native=True)}


def region_analysis(site_id, point, side, times):
    if side < 2 or side > MAX_REGION_SIDE or len(times) > MAX_REGION_EPOCHS or side*side*len(times) > MAX_REGION_RAYS:
        raise ValueError(f"Region limit is {MAX_REGION_SIDE} cells per side, {MAX_REGION_EPOCHS} epochs and {MAX_REGION_RAYS} rays.")
    covered_et(times[0])
    covered_et(times[-1])
    terrain = load_terrain(site_id)
    left, top, affine, observers = native_region(terrain, point, side)
    frames = []
    for timestamp in times:
        results = [sample(terrain, observer, timestamp) if observer else None for observer in observers]
        states = [item["state"] if item else "invalid" for item in results]
        native = [item["native_state"] if item else "invalid" for item in results]
        counts = classify_counts(states)
        frames.append({"utc": _utc(timestamp), "states": states, "native_states": native, "counts": counts,
                       "native_clear": native.count("clear"), "rms_sensitive": sum(item["rms_sensitive"] is True for item in results if item),
                       "lit_percent_of_valid_cells": 100*counts["illuminated"]/counts["valid_cells"] if counts["valid_cells"] else None,
                       "lit_percent_of_classified_cells": 100*counts["illuminated"]/counts["classified"] if counts["classified"] else None})
    return {**provenance(terrain), "region": {"left": left, "top": top, "width": side, "height": side,
                                             "affine": list(affine)[:6], "requested_point_m": point,
                                             "elevation_m": [observer.elevation_m if observer else None for observer in observers]},
            "frames": frames}


def native_region(terrain, point, side):
    """Place an inward-shifted native window and resolve its valid pixel centres."""
    row, col = terrain.point_cell(point)
    height, width = terrain.dem.shape
    if min(height, width) < side:
        raise ValueError("Requested region is larger than the native grid.")
    top = min(max(row - side//2, 0), height-side)
    left = min(max(col - side//2, 0), width-side)
    observers = [terrain.cell_observer(r, c) if np.isfinite(terrain.dem[r, c]) else None
                 for r in range(top, top+side) for c in range(left, left+side)]
    affine = terrain.transform @ Affine.translation(left, top)
    return left, top, affine, observers
