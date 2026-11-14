#!/usr/bin/env python3
"""
Download NASA PGDA LOLA south-pole terrain products for LUNA-SCOPE.

Default: core five GeoTIFF products for Site04 (Shackleton), Site11
(de Gerlache rim), and Site23 (Malapert Massif), plus ROI archives where
NASA lists them.

Optional large products:
  --include-point-clouds  downloads per-site XYZI point clouds
  --include-clones        downloads the 100 DEM error-realisation clones
                          for each selected site (potentially very large)

Only Python's standard library is required.
Run from the repository root:
  python scripts/download_lola_terrain.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp"
SITES = {
    "Site04": {"name": "Shackleton rim", "roi": True},
    "Site11": {"name": "de Gerlache rim", "roi": True},
    "Site23": {"name": "Malapert massif", "roi": False},
}
RASTER_SUFFIXES = {
    "elevation": "_final_adj_5mpp_surf.tif",
    "observation_count": "_final_adj_5mpp_ldec.tif",
    "slope": "_final_adj_5mpp_slp.tif",
    "elevation_uncertainty": "_final_adj_5mpp_toterr.tif",
    "slope_uncertainty": "_final_adj_5mpp_slperr.tif",
}
TIFF_HEADERS = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
USER_AGENT = "LUNA-SCOPE-data-acquisition/1.0 (research project; contact via repository)"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_tiff(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(4) in TIFF_HEADERS


def download(url: str, destination: Path, expected: str) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")

    if destination.exists():
        valid = is_tiff(destination) if expected == "tiff" else (
            (lambda f: f.read(2) == b"\x1f\x8b")(destination.open("rb")) if expected == "gzip" else destination.stat().st_size > 0
        )
        if valid:
            print(f"Already present: {destination}")
            return {"status": "already_present", "path": str(destination), "bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination)}
        destination.unlink()

    last_error = None
    for attempt in range(1, 4):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                status = getattr(response, "status", response.getcode())
                if offset and status != 206:
                    # Server ignored Range; restart cleanly instead of corrupting the file.
                    offset = 0
                    mode = "wb"
                else:
                    mode = "ab" if offset else "wb"

                content_type = response.headers.get("Content-Type", "")
                with partial.open(mode) as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)

            if expected == "tiff" and not is_tiff(partial):
                sample = partial.read_bytes()[:300].decode("utf-8", errors="replace")
                raise RuntimeError(f"Response is not a TIFF (possible HTML/error page). First bytes: {sample!r}")
            if expected == "gzip" and (lambda f: f.read(2) != b"\x1f\x8b")(partial.open("rb")):
                raise RuntimeError("Response is not a gzip archive.")
            if partial.stat().st_size < 1024:
                raise RuntimeError(f"Downloaded file is unexpectedly small: {partial.stat().st_size} bytes")

            partial.replace(destination)
            return {"status": "downloaded", "path": str(destination), "url": url,
                    "downloaded_utc": datetime.now(timezone.utc).isoformat(),
                    "bytes": destination.stat().st_size, "sha256": sha256_file(destination),
                    "content_type": content_type}
        except Exception as exc:
            last_error = exc
            print(f"Attempt {attempt}/3 failed for {url}: {exc}", file=sys.stderr)
            if attempt < 3:
                time.sleep(attempt * 2)

    raise RuntimeError(f"Could not download {url}: {last_error}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Download LOLA terrain products from NASA PGDA.")
    parser.add_argument("--sites", nargs="+", choices=sorted(SITES), default=["Site04", "Site11", "Site23"],
                        help="PGDA site codes (default: all three LUNA-SCOPE comparison regions)")
    parser.add_argument("--include-point-clouds", action="store_true",
                        help="Also download large XYZI point-cloud files.")
    parser.add_argument("--include-clones", action="store_true",
                        help="Also download all 100 error-realisation DEM clones per site (large download).")
    parser.add_argument("--skip-roi", action="store_true",
                        help="Skip ROI GIS shapefile archives.")
    args = parser.parse_args()

    repo = Path.cwd()
    if not (repo / "README.md").exists() or not (repo / "data").exists():
        print("Run this script from the LUNA-SCOPE repository root (README.md and data/ must be present).",
              file=sys.stderr)
        return 2

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "NASA GSFC Planetary Geodesy Data Archive, LOLA South Pole Landing Site DEMs",
        "source_product_page": "https://pgda.gsfc.nasa.gov/products/78",
        "archive_index": "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/",
        "evidence_class": "NASA source-derived products",
        "sites": {},
        "notes": [
            "5 m/pixel is raster pixel spacing, not independent measurement spacing.",
            "LOLA polar LDEMs contain interpolated pixels; consult LDEC and uncertainty layers.",
            "Original downloads are preserved under data/raw/terrain and should not be edited.",
            "Computed SHA-256 values identify the exact local files downloaded."
        ]
    }

    failures = []
    for site in args.sites:
        info = SITES[site]
        site_dir = repo / "data" / "raw" / "terrain" / site.lower()
        print(f"\\n=== {site}: {info['name']} ===")
        site_manifest = {"site_name": info["name"], "products": {}}

        for product, suffix in RASTER_SUFFIXES.items():
            filename = site + suffix
            url = f"{BASE_URL}/{site}/{filename}"
            try:
                result = download(url, site_dir / filename, "tiff")
                site_manifest["products"][product] = result
            except Exception as exc:
                failures.append(f"{site} {product}: {exc}")
                site_manifest["products"][product] = {"status": "failed", "url": url, "error": str(exc)}

        if not args.skip_roi and info["roi"]:
            filename = f"{site}_ROIs.tgz"
            url = f"{BASE_URL}/{site}/{filename}"
            try:
                site_manifest["products"]["regions_of_interest"] = download(url, site_dir / filename, "gzip")
            except Exception as exc:
                # ROI is useful ancillary data but not required for the first DEM workflow.
                print(f"Optional ROI archive unavailable for {site}: {exc}", file=sys.stderr)
                site_manifest["products"]["regions_of_interest"] = {"status": "not_downloaded", "url": url,
                                                                      "reason": str(exc)}
        elif not info["roi"]:
            site_manifest["products"]["regions_of_interest"] = {
                "status": "not_listed_for_site",
                "reason": "The PGDA Product 78 page does not list a Site23 ROI archive."
            }

        if args.include_point_clouds:
            filename = f"{site}_final_adj.xyzi"
            url = f"{BASE_URL}/{site}/{filename}"
            try:
                site_manifest["products"]["point_cloud"] = download(url, site_dir / filename, "binary")
            except Exception as exc:
                failures.append(f"{site} point cloud: {exc}")
                site_manifest["products"]["point_cloud"] = {"status": "failed", "url": url, "error": str(exc)}

        if args.include_clones:
            clone_dir = site_dir / "clones"
            clone_results = []
            for index in range(1, 101):
                filename = f"{site}_final_adj_5mpp_{index:04d}_err.tif"
                url = f"{BASE_URL}/{site}/Clones/{filename}"
                try:
                    clone_results.append(download(url, clone_dir / filename, "tiff"))
                except Exception as exc:
                    failures.append(f"{site} clone {index:04d}: {exc}")
                    clone_results.append({"status": "failed", "url": url, "error": str(exc)})
            site_manifest["products"]["error_realisation_clones"] = clone_results

        manifest["sites"][site] = site_manifest

    metadata_dir = repo / "data" / "metadata" / "terrain"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = metadata_dir / "download_manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        for site, entry in previous.get("sites", {}).items():
            if site not in manifest["sites"]:
                manifest["sites"][site] = entry
            else:
                for key, product in manifest["sites"][site]["products"].items():
                    old = entry.get("products", {}).get(key, {})
                    if product.get("status") == "already_present" and old.get("sha256") == product.get("sha256"):
                        product.update({k: v for k, v in old.items() if k not in product})
        manifest["previous_created_utc"] = previous.get("created_utc")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\\nManifest written to: {manifest_path}")
    if failures:
        print("\\nSome downloads failed:")
        for failure in failures:
            print(" -", failure)
        print("\\nRe-run the same command to retry; completed files are skipped.")
        return 1

    print("\\nRequested core downloads completed.")
    print("Next: python scripts/inspect_lola_site.py --site Site04")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
