"""Validate and process configured NASA sites sequentially at native resolution."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np
import pyproj
import rasterio

from app.scientific_engines.terrain.catalog import get_site_config, verify_source_association
from app.scientific_engines.terrain.loader import load_site_dataset, require_compatible_grid
from app.scientific_engines.terrain.pipeline import run_phase2_terrain_pipeline, run_phase3_hazard_pipeline
from app.scientific_engines.terrain.service import TerrainService
from app.scientific_engines.terrain.validation import validate_site_rasters

METADATA = ROOT / "data/metadata/terrain"


def clean_json(value):
    if isinstance(value, dict):
        return {k: clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def save(path, value):
    path.write_text(json.dumps(clean_json(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def process(site):
    started = time.perf_counter()
    cfg = get_site_config(site)
    raw, processed = cfg["raw_dir"], cfg["processed_dir"]
    report = {
        "site_id": site, "site_name": cfg["name"], "identity_source_url": cfg["identity_source_url"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "processing_status": "NOT_PROCESSED",
        "configuration": {"native_grid": True, "resampling": False, "diagnostics": False,
                          "roughness_scales_m": [15, 35, 75], "hazard_slope_source": "NASA SLP"},
        "limitations": ["Provisional screening, not mission safety certification.",
                        "Slope agreement with NASA is not independent ground-truth validation.",
                        "Site04 original download time was not retained; no timestamp is fabricated.",
                        "Horizon retains Phase 4 interpolation and gap-skipping behavior; incomplete terrain can omit obstacles."],
    }
    try:
        previous_values = {}
        if site == "Site04":
            for path in processed.glob(f"{site}_*.tif"):
                with rasterio.open(path) as src:
                    previous_values[path.name] = hashlib.sha256(src.read(1).tobytes()).hexdigest()
        print(f"{site}: checking source association", flush=True)
        ds = load_site_dataset(raw, site)
        require_compatible_grid(ds)
        verify_source_association(ds, METADATA)
        manifest = json.loads((METADATA / "download_manifest.json").read_text(encoding="utf-8"))
        report["source_provenance"] = manifest["sites"][site]
        report["raster_metadata"] = {
            k: {**r.metadata.to_dict(), "units": cfg["rasters"][k]["units"],
                "source_url": cfg["rasters"][k]["url"]} for k, r in ds.rasters.items()
        }
        meta = ds.elevation.metadata
        crs = pyproj.CRS.from_wkt(meta.crs_wkt)
        transformer = pyproj.Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        report["geographic_bounds_lonlat_deg"] = transformer.transform_bounds(*meta.bounds, densify_pts=41)
        print(f"{site}: Phase 1", flush=True)
        p1 = validate_site_rasters(raw, site, METADATA / f"{site.lower()}_validation_report.json")
        report["validation"] = p1
        if not p1["phase1_gate_passed"]:
            raise ValueError(f"{site} failed Phase 1; processing stopped")
        print(f"{site}: Phase 2", flush=True)
        p2 = run_phase2_terrain_pipeline(raw, processed, METADATA, site, generate_diagnostics=False)
        print(f"{site}: Phase 3", flush=True)
        p3 = run_phase3_hazard_pipeline(raw, processed, METADATA, site, generate_diagnostics=False,
                                        reuse_phase2_roughness=True)
        report["terrain"] = p2
        report["hazards"] = p3
        checks = {}
        for path in sorted(processed.glob(f"{site}_*.tif")):
            with rasterio.open(path) as src:
                if (src.height, src.width, tuple(src.transform)[:6], src.crs.to_wkt()) != (
                    meta.height, meta.width, meta.transform, meta.crs_wkt
                ):
                    raise ValueError(f"Output grid mismatch: {path}")
                arr = src.read(1, masked=True).compressed()
                finite = arr[np.isfinite(arr)]
                if not finite.size:
                    raise ValueError(f"No valid output values: {path}")
                low, high = float(finite.min()), float(finite.max())
                if "slope_deg" in path.name and not 0 <= low <= high <= 90:
                    raise ValueError(f"Implausible slope: {path}")
                if "aspect_deg" in path.name and not -1 <= low <= high <= 360:
                    raise ValueError(f"Implausible aspect: {path}")
                if "roughness" in path.name and low < 0:
                    raise ValueError(f"Negative roughness: {path}")
                if src.dtypes[0] == "uint8" and not np.isin(finite, [0, 1, 2, 3]).all():
                    raise ValueError(f"Invalid hazard code: {path}")
                checks[path.name] = {"grid_preserved": True, "finite_pixels": int(finite.size),
                                     "minimum": low, "maximum": high}
                if path.name in previous_values:
                    checks[path.name]["matches_pre_phase5_values"] = (
                        hashlib.sha256(src.read(1).tobytes()).hexdigest() == previous_values[path.name]
                    )
        report["derived_validation"] = checks
        service = TerrainService(site_id=site)
        service._ensure_loaded()
        # Select a real finite cell nearest the grid centre.
        row, col = meta.height // 2, meta.width // 2
        if not np.isfinite(service._dem[row, col]):
            rows, cols = np.nonzero(np.isfinite(service._dem))
            index = np.argmin((rows - row) ** 2 + (cols - col) ** 2)
            row, col = int(rows[index]), int(cols[index])
        x, y = service._transform @ (col + 0.5, row + 0.5)
        report["point_check"] = service.query_point(x, y)
        report["horizon_check"] = service.query_horizon(x, y, azimuth_step_deg=45, max_range_m=500)
        if not report["point_check"]["is_valid"] or not report["horizon_check"]["is_valid"]:
            raise ValueError(f"{site}: point or horizon check failed")
        report["processing_status"] = "PROCESSED"
    except (OSError, ValueError, rasterio.errors.RasterioError) as error:
        report["processing_status"] = "FAILED"
        report["error"] = f"{type(error).__name__}: {error}"
        print(report["error"], flush=True)
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    save(METADATA / f"{site.lower()}_phase5_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sites", nargs="+", default=["Site04", "Site11", "Site23"])
    args = parser.parse_args()
    requested_reports = [process(site) for site in args.sites]
    reports = []
    for site in json.loads((METADATA / "dataset_catalog.json").read_text(encoding="utf-8"))["sites"]:
        path = METADATA / f"{site.lower()}_phase5_report.json"
        if path.exists():
            reports.append(json.loads(path.read_text(encoding="utf-8")))
    rows = []
    for report in reports:
        terrain, hazard = report.get("terrain", {}), report.get("hazards", {})
        rows.append({"site_id": report["site_id"], "site_name": report["site_name"],
                     "status": report["processing_status"], "error": report.get("error"),
                     "grid": terrain.get("georeferencing_and_crs"),
                     "elevation": terrain.get("elevation_summary"),
                     "slope_comparison": terrain.get("slope_analysis"),
                     "roughness": terrain.get("roughness_analysis"),
                     "observations": hazard.get("interpolation_and_observation_summary"),
                     "hazard_counts": hazard.get("combined_class_counts"),
                     "hazard_percentages": hazard.get("combined_class_percentages"),
                     "elapsed_seconds": report["elapsed_seconds"]})
    save(METADATA / "multisite_comparison.json", {
        "report_type": "Comparable whole-grid metrics; no mission safety ranking",
        "all_three_sites_processed": len(reports) == 3 and all(r["processing_status"] == "PROCESSED" for r in reports),
        "sites": rows,
    })
    return 0 if all(r["processing_status"] == "PROCESSED" for r in requested_reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
