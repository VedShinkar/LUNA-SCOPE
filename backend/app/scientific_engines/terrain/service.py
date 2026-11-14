"""Terrain Intelligence Service layer for configured lunar sites.

Provides centralized, thread-safe access to validated site-specific terrain layers:
- Point coordinate queries for terrain attributes, hazards, and uncertainties.
- Local terrain horizon profile generation.
- Complete site-level summary and provenance metadata.
"""
from __future__ import annotations

import json
from threading import RLock
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio
from rasterio.transform import Affine

from app.scientific_engines.terrain.hazards import CODE_TO_SEVERITY, SEVERITY_TO_CODE
from app.scientific_engines.terrain.horizon import (
    compute_terrain_horizon_profile,
    world_to_pixel,
)
from app.scientific_engines.terrain.loader import (
    TerrainRasterMetadata,
    extract_raster_metadata,
    load_site_dataset,
    require_compatible_grid,
)
from app.scientific_engines.terrain.catalog import ROOT, get_site_config, verify_source_association

DEFAULT_RAW_DIR = Path("data/raw/terrain/site04")
DEFAULT_PROCESSED_DIR = Path("data/processed/terrain/site04")
DEFAULT_METADATA_DIR = ROOT / "data/metadata/terrain"


class TerrainService:
    """Cached service managing one site's terrain rasters and queries."""

    _instance: Optional["TerrainService"] = None
    _instances: Dict[str, "TerrainService"] = {}
    _cache_lock = RLock()

    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
        metadata_dir: Path = DEFAULT_METADATA_DIR,
        site_id: str = "Site04",
    ):
        self.config = get_site_config(site_id)
        self._verify_provenance = raw_dir is None
        self.raw_dir = Path(raw_dir) if raw_dir is not None else self.config["raw_dir"]
        self.processed_dir = Path(processed_dir) if processed_dir is not None else self.config["processed_dir"]
        self._load_lock = RLock()
        self.metadata_dir = metadata_dir
        self.site_id = site_id

        # Cached raster data and metadata
        self._loaded = False
        self._dem: Optional[np.ndarray] = None
        self._slope: Optional[np.ndarray] = None
        self._aspect: Optional[np.ndarray] = None
        self._r15: Optional[np.ndarray] = None
        self._r35: Optional[np.ndarray] = None
        self._r75: Optional[np.ndarray] = None
        self._toterr: Optional[np.ndarray] = None
        self._slperr: Optional[np.ndarray] = None
        self._ldec: Optional[np.ndarray] = None
        self._hazard_combined: Optional[np.ndarray] = None
        self._data_quality: Optional[np.ndarray] = None
        self._meta: Optional[TerrainRasterMetadata] = None
        self._transform: Optional[Affine] = None

    @classmethod
    def get_instance(cls, site_id: str = "Site04") -> "TerrainService":
        """Cache one isolated service per configured site."""
        get_site_config(site_id)
        with cls._cache_lock:
            if site_id == "Site04":
                if cls._instance is None:
                    cls._instance = cls(site_id=site_id)
                return cls._instance
            if site_id not in cls._instances:
                cls._instances[site_id] = cls(site_id=site_id)
            return cls._instances[site_id]

    def _ensure_loaded(self) -> None:
        with self._load_lock:
            self._load()

    def _load(self) -> None:
        """Load required rasters into memory if not already cached."""
        if self._loaded:
            return

        sources = load_site_dataset(self.raw_dir, self.site_id)
        require_compatible_grid(sources)
        if self._verify_provenance:
            verify_source_association(sources, self.metadata_dir)

        surf_path = self.raw_dir / f"{self.site_id}_final_adj_5mpp_surf.tif"
        if not surf_path.exists():
            raise FileNotFoundError(f"Missing primary DEM at {surf_path}")

        self._meta = sources.elevation.metadata
        self._transform = Affine(*self._meta.transform)

        def read_aligned(path, categorical=False):
            if not path.is_file():
                raise FileNotFoundError(f"Missing required terrain product for {self.site_id}: {path}")
            with rasterio.open(path) as source:
                source_hash = source.tags().get("SOURCE_DEM_SHA256")
                if source_hash is not None and source_hash != self._meta.sha256_hash:
                    raise ValueError(f"Incorrect source association for terrain product: {path}")
                ref_crs = rasterio.crs.CRS.from_wkt(self._meta.crs_wkt)
                crs_ok = (source.crs == ref_crs) or (
                    source.crs.to_proj4() == ref_crs.to_proj4()
                    or pyproj.CRS.from_wkt(source.crs.to_wkt()).to_dict() == pyproj.CRS.from_wkt(self._meta.crs_wkt).to_dict()
                )
                if (source.width, source.height, source.transform) != (
                    self._meta.width, self._meta.height, self._transform
                ) or not crs_ok:
                    raise ValueError(f"Incompatible terrain product grid: {path}")
                values = source.read(1, masked=True)
                if categorical:
                    return values.filled(0)
                return values.astype(np.float32).filled(np.nan)

        self._dem = read_aligned(surf_path)
        for attribute, suffix in {
            "_slope": "calculated_slope_deg", "_aspect": "calculated_aspect_deg",
            "_r15": "roughness_15m", "_r35": "roughness_35m", "_r75": "roughness_75m",
            "_hazard_combined": "combined_hazard_screen", "_data_quality": "data_quality_screen",
        }.items():
            setattr(self, attribute, read_aligned(
                self.processed_dir / f"{self.site_id}_{suffix}.tif",
                categorical=attribute in ("_hazard_combined", "_data_quality"),
            ))
        for attribute, suffix in {"_toterr": "toterr", "_slperr": "slperr", "_ldec": "ldec"}.items():
            setattr(self, attribute, read_aligned(self.raw_dir / f"{self.site_id}_final_adj_5mpp_{suffix}.tif"))

        maximum = np.zeros(self._dem.shape, dtype=np.uint8)
        missing = np.zeros(self._dem.shape, dtype=bool)
        for key in ("slope", "roughness_small", "roughness_medium", "roughness_large"):
            codes = read_aligned(self.processed_dir / f"{self.site_id}_hazard_{key}.tif", categorical=True)
            if not np.isin(codes, [0, 1, 2, 3]).all():
                raise ValueError(f"Invalid physical hazard codes: {self.site_id}/{key}")
            np.maximum(maximum, codes, out=maximum)
            missing |= codes == 0
        maximum[missing & (maximum < 2)] = 0
        self._physical_hazard = maximum
        self._loaded = True

    def query_point(
        self,
        easting_m: float,
        northing_m: float,
    ) -> Dict[str, Any]:
        """Query terrain properties at given Lunar South-Polar Stereographic coordinates.

        Args:
            easting_m: Projected Easting coordinate in metres.
            northing_m: Projected Northing coordinate in metres.

        Returns:
            Structured dictionary conforming to API contracts.
        """
        self._ensure_loaded()
        assert self._meta is not None
        assert self._transform is not None

        col, row = world_to_pixel(easting_m, northing_m, self._transform)
        w, h = self._meta.width, self._meta.height

        c_idx = int(np.floor(col))
        r_idx = int(np.floor(row))

        within_bounds = (0 <= c_idx < w) and (0 <= r_idx < h)

        if not within_bounds:
            return {
                "site_id": self.site_id,
                "coordinates": {
                    "easting_m": float(easting_m),
                    "northing_m": float(northing_m),
                    "coordinate_system": "Lunar South-Polar Stereographic",
                    "reference_frame": "MOON_ME associated with DE421 ephemeris",
                },
                "within_bounds": False,
                "is_valid": False,
                "error": "Coordinates are outside the raster spatial extent.",
                "raster_indices": {"col": c_idx, "row": r_idx},
            }

        # Read cell values
        elev_val = float(self._dem[r_idx, c_idx]) if self._dem is not None else float(np.nan)
        is_finite_dem = np.isfinite(elev_val)

        if not is_finite_dem:
            return {
                "site_id": self.site_id,
                "coordinates": {
                    "easting_m": float(easting_m),
                    "northing_m": float(northing_m),
                    "coordinate_system": "Lunar South-Polar Stereographic",
                    "reference_frame": "MOON_ME associated with DE421 ephemeris",
                },
                "within_bounds": True,
                "is_valid": False,
                "error": "Cell contains NoData.",
                "raster_indices": {"col": c_idx, "row": r_idx},
            }

        slope_val = float(self._slope[r_idx, c_idx]) if self._slope is not None else float(np.nan)
        aspect_val = float(self._aspect[r_idx, c_idx]) if self._aspect is not None else float(np.nan)

        r15_val = float(self._r15[r_idx, c_idx]) if self._r15 is not None else float(np.nan)
        r35_val = float(self._r35[r_idx, c_idx]) if self._r35 is not None else float(np.nan)
        r75_val = float(self._r75[r_idx, c_idx]) if self._r75 is not None else float(np.nan)

        toterr_val = float(self._toterr[r_idx, c_idx]) if self._toterr is not None else float(np.nan)
        slperr_val = float(self._slperr[r_idx, c_idx]) if self._slperr is not None else float(np.nan)
        ldec_raw = float(self._ldec[r_idx, c_idx]) if self._ldec is not None else float(np.nan)
        ldec_val = int(ldec_raw) if np.isfinite(ldec_raw) and ldec_raw >= 0 else None

        comb_code = int(self._hazard_combined[r_idx, c_idx]) if self._hazard_combined is not None else 0
        comb_class = CODE_TO_SEVERITY.get(comb_code, "UNKNOWN")

        qual_code = int(self._data_quality[r_idx, c_idx]) if self._data_quality is not None else 0
        qual_class = CODE_TO_SEVERITY.get(qual_code, "UNKNOWN")

        phys_code = int(self._physical_hazard[r_idx, c_idx])
        phys_class = CODE_TO_SEVERITY.get(phys_code, "UNKNOWN")

        is_interp = ldec_val == 0 if ldec_val is not None else False
        is_direct = ldec_val > 0 if ldec_val is not None else False

        return {
            "site_id": self.site_id,
            "coordinates": {
                "easting_m": float(easting_m),
                "northing_m": float(northing_m),
                "coordinate_system": "Lunar South-Polar Stereographic",
                "reference_frame": "MOON_ME associated with DE421 ephemeris",
                "units": "metre",
            },
            "within_bounds": True,
            "is_valid": True,
            "raster_indices": {"col": c_idx, "row": r_idx},
            "elevation_m": round(elev_val, 3),
            "slope_deg": round(slope_val, 4) if np.isfinite(slope_val) else None,
            "aspect_deg": round(aspect_val, 2) if np.isfinite(aspect_val) else None,
            "aspect_description": "Clockwise from grid North (+Y Northing). Flat terrain coded as -1.0.",
            "roughness": {
                "roughness_15m_m": round(r15_val, 4) if np.isfinite(r15_val) else None,
                "roughness_35m_m": round(r35_val, 4) if np.isfinite(r35_val) else None,
                "roughness_75m_m": round(r75_val, 4) if np.isfinite(r75_val) else None,
                "scale_classification": "provisional_analytical_scales",
                "metric": "unbiased_sample_elevation_standard_deviation_ddof1",
            },
            "hazard_classification": {
                "physical_hazard_class": phys_class,
                "physical_hazard_code": phys_code,
                "epistemic_quality_class": qual_class,
                "epistemic_quality_code": qual_code,
                "combined_screening_class": comb_class,
                "combined_screening_code": comb_code,
                "policy": "Option B: Decoupled Decisional Screening",
            },
            "uncertainty_and_observation": {
                "lola_observation_count": ldec_val,
                "elevation_uncertainty_m_rms": round(toterr_val, 4) if np.isfinite(toterr_val) else None,
                "slope_uncertainty_deg_rms": round(slperr_val, 4) if np.isfinite(slperr_val) else None,
                "is_interpolated": is_interp,
                "is_direct_observation": is_direct,
            },
            "provenance": {
                "source_dataset": f"NASA LOLA 5m South Polar PGDA ({self.site_id}: {self.config['name']})",
                "dem_product_id": f"{self.site_id}_final_adj_5mpp_surf",
                "grid_resolution_m": [self._meta.resolution[0], self._meta.resolution[1]],
                "vertical_datum": "1737.4 km lunar spherical datum",
                "evidence_class": "DIRECT_OBSERVATION" if is_direct else "INTERPOLATED_TERRAIN",
            },
        }

    def query_horizon(
        self,
        observer_x: float,
        observer_y: float,
        azimuth_step_deg: float = 1.0,
        azimuths_deg: Optional[List[float]] = None,
        observer_height_m: float = 2.0,
        max_range_m: float = 5000.0,
        sample_interval_m: float = 5.0,
        include_curvature: bool = True,
    ) -> Dict[str, Any]:
        """Compute local terrain-horizon profile for observer."""
        self._ensure_loaded()
        assert self._dem is not None
        assert self._transform is not None

        result = compute_terrain_horizon_profile(
            dem=self._dem,
            transform=self._transform,
            observer_x=observer_x,
            observer_y=observer_y,
            azimuth_step_deg=azimuth_step_deg,
            azimuths_deg=azimuths_deg,
            observer_height_m=observer_height_m,
            max_range_m=max_range_m,
            sample_interval_m=sample_interval_m,
            include_curvature=include_curvature,
            site_id=self.site_id,
        )

        result["site_id"] = self.site_id
        return result

    def get_site_summary(self) -> Dict[str, Any]:
        """Return comprehensive site-level metadata, statistics, and distributions."""
        self._ensure_loaded()
        assert self._meta is not None

        # Load reports if available
        p3_report_path = self.metadata_dir / f"{self.site_id.lower()}_phase3_hazard_report.json"
        p2_report_path = self.metadata_dir / f"{self.site_id.lower()}_phase2_terrain_report.json"
        p1_report_path = self.metadata_dir / f"{self.site_id.lower()}_validation_report.json"

        p3_data: Dict[str, Any] = {}
        if p3_report_path.exists():
            p3_data = json.loads(p3_report_path.read_text(encoding="utf-8"))

        p2_data: Dict[str, Any] = {}
        if p2_report_path.exists():
            p2_data = json.loads(p2_report_path.read_text(encoding="utf-8"))

        p1_data: Dict[str, Any] = {}
        if p1_report_path.exists():
            p1_data = json.loads(p1_report_path.read_text(encoding="utf-8"))

        for report in (p1_data, p2_data, p3_data):
            if report and report.get("site") != self.site_id:
                raise ValueError(f"Incorrect report/site association for {self.site_id}")

        left, bottom, right, top = self._meta.bounds

        return {
            "site_id": self.site_id,
            "site_name": self.config.get("display_name", self.config["name"]),
            "region": "Lunar South Pole",
            "coordinate_system": {
                "name": "Lunar South-Polar Stereographic",
                "projection": "Polar_Stereographic",
                "reference_frame": "MOON_ME associated with DE421 ephemeris",
                "spheroid_radius_m": 1737400.0,
                "origin_latitude": -90.0,
                "central_meridian": 0.0,
                "linear_units": "metre",
                "crs_wkt": self._meta.crs_wkt,
                "no_terrestrial_epsg": True,
            },
            "spatial_grid": {
                "width_pixels": self._meta.width,
                "height_pixels": self._meta.height,
                "total_pixels": self._meta.width * self._meta.height,
                "pixel_spacing_x_m": self._meta.resolution[0],
                "pixel_spacing_y_m": self._meta.resolution[1],
                "bounds_projected_m": {
                    "left_easting": left,
                    "right_easting": right,
                    "bottom_northing": bottom,
                    "top_northing": top,
                },
                "affine_transform": list(self._meta.transform),
            },
            "elevation_summary": p2_data.get("elevation_summary", {}).get("statistics"),
            "slope_summary": {
                "primary_method": "zevenbergen_thorne_2nd_order_central_difference",
                "comparison_against_nasa_supplied": p2_data.get("slope_analysis", {}).get(
                    "zevenbergen_thorne_vs_nasa_supplied", {}
                ).get("metrics_deg"),
            },
            "roughness_summary": {
                "scale_classification": "provisional_analytical_scales",
                "scales": p2_data.get("roughness_analysis", {}).get("scales"),
            },
            "epistemic_quality_and_observation": {
                "interpolation_and_observations": p3_data.get("interpolation_and_observation_summary"),
                "epistemic_quality_summary_counts": p3_data.get("epistemic_quality_summary_counts"),
                "epistemic_quality_summary_percentages": p3_data.get("epistemic_quality_summary_percentages"),
            },
            "hazard_screening_summary": {
                "policy": p3_data.get("policy", "Option B: Decoupled Decisional Screening"),
                "combined_class_counts": p3_data.get("combined_class_counts"),
                "combined_class_percentages": p3_data.get("combined_class_percentages"),
                "physical_hazard_summary_counts": p3_data.get("physical_hazard_summary_counts"),
                "physical_hazard_summary_percentages": p3_data.get("physical_hazard_summary_percentages"),
                "combination_rules": p3_data.get("combination_rules"),
            },
            "data_provenance": {
                "source": "NASA Planetary Geosciences Data Node (PGDA) LOLA Polar Digital Elevation Models",
                "dataset_id": f"{self.site_id}_final_adj_5mpp",
                "ephemeris": "JPL DE421",
                "processing_phases_completed": [label for label, passed in (("Phase 1: Ingestion & Validation", p1_data.get("phase1_gate_passed")), ("Phase 2: Terrain Computation", p2_data.get("phase2_complete")), ("Phase 3: Hazard Intelligence", p3_data.get("phase3_complete"))) if passed],
            },
            "scientific_limitations": p3_data.get("scientific_limitations", [
                "Pixel spacing is not measurement spacing; consult this site's LDEC coverage.",
                "Roughness and hazard thresholds are provisional and unsupported by vehicle-specific dimensions.",
                "This is a decision-support preliminary screening layer, NOT a certified landing-site safety assessment.",
            ]),
        }
