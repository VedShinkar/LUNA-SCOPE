"""Isolated unit tests for TerrainService using temporary synthetic GeoTIFFs.

These tests exercise the real service loading/query code without depending on
large NASA LOLA rasters, which are intentionally excluded from Git.
Real-data validation belongs in a separate dataset-enabled integration suite.
"""
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.scientific_engines.terrain.hazards import CODE_TO_SEVERITY
from app.scientific_engines.terrain.horizon import pixel_to_world
from app.scientific_engines.terrain.service import TerrainService


@pytest.fixture
def terrain_service(tmp_path: Path) -> TerrainService:
    """Build a minimal, deterministic Site04 raster set in a temporary directory."""
    raw_dir = tmp_path / "raw" / "site04"
    processed_dir = tmp_path / "processed" / "site04"
    metadata_dir = tmp_path / "metadata"
    raw_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)

    height = width = 20
    transform = from_origin(1000.0, 2000.0, 5.0, 5.0)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": np.nan,
    }

    rows, cols = np.indices((height, width))
    dem = (100.0 + rows * 0.1 + cols * 0.05).astype(np.float32)
    dem[0, 0] = np.nan  # A deterministic NoData cell for the dedicated test.
    slope = np.full((height, width), 3.0, dtype=np.float32)
    aspect = np.full((height, width), 90.0, dtype=np.float32)
    roughness_15m = np.full((height, width), 0.2, dtype=np.float32)
    roughness_35m = np.full((height, width), 0.4, dtype=np.float32)
    roughness_75m = np.full((height, width), 0.8, dtype=np.float32)
    toterr = np.full((height, width), 0.3, dtype=np.float32)
    slperr = np.full((height, width), 0.2, dtype=np.float32)
    ldec = np.full((height, width), 3.0, dtype=np.float32)

    def write_raster(directory: Path, filename: str, data: np.ndarray) -> None:
        raster_profile = {**profile, "dtype": str(data.dtype)}
        if np.issubdtype(data.dtype, np.floating):
            raster_profile["nodata"] = np.nan
        else:
            raster_profile.pop("nodata", None)
        with rasterio.open(directory / filename, "w", **raster_profile) as dst:
            dst.write(data, 1)

    # Required raw LOLA inputs.
    write_raster(raw_dir, "Site04_final_adj_5mpp_surf.tif", dem)
    write_raster(raw_dir, "Site04_final_adj_5mpp_slp.tif", slope)
    write_raster(raw_dir, "Site04_final_adj_5mpp_toterr.tif", toterr)
    write_raster(raw_dir, "Site04_final_adj_5mpp_slperr.tif", slperr)
    write_raster(raw_dir, "Site04_final_adj_5mpp_ldec.tif", ldec)

    # Derived layers consumed by TerrainService.
    write_raster(processed_dir, "Site04_calculated_slope_deg.tif", slope)
    write_raster(processed_dir, "Site04_calculated_aspect_deg.tif", aspect)
    write_raster(processed_dir, "Site04_roughness_15m.tif", roughness_15m)
    write_raster(processed_dir, "Site04_roughness_35m.tif", roughness_35m)
    write_raster(processed_dir, "Site04_roughness_75m.tif", roughness_75m)
    write_raster(
        processed_dir,
        "Site04_combined_hazard_screen.tif",
        np.ones((height, width), dtype=np.uint8),
    )
    write_raster(
        processed_dir,
        "Site04_data_quality_screen.tif",
        np.ones((height, width), dtype=np.uint8),
    )

    service = TerrainService(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        metadata_dir=metadata_dir,
        site_id="Site04",
    )
    service._ensure_loaded()
    return service


def test_query_point_returns_all_fields(terrain_service: TerrainService) -> None:
    service = terrain_service
    assert service._meta is not None
    centre_easting = (service._meta.bounds[0] + service._meta.bounds[2]) / 2.0
    centre_northing = (service._meta.bounds[1] + service._meta.bounds[3]) / 2.0

    result = service.query_point(
        easting_m=centre_easting,
        northing_m=centre_northing,
    )

    expected_keys = {
        "site_id",
        "coordinates",
        "within_bounds",
        "is_valid",
        "raster_indices",
        "elevation_m",
        "slope_deg",
        "aspect_deg",
        "aspect_description",
        "roughness",
        "hazard_classification",
        "uncertainty_and_observation",
        "provenance",
    }
    assert expected_keys.issubset(result)
    assert result["site_id"] == "Site04"
    assert result["within_bounds"] is True
    assert result["is_valid"] is True
    assert np.isfinite(result["elevation_m"])
    assert result["slope_deg"] == pytest.approx(3.0)
    assert result["aspect_deg"] == pytest.approx(90.0)

    hazard = result["hazard_classification"]
    code = hazard["combined_screening_code"]
    assert hazard["combined_screening_class"] == CODE_TO_SEVERITY.get(code, "UNKNOWN")
    assert hazard["policy"] == "Option B: Decoupled Decisional Screening"

    uncertainty = result["uncertainty_and_observation"]
    assert uncertainty["lola_observation_count"] == 3
    assert uncertainty["is_direct_observation"] is True
    assert uncertainty["is_interpolated"] is False


def test_query_point_out_of_bounds(terrain_service: TerrainService) -> None:
    service = terrain_service
    assert service._meta is not None
    out_easting = service._meta.bounds[2] + 1_000_000.0
    out_northing = service._meta.bounds[3] + 1_000_000.0

    result = service.query_point(
        easting_m=out_easting,
        northing_m=out_northing,
    )

    assert result["within_bounds"] is False
    assert result["is_valid"] is False
    assert "outside the raster spatial extent" in result["error"].lower()


def test_query_point_nodata_cell(terrain_service: TerrainService) -> None:
    service = terrain_service
    assert service._dem is not None
    assert service._transform is not None
    nodata_cells = np.argwhere(~np.isfinite(service._dem))
    assert nodata_cells.size > 0, "The fixture must contain a NoData cell."

    row, col = nodata_cells[0]
    x, y = pixel_to_world(col + 0.5, row + 0.5, service._transform)
    result = service.query_point(easting_m=x, northing_m=y)

    assert result["within_bounds"] is True
    assert result["is_valid"] is False
    assert result["error"] == "Cell contains NoData."
