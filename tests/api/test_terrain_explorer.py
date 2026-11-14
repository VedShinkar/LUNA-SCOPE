from pathlib import Path

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from rasterio.crs import CRS
from rasterio.transform import Affine

from app.main import app
from app.scientific_engines.terrain.explorer import load_explorer_grid
from app.scientific_engines.terrain.service import TerrainService


def test_site04_explorer_serves_exact_aligned_samples():
    client = TestClient(app)
    response = client.get("/terrain/explorer/grid?max_dimension=64")
    assert response.status_code == 200
    grid = response.json()
    assert grid["site_id"] == "Site04"
    assert max(grid["height"], grid["width"]) <= 64
    stride, offset = (grid["sampling"][key] for key in ("stride", "offset"))
    transform = Affine(*grid["transform"])
    processed = Path("data/processed/terrain/site04")
    with rasterio.open(processed / "Site04_processed_elevation.tif") as source, rasterio.open(
        processed / "Site04_combined_hazard_screen.tif"
    ) as hazard:
        assert [grid["source_height"], grid["source_width"]] == list(source.shape)
        assert grid["crs_wkt"] == source.crs.to_wkt()
        assert grid["source_transform"] == list(source.transform)[:6]
        assert grid["source_resolution"] == list(source.res)
        assert grid["source_raster_type"] == source.tags()["AREA_OR_POINT"]
        native, hazard_native = source.read(1), hazard.read(1)
        for row, col in ((0, 0), (5, 8), (grid["height"] - 1, grid["width"] - 1)):
            source_row, source_col = row * stride + offset, col * stride + offset
            assert transform @ (col + 0.5, row + 0.5) == source.xy(source_row, source_col)
            index = row * grid["width"] + col
            assert grid["valid"][index]
            assert grid["elevation"]["values"][index] == native[source_row, source_col]
            assert grid["layers"]["hazards"]["values"][index] == hazard_native[source_row, source_col]
    assert client.get("/terrain/explorer/grid?max_dimension=385").status_code == 422


def test_explorer_keeps_unsampled_nodata_hole_and_rejects_unaligned_layers(tmp_path):
    path = tmp_path / "processed/terrain/site04"
    path.mkdir(parents=True)
    transform = Affine(4, 2, 100, 2, -4, 200)
    crs = CRS.from_string("+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m +type=crs")
    data = np.arange(36, dtype=np.float32).reshape(6, 6)
    data[1, 1] = np.nan
    data[0, 5] = np.nan
    for name, affine in (("processed_elevation", transform), ("calculated_slope_deg", transform @ Affine.translation(1, 0))):
        with rasterio.open(path / f"Site04_{name}.tif", "w", driver="GTiff", width=6, height=6,
                           count=1, dtype="float32", transform=affine, crs=crs, nodata=np.nan) as output:
            output.write(data, 1)
    grid = load_explorer_grid(3, root=tmp_path)
    assert grid["valid"] == [True] * 9
    assert grid["quad_valid"] == [False, True, True, True]
    assert grid["nodata_percent"] == 100 * (1 - 34 / 36)
    assert "differs" in grid["unavailable"]["slope"]
    assert "slope" not in grid["layers"]
    full = load_explorer_grid(6, root=tmp_path)
    assert full["elevation"]["values"][7] is None
    assert not full["valid"][7]


def test_explorer_horizon_preserves_missing_ray_positions(monkeypatch):
    def profile(self, **kwargs):
        return {
            "status": "SUCCESS",
            "is_valid": True,
            "azimuths_deg": [0.0, 5.0],
            "horizon_angles_deg": [np.nan, 4.0],
            "horizon_distances_m": [np.nan, 10.0],
            "horizon_obstacle_elevations_m": [np.nan, 15.0],
        }

    monkeypatch.setattr(TerrainService, "query_horizon", profile)
    response = TestClient(app).post("/terrain/horizon", json={"observer_x": 0, "observer_y": 0})
    assert response.status_code == 200
    result = response.json()
    assert result["azimuths_deg"] == [0.0, 5.0]
    assert result["horizon_angles_deg"] == [None, 4.0]
    assert result["horizon_distances_m"] == [None, 10.0]
    assert result["horizon_obstacle_elevations_m"] == [None, 15.0]
