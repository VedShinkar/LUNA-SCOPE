#!/usr/bin/env python3
"""Inspect downloaded LOLA rasters and verify that co-registered layers align."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import rasterio

SUFFIXES = {
    "elevation": "_final_adj_5mpp_surf.tif",
    "observation_count": "_final_adj_5mpp_ldec.tif",
    "slope": "_final_adj_5mpp_slp.tif",
    "elevation_uncertainty": "_final_adj_5mpp_toterr.tif",
    "slope_uncertainty": "_final_adj_5mpp_slperr.tif",
}


def inspect(path: Path) -> dict:
    with rasterio.open(path) as src:
        arr = src.read(1, masked=True)
        valid = arr.compressed()
        if valid.size == 0:
            stats = {"valid_pixels": 0}
        else:
            stats = {
                "valid_pixels": int(valid.size),
                "minimum": float(np.min(valid)),
                "maximum": float(np.max(valid)),
                "mean": float(np.mean(valid)),
                "standard_deviation": float(np.std(valid)),
            }
        return {
            "file": path.name,
            "crs": str(src.crs),
            "width_pixels": src.width,
            "height_pixels": src.height,
            "pixel_size_map_units": list(src.res),
            "bounds": list(src.bounds),
            "transform": list(src.transform)[:6],
            "nodata": src.nodata,
            "band_count": src.count,
            "dtype": src.dtypes[0],
            **stats,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=["Site04", "Site11", "Site23"], default="Site04")
    args = parser.parse_args()
    site_dir = Path("data/raw/terrain") / args.site.lower()
    results = {}
    reference = None
    for key, suffix in SUFFIXES.items():
        path = site_dir / (args.site + suffix)
        if not path.exists():
            print(f"MISSING: {path}")
            continue
        info = inspect(path)
        results[key] = info
        grid = (info["crs"], info["width_pixels"], info["height_pixels"],
                tuple(info["transform"]))
        if reference is None:
            reference = grid
            info["grid_matches_elevation"] = True
        else:
            info["grid_matches_elevation"] = grid == reference

    output = {
        "site": args.site,
        "site_directory": str(site_dir),
        "inspection": results,
        "warning": "Check lunar CRS, datum, units and pixel registration against the exact PGDA product README before coordinate transformations or combining rasters."
    }
    out_path = Path("data/metadata/terrain") / f"{args.site.lower()}_inspection.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    print(f"\\nSaved: {out_path}")


if __name__ == "__main__":
    main()
