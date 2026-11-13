#!/usr/bin/env python3
"""Inspect downloaded LOLA rasters and verify that co-registered layers align."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import rasterio

# Ensure backend package is in python search path
repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.scientific_engines.terrain.loader import LOLA_CORE_PRODUCTS
from app.scientific_engines.terrain.validation import validate_site_rasters

SUFFIXES = LOLA_CORE_PRODUCTS


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
    parser = argparse.ArgumentParser(description="Inspect and validate LOLA terrain rasters.")
    parser.add_argument("--site", choices=["Site04", "Site11", "Site23"], default="Site04")
    parser.add_argument("--no-validate", action="store_false", dest="validate", default=True,
                        help="Skip Phase 1 scientific validation and report generation")
    args = parser.parse_args()
    site_dir = Path("data/raw/terrain") / args.site.lower()
    results = {}
    reference = None
    all_present = True

    for key, suffix in SUFFIXES.items():
        path = site_dir / (args.site + suffix)
        if not path.exists():
            print(f"MISSING: {path}")
            all_present = False
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
    print(f"Saved inspection: {out_path}")

    if args.validate and all_present:
        validation_report_path = Path("data/metadata/terrain") / f"{args.site.lower()}_validation_report.json"
        report = validate_site_rasters(
            site_dir=site_dir,
            site=args.site,
            output_report_path=validation_report_path,
        )
        print(f"Phase 1 Gate Status: {report['status']} (Passed: {report['phase1_gate_passed']})")
        print(f"Saved validation report: {validation_report_path}")


if __name__ == "__main__":
    main()
