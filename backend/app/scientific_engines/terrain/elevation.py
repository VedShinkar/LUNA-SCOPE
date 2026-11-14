"""Elevation surface analysis and product generation.

Phase 2 Elevation module:
- Computes descriptive statistics and valid coverage over the lunar DEM.
- Analyzes hypsometric/elevation distributions.
- Exports georeferenced processed GeoTIFFs preserving source lunar CRS and transform.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import rasterio
from rasterio.transform import Affine

from app.scientific_engines.terrain.loader import TerrainRasterMetadata


def calculate_elevation_statistics(
    elevation: np.ndarray,
    nodata: Optional[float] = None,
    num_bins: int = 30,
) -> Dict[str, Any]:
    """Calculate comprehensive descriptive statistics and distribution for elevation.

    Args:
        elevation: 2D array of surface heights in metres.
        nodata: Optional nodata value to mask out.
        num_bins: Number of histogram bins for the hypsometric distribution.

    Returns:
        Dictionary of elevation statistics, coverage metrics, and distribution bins.
    """
    total_pixels = int(elevation.size)

    # Identify valid finite pixels
    if nodata is not None and not np.isnan(nodata):
        valid_mask = np.isfinite(elevation) & (elevation != nodata)
    else:
        valid_mask = np.isfinite(elevation)

    valid_count = int(valid_mask.sum())
    invalid_count = total_pixels - valid_count
    coverage_pct = float(valid_count / total_pixels * 100.0)

    if valid_count == 0:
        return {
            "total_pixels": total_pixels,
            "valid_pixels": 0,
            "invalid_pixels": total_pixels,
            "coverage_percentage": 0.0,
            "statistics": None,
            "distribution": None,
        }

    valid_vals = elevation[valid_mask].astype(np.float64)

    min_val = float(np.min(valid_vals))
    max_val = float(np.max(valid_vals))
    mean_val = float(np.mean(valid_vals))
    std_val = float(np.std(valid_vals, ddof=1)) if valid_count > 1 else 0.0
    median_val = float(np.median(valid_vals))

    # Percentiles
    p1, p5, p25, p75, p95, p99 = [
        float(x) for x in np.percentile(valid_vals, [1, 5, 25, 75, 95, 99])
    ]
    iqr = p75 - p25

    # Hypsometric distribution / histogram
    counts, bin_edges = np.histogram(valid_vals, bins=num_bins)
    histogram_bins = []
    for i in range(len(counts)):
        bin_start = float(bin_edges[i])
        bin_end = float(bin_edges[i + 1])
        cnt = int(counts[i])
        histogram_bins.append({
            "bin_index": i,
            "range_m": [round(bin_start, 2), round(bin_end, 2)],
            "pixel_count": cnt,
            "percentage": round(float(cnt / valid_count * 100.0), 4),
        })

    return {
        "total_pixels": total_pixels,
        "valid_pixels": valid_count,
        "invalid_pixels": invalid_count,
        "coverage_percentage": round(coverage_pct, 4),
        "statistics": {
            "minimum_m": round(min_val, 4),
            "maximum_m": round(max_val, 4),
            "range_m": round(max_val - min_val, 4),
            "mean_m": round(mean_val, 4),
            "std_dev_m": round(std_val, 4),
            "median_m": round(median_val, 4),
            "percentiles_m": {
                "p01": round(p1, 4),
                "p05": round(p5, 4),
                "p25": round(p25, 4),
                "p75": round(p75, 4),
                "p95": round(p95, 4),
                "p99": round(p99, 4),
            },
            "interquartile_range_m": round(iqr, 4),
        },
        "hypsometric_distribution": {
            "bin_count": num_bins,
            "bins": histogram_bins,
        },
    }


def write_geotiff(
    data: np.ndarray,
    meta: TerrainRasterMetadata,
    output_path: Path,
    nodata: float = np.nan,
    dtype: str = "float32",
    description: str = "",
) -> Path:
    """Save a 2D numpy array as a georeferenced GeoTIFF preserving source lunar metadata.

    Guarantees:
    - Verbatim lunar CRS WKT is written.
    - Exact affine transform, resolution, and bounds are preserved.
    - No terrestrial EPSG codes are assigned.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    height, width = data.shape

    out_arr = data.astype(dtype)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": dtype,
        "crs": rasterio.crs.CRS.from_wkt(meta.crs_wkt),
        "transform": Affine(*meta.transform),
        "nodata": nodata,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": min(256, width),
        "blockysize": min(256, height),
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(out_arr, 1)
        tags = {
            "AREA_OR_POINT": "Area",
            "DESCRIPTION": description,
            "LUNAR_REFERENCE_FRAME": "MOON_ME associated with DE421 ephemeris",
            "PROJECTION": "Lunar South-Polar Stereographic",
            "UNITS": "metre",
        }
        dst.update_tags(**tags)

    return output_path
