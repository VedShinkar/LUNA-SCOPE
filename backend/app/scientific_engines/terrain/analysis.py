"""Native raster statistics and cross-sections for the terrain workspace."""
from functools import lru_cache
from math import ceil
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform

from .catalog import get_site_config
from .explorer import ROOT, LAYERS, _band, _path, _same_crs, site_elevation_path
from .lunar_context import GEOD, LUNAR_GEOGRAPHIC

SLOPE_BINS = [0, 5, 10, 15, 20, 30, 45, 90]


def raster_statistics(elevation, source, name, unit, threshold=None):
    count = direct = exceeds = 0
    total = 0.0
    low, high = np.inf, -np.inf
    histogram = np.zeros(len(SLOPE_BINS) - 1, dtype=np.int64)
    # Bounded row slabs also work for untiled or single-strip inputs.
    for row in range(0, source.height, 128):
        window = Window(0, row, source.width, min(128, source.height - row))
        values, valid = _band(source, window)
        if source is not elevation:
            valid &= _band(elevation, window)[1]
        selected = values[valid]
        if not selected.size:
            continue
        count += selected.size
        total += float(selected.sum(dtype=np.float64))
        low, high = min(low, float(selected.min())), max(high, float(selected.max()))
        if name == "coverage":
            direct += int(np.count_nonzero(selected > 0))
        if name == "slope":
            histogram += np.histogram(selected, SLOPE_BINS)[0]
        if threshold is not None:
            exceeds += int(np.count_nonzero(selected > threshold))
    cells = source.width * source.height
    result = {"file": Path(source.name).name, "unit": unit,
              "valid": int(count), "invalid": int(cells - count), "total": cells,
              "minimum": low if count else None, "maximum": high if count else None,
              "mean": total / count if count else None}
    if name == "coverage":
        result["direct"] = direct
        result["direct_percent"] = 100 * direct / count if count else None
    if name == "slope":
        result["histogram"] = {"edges": SLOPE_BINS, "counts": histogram.tolist(), "outside": int(count - histogram.sum())}
    if threshold is not None:
        result["screening"] = {"threshold": threshold, "within": int(count - exceeds), "exceeds": exceeds}
    return result


@lru_cache(maxsize=12)
def _statistics(site_id, name, elevation_path, path, elevation_stamp, stamp, threshold):
    config = get_site_config(site_id)
    stage, product, unit = LAYERS.get(name, ("processed", "processed_elevation", "m"))
    with rasterio.open(elevation_path) as elevation:
        if name == "elevation":
            result = raster_statistics(elevation, elevation, name, unit)
        else:
            with rasterio.open(path) as source:
                if (source.shape != elevation.shape or source.transform != elevation.transform or
                        not _same_crs(source.crs, elevation.crs)):
                    raise ValueError(f"{name} raster is not aligned to {site_id} elevation.")
                digest = elevation.tags().get("SOURCE_DEM_SHA256")
                if stage == "processed" and digest and source.tags().get("SOURCE_DEM_SHA256") != digest:
                    raise ValueError(f"{name} raster provenance does not match {site_id} elevation.")
                result = raster_statistics(elevation, source, name, unit, threshold)
        result.update(site_id=site_id, layer=name, bounds=list(elevation.bounds),
                      resolution=list(elevation.res), width=elevation.width, height=elevation.height,
                      source_url=config["rasters"][product if stage == "raw" else "elevation"]["url"],
                      source_kind="NASA raster" if stage == "raw" else "Processed LOLA raster")
        return result


def site_statistics(site_id, name, threshold=None):
    config = get_site_config(site_id)
    stage, product, _ = LAYERS.get(name, ("processed", "processed_elevation", "m"))
    elevation = site_elevation_path(site_id)
    path = _path(ROOT, stage, product, config)
    return _statistics(site_id, name, elevation, path, elevation.stat().st_mtime_ns, path.stat().st_mtime_ns, threshold)


def site_cross_section(site_id, vertices):
    """Sample native cells along piecewise spherical geodesics at no more than native spacing."""
    with rasterio.open(site_elevation_path(site_id)) as source:
        spacing = min(source.res)
        segments = []
        for start, end in zip(vertices, vertices[1:]):
            _, _, length = GEOD.inv(*start, *end)
            if length > 0:
                segments.append((start, end, length, ceil(length / spacing)))
        if sum(segment[3] for segment in segments) > 20000:
            raise ValueError("Path exceeds 20,000 native-spaced samples. Shorten the profile.")
        coordinates, distances = [vertices[0]], [0.0]
        for start, end, length, count in segments:
            coordinates.extend(GEOD.npts(*start, *end, count - 1) if count > 1 else [])
            coordinates.append(end)
            offset = distances[-1]
            distances.extend(offset + length * i / count for i in range(1, count + 1))
        xs, ys = transform(LUNAR_GEOGRAPHIC, source.crs, *zip(*coordinates))
        values, blocks = [], {}
        for x, y in zip(xs, ys):
            row, col = source.index(x, y)
            if not (0 <= row < source.height and 0 <= col < source.width):
                values.append(None)
                continue
            top, left = row // 64 * 64, col // 64 * 64
            if (top, left) not in blocks:
                # Limit the working set while retaining locality along adjacent samples.
                if len(blocks) >= 64:
                    blocks.pop(next(iter(blocks)))
                blocks[top, left] = _band(source, Window(left, top, min(64, source.width-left), min(64, source.height-top)))
            block, valid = blocks[top, left]
            i, j = row-top, col-left
            values.append(float(block[i, j]) if valid[i, j] else None)
        return {"distance_m": distances[-1], "distance_along_m": distances, "elevation_m": values,
                "coordinates": [{"longitude": lon, "latitude": lat} for lon, lat in coordinates],
                "projected": [{"easting": x, "northing": y} for x, y in zip(xs, ys)],
                "source": f"{site_id} LOLA", "source_file": site_elevation_path(site_id).name,
                "source_url": get_site_config(site_id)["rasters"]["elevation"]["url"],
                "sampling": "Native cell lookup along spherical geodesic segments; no interpolation",
                "max_interval_m": spacing}
