"""Display and measurement products for the lunar globe and polar approach."""
from functools import lru_cache
from pathlib import Path
import warnings

import numpy as np
from pyproj import Geod
import rasterio
from rasterio.errors import NotGeoreferencedWarning
from rasterio.windows import Window

from app.scientific_engines.terrain.explorer import ROOT, _band, _encode, _path, _quad_validity

RADIUS = 1_737_400.0
CACHE = ROOT / "cache" / "lunar-experience"
SVS = "https://svs.gsfc.nasa.gov/4720/"
PDS = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/"
GEOD = Geod(a=RADIUS, b=RADIUS)


def polar_xy(latitude, longitude):
    """Spherical south polar stereographic, true scale at the pole, east-positive."""
    rho = 2 * RADIUS * np.tan(np.radians(90 + latitude) / 2)
    angle = np.radians(longitude)
    return rho * np.sin(angle), rho * np.cos(angle)


def polar_lonlat(x, y):
    return float(np.degrees(np.arctan2(x, y))), float(2 * np.degrees(np.arctan(np.hypot(x, y) / (2 * RADIUS))) - 90)


def site04_context():
    with rasterio.open(_path(ROOT, "processed", "processed_elevation")) as source:
        x, y = source.transform @ (source.width / 2, source.height / 2)
        longitude, latitude = polar_lonlat(x, y)
        return {
            "longitude": longitude, "latitude": latitude, "easting": x, "northing": y,
            "bounds": list(source.bounds), "source_resolution_m": list(source.res),
        }


@lru_cache(maxsize=1)
def global_elevation():
    # The SVS visualization TIFF has no embedded CRS. Registration comes from
    # the documented, zero-centred global cylindrical export and its dimensions.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NotGeoreferencedWarning)
        with rasterio.open(CACHE / "ldem_4.tif") as source:
            values, valid = _band(source)
    if values.shape != (720, 1440) or not valid.all():
        raise ValueError("Unexpected global LOLA grid or missing elevations.")
    return (values * np.float32(1000)).astype("<f4")


def open_polar():
    source = rasterio.open(CACHE / "ldem_85s_40m.lbl")
    if (source.shape, source.res, source.scales, source.offsets, source.nodata) != (
        (7584, 7584), (40.0, 40.0), (0.5,), (RADIUS,), -32768.0
    ) or (CACHE / "ldem_85s_40m.img").stat().st_size != 115034112:
        source.close()
        raise ValueError("Unexpected LOLA PDS dimensions, scaling or NoData.")
    return source


@lru_cache(maxsize=2)
def regional_grid(detail: str):
    """Two bounded windows of the same native PDS product, at exact sample centres."""
    if detail not in ("overview", "approach"):
        raise ValueError("Unknown regional detail.")
    site = site04_context()
    # Square around the pole for context, then a finer square around the site.
    span, stride = (256_000, 16) if detail == "overview" else (48_000, 4)
    x, y = (0, 0) if detail == "overview" else (site["easting"], site["northing"])
    with open_polar() as source:
        col, row = (~source.transform) @ (x - span / 2, y + span / 2)
        length = int(span / source.res[0])
        window = Window(round(col), round(row), length, length)
        band = source.read(1, window=window, masked=True)
        valid = ~np.ma.getmaskarray(band)
        # PDS OFFSET is the radius datum, so only the 0.5 m scale applies to heights.
        offset = (stride - 1) // 2
        samples = np.arange(offset, length, stride)
        subset = np.ix_(samples, samples)
        transform = source.window_transform(window) @ rasterio.Affine.translation(
            offset + 0.5 - stride / 2, offset + 0.5 - stride / 2
        ) @ rasterio.Affine.scale(stride)
        return {
            "width": samples.size, "height": samples.size, "transform": list(transform)[:6],
            "resolution": [source.res[0] * stride, source.res[1] * stride],
            "source_resolution": list(source.res), "source_shape": list(source.shape),
            "source_transform": list(source.transform)[:6], "source_wkt": source.crs.to_wkt(),
            "source_nodata": source.nodata, "source": "NASA PDS LOLA LDEM_85S_40M V2.0",
            "source_url": PDS, "source_coverage": "85°S to 90°S",
            "registration": "pixel centre", "vertical_unit": "m", "radius_m": RADIUS,
            "sampling": "native-pixel decimation", "stride": stride,
            "elevation": _encode(band.data[subset].astype(np.float32) * source.scales[0], valid[subset], "m"),
            "quad_valid": _quad_validity(valid, samples, samples).ravel().tolist(),
        }


def _projected_samples(source, coordinates, scale=1):
    result = []
    for xy, values in zip(coordinates, source.sample(coordinates, masked=True)):
        row, col = source.index(*xy)
        value = values[0]
        valid = 0 <= row < source.height and 0 <= col < source.width
        result.append(float(value) * scale if valid and not np.ma.is_masked(value) and np.isfinite(value) else None)
    return result


def elevation_profile(start, end, level):
    """Return 128 samples along the short spherical geodesic in the selected source."""
    lon1, lat1 = start
    lon2, lat2 = end
    _, _, distance = GEOD.inv(lon1, lat1, lon2, lat2)
    coordinates = [start, *GEOD.npts(lon1, lat1, lon2, lat2, 126), end] if distance else [start] * 128
    if level == "moon":
        grid = global_elevation()
        values = [float(grid[min(719, int((90 - lat) * 4)), int(((lon + 180) % 360) * 4)])
                  for lon, lat in coordinates]
        source = "Global LOLA · 4 samples/degree"
    else:
        projected = [polar_xy(lat, lon) for lon, lat in coordinates]
        if level == "polar":
            with open_polar() as dataset:
                values = _projected_samples(dataset, projected, dataset.scales[0])
            values = [value if lat <= -85 else None for value, (_, lat) in zip(values, coordinates)]
            source = "Polar LOLA · 40 m"
        else:
            with rasterio.open(_path(ROOT, "processed", "processed_elevation")) as dataset:
                values = _projected_samples(dataset, projected)
            source = "Site04 LOLA · 5 m"
    return {"distance_m": distance, "elevation_m": values, "source": source, "sampling": "nearest native cell"}
