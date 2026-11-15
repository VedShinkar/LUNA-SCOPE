"""LOLA surface observers and east/north/up transformations."""
from dataclasses import dataclass
from functools import lru_cache
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

from app.scientific_engines.terrain.catalog import get_site_config
from app.scientific_engines.terrain.explorer import ROOT, _band, site_elevation_path
from app.scientific_engines.terrain.lunar_context import LUNAR_GEOGRAPHIC, RADIUS

DATUM = "Radial height above the LOLA 1,737,400 m reference sphere"
SOURCE_FRAME = "MOON_ME (DE421)"


class UnsupportedObserver(ValueError):
    pass


class ObserverUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Observer:
    site_id: str
    latitude_deg: float
    longitude_deg_east: float
    elevation_m: float
    easting_m: float
    northing_m: float
    source_pixel_row: int
    source_pixel_column: int
    source_url: str
    source_file: str
    source_dem_sha256: str
    placement: str
    datum: str = DATUM
    source_frame: str = SOURCE_FRAME


def local_basis(latitude_deg, longitude_deg_east):
    """Rows of the orthonormal transformation from body-fixed XYZ to ENU."""
    lat, lon = radians(latitude_deg), radians(longitude_deg_east)
    return np.array([
        [-sin(lon), cos(lon), 0],
        [-sin(lat) * cos(lon), -sin(lat) * sin(lon), cos(lat)],
        [cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat)],
    ])


def azimuth_elevation(enu):
    east, north, up = enu
    horizontal = hypot(east, north)
    return (degrees(atan2(east, north)) % 360 if horizontal > 1e-14 else None,
            degrees(atan2(up, horizontal)))


@lru_cache(maxsize=128)
def _observe(site_id, source_path, stamp, point):
    config = get_site_config(site_id)
    with rasterio.open(source_path) as source:
        tags = source.tags()
        if (not source.crs or source.crs.to_dict().get("R") != RADIUS or
                tags.get("LUNAR_REFERENCE_FRAME") != "MOON_ME associated with DE421 ephemeris" or
                tags.get("UNITS") != "metre" or not tags.get("SOURCE_DEM_SHA256")):
            raise ObserverUnavailable(f"Observer datum or raster provenance is unverified for {site_id}.")
        x, y = point if point is not None else source.transform @ (source.width / 2, source.height / 2)
        row, col = source.index(x, y)
        if not (0 <= row < source.height and 0 <= col < source.width):
            raise UnsupportedObserver(f"Observer point lies outside the {site_id} raster.")
        values, valid = _band(source, Window(col, row, 1, 1))
        if not valid[0, 0]:
            raise UnsupportedObserver(f"Observer point has no valid {site_id} LOLA elevation.")
        lon, lat = transform(source.crs, LUNAR_GEOGRAPHIC, [x], [y])
        return Observer(site_id, lat[0], lon[0], float(values[0, 0]), x, y, row, col,
                        config["rasters"]["elevation"]["url"], Path(source.name).name,
                        tags["SOURCE_DEM_SHA256"], "terrain point" if point is not None else "raster centre")


def resolve_observer(site_id, point=None):
    get_site_config(site_id)
    try:
        path = site_elevation_path(site_id)
        return _observe(site_id, path, path.stat().st_mtime_ns, point)
    except (OSError, rasterio.errors.RasterioIOError) as exc:
        raise ObserverUnavailable(f"Validated LOLA observer elevation is unavailable for {site_id}.") from exc
