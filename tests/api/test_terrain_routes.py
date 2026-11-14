"""API contract tests for the Terrain endpoints.
These tests use FastAPI's TestClient against the live app defined in backend/app/main.py.
They verify that the four routes return the schemas defined in docs/API_CONTRACTS.md.
"""

import json
from fastapi.testclient import TestClient

from backend.app.main import app  # Adjust import path if needed

client = TestClient(app)


def test_get_terrain_site_summary():
    response = client.get("/terrain/site")
    assert response.status_code == 200
    data = response.json()
    # Expect site‑level keys defined in SiteSummaryResponse
    expected_keys = {
        "site_id",
        "site_name",
        "region",
        "coordinate_system",
        "spatial_grid",
        "data_provenance",
        "scientific_limitations",
    }
    assert expected_keys.issubset(set(data.keys()))


def test_get_terrain_site_point_query():
    # Choose centre of DEM from service metadata (reuse same logic)
    from app.scientific_engines.terrain.service import TerrainService
    service = TerrainService.get_instance()
    service._ensure_loaded()
    meta = service._meta
    centre_easting = (meta.bounds[0] + meta.bounds[2]) / 2.0
    centre_northing = (meta.bounds[1] + meta.bounds[3]) / 2.0

    response = client.get(
        "/terrain/site",
        params={"easting_m": centre_easting, "northing_m": centre_northing},
    )
    assert response.status_code == 200
    data = response.json()
    # Should contain point query fields
    point_keys = {
        "elevation_m",
        "slope_deg",
        "aspect_deg",
        "roughness",
        "hazard_classification",
        "uncertainty_and_observation",
    }
    assert point_keys.issubset(set(data.keys()))
    assert data["within_bounds"] is True
    assert data["is_valid"] is True


def test_post_terrain_point():
    from app.scientific_engines.terrain.service import TerrainService
    service = TerrainService.get_instance()
    service._ensure_loaded()
    meta = service._meta
    centre_easting = (meta.bounds[0] + meta.bounds[2]) / 2.0
    centre_northing = (meta.bounds[1] + meta.bounds[3]) / 2.0

    payload = {"easting_m": centre_easting, "northing_m": centre_northing}
    response = client.post("/terrain/point", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Verify response matches TerrainPointQueryResponse schema (subset)
    required = ["site_id", "coordinates", "within_bounds", "is_valid", "elevation_m"]
    for key in required:
        assert key in data
    assert data["within_bounds"] is True
    assert data["is_valid"] is True


def test_post_terrain_horizon():
    from app.scientific_engines.terrain.service import TerrainService
    service = TerrainService.get_instance()
    service._ensure_loaded()
    meta = service._meta
    # Use centre point as observer
    centre_easting = (meta.bounds[0] + meta.bounds[2]) / 2.0
    centre_northing = (meta.bounds[1] + meta.bounds[3]) / 2.0
    payload = {
        "observer_x": centre_easting,
        "observer_y": centre_northing,
        "azimuth_step_deg": 90,
        "observer_height_m": 2.0,
    }
    response = client.post("/terrain/horizon", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Basic contract assertions
    assert data["status"] == "SUCCESS"
    assert data["is_valid"] is True
    assert isinstance(data["horizon_angles_deg"], list)
    assert isinstance(data["azimuths_deg"], list)
    # Length should match number of sampled azimuths (360/90 = 4)
    assert len(data["azimuths_deg"]) == 4


def test_get_terrain_summary_endpoint():
    response = client.get("/terrain/summary")
    assert response.status_code == 200
    data = response.json()
    # Should contain the same keys as get_terrain_site_summary
    expected_keys = {
        "site_id",
        "site_name",
        "region",
        "coordinate_system",
        "spatial_grid",
        "data_provenance",
        "scientific_limitations",
    }
    assert expected_keys.issubset(set(data.keys()))
