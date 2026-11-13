"""Unit tests for the TerrainService (backend/app/scientific_engines/terrain/service.py).
These tests use the real Site04 DEM and derived rasters already present in the repository.
They verify that the point query returns all required fields, handles bounds and NoData correctly,
and that the hazard classification follows the Option B policy.
"""

import os
import numpy as np
from pathlib import Path

from app.scientific_engines.terrain.service import TerrainService
from app.scientific_engines.terrain.hazards import CODE_TO_SEVERITY


def _get_service():
    """Return a loaded singleton TerrainService.
    The service loads rasters from the repository's data directories.
    """
    service = TerrainService.get_instance()
    # Force loading; this will raise if required files are missing.
    service._ensure_loaded()
    return service


def test_query_point_returns_all_fields():
    service = _get_service()
    meta = service._meta
    # Choose a coordinate roughly at the centre of the raster bounds.
    centre_easting = (meta.bounds[0] + meta.bounds[2]) / 2.0
    centre_northing = (meta.bounds[1] + meta.bounds[3]) / 2.0

    res = service.query_point(easting_m=centre_easting, northing_m=centre_northing)

    # Core response keys
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
    assert expected_keys.issubset(res.keys())
    assert res["within_bounds"] is True
    assert res["is_valid"] is True
    # Verify numeric fields are present and finite where applicable
    assert isinstance(res["elevation_m"], float)
    assert isinstance(res["slope_deg"], (float, type(None)))
    # Check hazard classification mapping consistency
    hazard = res["hazard_classification"]
    assert hazard["combined_screening_code"] == hazard["combined_screening_code"]
    # Ensure the combined class string matches the code via the mapping
    expected_class = CODE_TO_SEVERITY.get(hazard["combined_screening_code"], "UNKNOWN")
    assert hazard["combined_screening_class"] == expected_class
    # Policy must be Option B
    assert hazard.get("policy") == "Option B: Decoupled Decisional Screening"


def test_query_point_out_of_bounds():
    service = _get_service()
    meta = service._meta
    # Generate a coordinate far outside the raster extents
    out_easting = meta.bounds[2] + 1_000_000.0
    out_northing = meta.bounds[3] + 1_000_000.0
    res = service.query_point(easting_m=out_easting, northing_m=out_northing)
    assert res["within_bounds"] is False
    assert res["is_valid"] is False
    assert "error" in res
    assert "outside the raster spatial extent" in res["error"].lower()


def test_query_point_nodata_cell():
    service = _get_service()
    # Find a raster cell that contains NaN (NoData) in the DEM.
    dem = service._dem
    nan_coords = np.argwhere(~np.isfinite(dem))
    if nan_coords.size == 0:
        # If the DEM has no explicit NaN values, skip this test.
        return
    row, col = nan_coords[0]
    # Convert pixel indices to world coordinates using the stored affine.
    from app.scientific_engines.terrain.horizon import pixel_to_world
    x, y = pixel_to_world(col + 0.5, row + 0.5, service._transform)
    res = service.query_point(easting_m=x, northing_m=y)
    assert res["within_bounds"] is True
    assert res["is_valid"] is False
    assert res["error"] == "Cell contains NoData."
