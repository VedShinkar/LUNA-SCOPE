from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.crs import CRS
from rasterio.transform import Affine
from rasterio.warp import transform

from app.main import app
from app.scientific_engines.terrain.explorer import load_explorer_grid
from app.scientific_engines.terrain.service import TerrainService


@pytest.mark.parametrize("site_id", ["Site04", "Site11", "Site23"])
def test_catalogued_site_grid_window_and_profile_are_isolated(site_id):
    client = TestClient(app)
    site = next(site for site in client.get('/terrain/explorer/context').json()['sites'] if site['site_id'] == site_id)
    assert site['available'] and site['reference']
    params = {'site_id': site_id, 'max_dimension': 32, 'easting_m': site['easting'], 'northing_m': site['northing']}
    response = client.get('/terrain/explorer/grid', params=params)
    assert response.status_code == 200, response.text
    grid = response.json()
    assert grid['site_id'] == site_id and grid['source_file'].startswith(site_id)
    assert grid['resolution'] == [5, 5]
    assert {'nasa_slope', 'coverage', 'uncertainty', 'elevation_uncertainty', 'hazards'} <= grid['layers'].keys()
    with rasterio.open(Path('data/processed/terrain') / site_id.lower() / grid['source_file']) as raster:
        affine = Affine(*grid['transform'])
        row, col = raster.index(*(affine @ (8.5, 5.5)))
        assert raster.xy(row, col) == affine @ (8.5, 5.5)
        assert grid['elevation']['values'][5 * grid['width'] + 8] == raster.read(1)[row, col]
        point = {key: site[key] for key in ('latitude', 'longitude')}
        profile = client.post('/terrain/explorer/profile', json={'start': point, 'end': point, 'level': 'site', 'site_id': site_id})
        assert profile.status_code == 200, profile.text
        assert profile.json()['source'].startswith(site_id)
        # Avoid a coordinate exactly on a pixel corner in the equality check.
        x, y = raster.xy(row, col)
        lon, lat = transform(raster.crs, '+proj=longlat +R=1737400 +type=crs', [x], [y])
        point = {'latitude': lat[0], 'longitude': lon[0]}
        profile = client.post('/terrain/explorer/profile', json={'start': point, 'end': point, 'level': 'site', 'site_id': site_id})
        assert profile.json()['elevation_m'] == [grid['elevation']['values'][5 * grid['width'] + 8]] * 128
    other = 'Site11' if site_id == 'Site04' else 'Site04'
    assert client.get('/terrain/explorer/grid', params={**params, 'site_id': other}).status_code == 422


@pytest.mark.parametrize("site_id", ["Site04", "Site11", "Site23"])
def test_regional_approach_contains_target(site_id):
    from app.scientific_engines.terrain.lunar_context import regional_grid, site_context

    site = site_context(site_id)
    grid = regional_grid('approach', site_id)
    col, row = (~Affine(*grid['transform'])) @ (site['easting'], site['northing'])
    assert 0 < col < grid['width'] and 0 < row < grid['height']
    assert grid['elevation']['values'][int(row) * grid['width'] + int(col)] is not None


def test_explorer_distinguishes_unknown_and_unavailable_sites(monkeypatch):
    from app.scientific_engines.terrain import explorer
    from rasterio.errors import RasterioIOError

    client = TestClient(app)
    assert client.get('/terrain/explorer/grid?site_id=Site99').status_code == 404
    def unavailable(*args, **kwargs):
        raise RasterioIOError('Missing fixture')
    monkeypatch.setattr(explorer.rasterio, 'open', unavailable)
    response = client.get('/terrain/explorer/grid?site_id=Site23')
    assert response.status_code == 503 and 'Site23' in response.json()['detail']


def test_archived_comparison_does_not_mix_site_summaries():
    response = TestClient(app).get('/terrain/explorer/comparison')
    assert response.status_code == 200
    sites = response.json()['sites']
    assert [site['site_id'] for site in sites] == ['Site04', 'Site11', 'Site23']
    assert len({site['metrics']['elevation']['minimum_m'] for site in sites}) == 3


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
