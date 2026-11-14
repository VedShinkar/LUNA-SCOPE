"""Terrain raster loader for NASA LOLA GeoTIFF products.

Handles robust loading, TIFF header verification, complete-read integrity
checks, metadata extraction, and dataset grouping for lunar landing sites.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pyproj
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

TIFF_MAGIC_HEADERS = (
    b"II*\x00",  # Little-endian classic TIFF
    b"MM\x00*",  # Big-endian classic TIFF
    b"II+\x00",  # Little-endian BigTIFF
    b"MM\x00+",  # Big-endian BigTIFF
)

LOLA_CORE_PRODUCTS = {
    "elevation": "_final_adj_5mpp_surf.tif",
    "observation_count": "_final_adj_5mpp_ldec.tif",
    "slope": "_final_adj_5mpp_slp.tif",
    "elevation_uncertainty": "_final_adj_5mpp_toterr.tif",
    "slope_uncertainty": "_final_adj_5mpp_slperr.tif",
}


@dataclass(frozen=True)
class TerrainRasterMetadata:
    """Metadata container for a single lunar terrain GeoTIFF."""
    file_name: str
    file_path: str
    file_size_bytes: int
    sha256_hash: str
    is_valid_tiff_header: bool
    width: int
    height: int
    band_count: int
    dtype: str
    nodata: Optional[float]
    crs_wkt: str
    crs_proj4: str
    is_lunar_crs: bool
    is_terrestrial_epsg: bool
    epsg_code: Optional[int]
    transform: Tuple[float, float, float, float, float, float]
    resolution: Tuple[float, float]
    bounds: Tuple[float, float, float, float]  # (left, bottom, right, top)
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to JSON-serializable dictionary."""
        d = asdict(self)
        d["transform"] = list(self.transform)
        d["bounds"] = list(self.bounds)
        d["resolution"] = list(self.resolution)
        return d


@dataclass
class TerrainRaster:
    """Holds a terrain raster array alongside its extracted metadata."""
    key: str
    metadata: TerrainRasterMetadata
    data: Optional[np.ndarray] = None


@dataclass
class SiteTerrainDataset:
    """Container for the complete five-raster LOLA site suite."""
    site_id: str
    site_dir: Path
    rasters: Dict[str, TerrainRaster] = field(default_factory=dict)

    @property
    def elevation(self) -> Optional[TerrainRaster]:
        return self.rasters.get("elevation")

    @property
    def observation_count(self) -> Optional[TerrainRaster]:
        return self.rasters.get("observation_count")

    @property
    def slope(self) -> Optional[TerrainRaster]:
        return self.rasters.get("slope")

    @property
    def elevation_uncertainty(self) -> Optional[TerrainRaster]:
        return self.rasters.get("elevation_uncertainty")

    @property
    def slope_uncertainty(self) -> Optional[TerrainRaster]:
        return self.rasters.get("slope_uncertainty")


def compute_sha256(path: Path, block_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 digest of a file in streaming chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def check_tiff_header(path: Path) -> bool:
    """Validate TIFF magic number in file header."""
    if not path.is_file():
        return False
    try:
        with path.open("rb") as stream:
            header = stream.read(4)
            return header in TIFF_MAGIC_HEADERS
    except OSError:
        return False


def inspect_lunar_crs_properties(crs: CRS) -> Tuple[bool, bool, Optional[int], str, str]:
    """Inspect CRS to determine if it is a lunar CRS without terrestrial EPSG.

    Returns:
        (is_lunar, is_terrestrial, epsg_code, wkt, proj4)
    """
    if crs is None:
        return False, False, None, "", ""
    wkt = crs.to_wkt()
    proj4 = crs.to_proj4() if hasattr(crs, "to_proj4") else ""
    epsg = crs.to_epsg()

    is_terrestrial = epsg is not None
    # Check for lunar spheroid radius 1737400 m
    is_lunar = False
    try:
        pyproj_crs = pyproj.CRS.from_user_input(crs)
        if pyproj_crs.ellipsoid:
            radius = pyproj_crs.ellipsoid.semi_major_metre
            if abs(radius - 1737400.0) < 1000.0:
                is_lunar = True
    except Exception:
        if "1737400" in wkt:
            is_lunar = True

    return is_lunar, is_terrestrial, epsg, wkt, proj4


def extract_raster_metadata(path: Path) -> TerrainRasterMetadata:
    """Extract and validate comprehensive metadata from a GeoTIFF.

    Raises:
        FileNotFoundError: If the raster does not exist.
        ValueError: If file is not a valid TIFF or cannot be opened.
    """
    if not path.exists():
        raise FileNotFoundError(f"Raster file not found: {path}")

    is_valid_header = check_tiff_header(path)
    if not is_valid_header:
        raise ValueError(f"Corrupt or non-TIFF file (invalid header): {path}")

    file_size = path.stat().st_size
    sha256 = compute_sha256(path)

    try:
        with rasterio.open(path) as src:
            is_lunar, is_terr, epsg, wkt, proj4 = inspect_lunar_crs_properties(src.crs)
            t = src.transform
            transform_tuple = (float(t.a), float(t.b), float(t.c), float(t.d), float(t.e), float(t.f))
            b = src.bounds
            bounds_tuple = (float(b.left), float(b.bottom), float(b.right), float(b.top))
            res_tuple = (float(src.res[0]), float(src.res[1]))

            return TerrainRasterMetadata(
                file_name=path.name,
                file_path=str(path.resolve()),
                file_size_bytes=file_size,
                sha256_hash=sha256,
                is_valid_tiff_header=is_valid_header,
                width=src.width,
                height=src.height,
                band_count=src.count,
                dtype=src.dtypes[0],
                nodata=src.nodata,
                crs_wkt=wkt,
                crs_proj4=proj4,
                is_lunar_crs=is_lunar,
                is_terrestrial_epsg=is_terr,
                epsg_code=epsg,
                transform=transform_tuple,
                resolution=res_tuple,
                bounds=bounds_tuple,
                tags=dict(src.tags()),
            )
    except rasterio.errors.RasterioError as exc:
        raise ValueError(f"Rasterio error reading GeoTIFF {path}: {exc}") from exc


def read_raster_band(path: Path, band: int = 1) -> Tuple[np.ndarray, TerrainRasterMetadata]:
    """Read full raster band array into memory and return with metadata.

    Verifies complete file readability and absence of truncated strips/tiles.
    """
    meta = extract_raster_metadata(path)
    try:
        with rasterio.open(path) as src:
            data = src.read(band)
            # Preserve valid values; represent the raster's own mask as NaN for
            # numerical kernels. LDEC zero remains valid unless explicitly masked.
            invalid = src.read_masks(band) == 0
            if np.any(invalid):
                if not np.issubdtype(data.dtype, np.floating):
                    data = data.astype(np.float64)
                data[invalid] = np.nan
            if data.shape != (meta.height, meta.width):
                raise ValueError(
                    f"Read array shape {data.shape} does not match metadata ({meta.height}, {meta.width})"
                )
            return data, meta
    except Exception as exc:
        raise ValueError(f"Failed to read raster data from {path}: {exc}") from exc


def load_site_dataset(
    site_dir: Path,
    site: str = "Site04",
    load_arrays: bool = False,
) -> SiteTerrainDataset:
    """Load the full suite of five core LOLA rasters for a lunar landing site.

    Args:
        site_dir: Directory containing the GeoTIFFs.
        site: Site identifier (e.g. 'Site04').
        load_arrays: If True, reads full array data into memory.
    """
    dataset = SiteTerrainDataset(site_id=site, site_dir=site_dir)

    for key, suffix in LOLA_CORE_PRODUCTS.items():
        raster_path = site_dir / f"{site}{suffix}"
        if not raster_path.exists():
            raise FileNotFoundError(
                f"Missing required LOLA {key} raster for {site}: {raster_path}"
            )

        if load_arrays:
            data, meta = read_raster_band(raster_path, band=1)
            dataset.rasters[key] = TerrainRaster(key=key, metadata=meta, data=data)
        else:
            meta = extract_raster_metadata(raster_path)
            dataset.rasters[key] = TerrainRaster(key=key, metadata=meta, data=None)

    return dataset


def require_compatible_grid(dataset: SiteTerrainDataset) -> None:
    """Reject incompatible layers before any cross-layer computation."""
    ref = dataset.elevation.metadata
    for key, raster in dataset.rasters.items():
        meta = raster.metadata
        if meta.file_name != dataset.site_id + LOLA_CORE_PRODUCTS[key]:
            raise ValueError(f"Incorrect site-layer association: {dataset.site_id}/{key}")
        crs_compatible = (meta.crs_wkt == ref.crs_wkt) or (
            meta.crs_proj4 == ref.crs_proj4
            or pyproj.CRS.from_wkt(meta.crs_wkt).to_dict() == pyproj.CRS.from_wkt(ref.crs_wkt).to_dict()
        )
        if (meta.width, meta.height, meta.transform, meta.band_count) != (
            ref.width, ref.height, ref.transform, 1
        ) or not crs_compatible:
            raise ValueError(f"Incompatible raster grid: {dataset.site_id}/{key}")
        if not meta.is_lunar_crs or meta.is_terrestrial_epsg:
            raise ValueError(f"Invalid lunar CRS: {dataset.site_id}/{key}")
