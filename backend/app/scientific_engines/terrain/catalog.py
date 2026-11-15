"""Repository catalog paths and source association checks for terrain sites."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = ROOT / "data/metadata/terrain/dataset_catalog.json"


class UnknownSiteError(ValueError):
    pass


def list_site_ids(catalog_path: Path = CATALOG_PATH) -> tuple[str, ...]:
    return tuple(json.loads(catalog_path.read_text(encoding="utf-8"))["sites"])


def get_site_config(site_id: str, catalog_path: Path = CATALOG_PATH) -> dict:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if site_id not in catalog["sites"]:
        raise UnknownSiteError(f"Unknown terrain site: {site_id}")
    entry = dict(catalog["sites"][site_id])
    entry["site_id"] = site_id
    entry["raw_dir"] = ROOT / entry["directory"]
    entry["processed_dir"] = ROOT / entry.get("processed_directory", f"data/processed/terrain/{site_id.lower()}")
    return entry


def verify_source_association(dataset, metadata_dir: Path) -> None:
    """Match every source byte stream against the acquisition registry."""
    manifest_path = metadata_dir / "download_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Source provenance unavailable: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    products = manifest.get("sites", {}).get(dataset.site_id, {}).get("products", {})
    for key, raster in dataset.rasters.items():
        record = products.get(key, {})
        if record.get("sha256") != raster.metadata.sha256_hash:
            raise ValueError(f"Source checksum/site-layer association failed: {dataset.site_id}/{key}")
        url = record.get("url")
        if url and not url.endswith(f"/{dataset.site_id}/{raster.metadata.file_name}"):
            raise ValueError(f"Source URL/site-layer association failed: {dataset.site_id}/{key}")
