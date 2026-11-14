"""Small, offline fixtures exercise site isolation and native grid handling."""
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine
from fastapi.testclient import TestClient

from app.main import app
from app.scientific_engines.terrain.catalog import UnknownSiteError, verify_source_association
from app.scientific_engines.terrain.loader import LOLA_CORE_PRODUCTS, load_site_dataset, require_compatible_grid
from app.scientific_engines.terrain.pipeline import run_phase2_terrain_pipeline, run_phase3_hazard_pipeline
from app.scientific_engines.terrain.service import TerrainService
from app.scientific_engines.terrain.validation import validate_site_rasters

CRS = '+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +no_defs'


def source_suite(root, site, shape, transform, height):
    raw = root / site / 'raw'
    raw.mkdir(parents=True)
    y, x = np.indices(shape)
    dem = (height + x * 0.5).astype('float32')
    values = {'elevation': dem, 'slope': np.full(shape, np.degrees(np.arctan(0.5 / transform.a))),
              'observation_count': (x % 3).astype('int16'),
              'elevation_uncertainty': np.full(shape, 0.2), 'slope_uncertainty': np.full(shape, 0.2)}
    for key, suffix in LOLA_CORE_PRODUCTS.items():
        arr = values[key].astype('int16' if key == 'observation_count' else 'float32')
        arr[0, 0] = -9999
        with rasterio.open(raw / (site + suffix), 'w', driver='GTiff', height=shape[0], width=shape[1],
                           count=1, dtype=arr.dtype, nodata=-9999, crs=CRS, transform=transform) as dst:
            dst.write(arr, 1)
    return raw


@pytest.fixture
def sites(tmp_path):
    services = {}
    for site, shape, transform, height in [
        ('Site04', (24, 32), Affine(5, 0, 100, 0, -5, 300), 100),
        ('Site11', (32, 40), Affine(5, 0, 1000, 0, -5, 2000), 500),
        ('Site23', (40, 48), Affine(10, 0, -3000, 0, -10, 4000), 1000),
    ]:
        raw = source_suite(tmp_path, site, shape, transform, height)
        processed, metadata = tmp_path / site / 'processed', tmp_path / site / 'metadata'
        metadata.mkdir()
        validation = validate_site_rasters(raw, site, metadata / f'{site.lower()}_validation_report.json')
        assert validation['phase1_gate_passed']
        run_phase2_terrain_pipeline(raw, processed, metadata, site, False)
        run_phase3_hazard_pipeline(raw, processed, metadata, site, False, reuse_phase2_roughness=True)
        services[site] = TerrainService(raw, processed, metadata, site)
    return services


def test_different_grids_and_site_queries(sites):
    for site, service in sites.items():
        service._ensure_loaded()
        x, y = service._transform @ (12.5, 12.5)
        point = service.query_point(x, y)
        assert point['site_id'] == site
        assert point['elevation_m'] == float(service._dem[12, 12])
        assert point['uncertainty_and_observation']['is_interpolated']
        summary = service.get_site_summary()
        assert summary['spatial_grid']['width_pixels'] == service._dem.shape[1]
        assert summary['site_name'] == service.config.get('display_name', service.config['name'])
        horizon = service.query_horizon(x, y, azimuths_deg=[90], max_range_m=30,
                                        observer_height_m=0, include_curvature=False)
        assert horizon['site_id'] == site
        assert horizon['horizon_angles_deg'][0] == pytest.approx(np.degrees(np.arctan(0.5 / service._transform.a)), abs=0.0001)
        assert not service.query_point(*(service._transform @ (0.5, 0.5)))['is_valid']
    x, y = sites['Site11']._transform @ (12.5, 12.5)
    assert not sites['Site04'].query_point(x, y)['within_bounds']


def test_api_selection_and_default(sites, monkeypatch):
    def instance(cls, site_id='Site04'):
        if site_id not in sites:
            raise UnknownSiteError(site_id)
        return sites[site_id]
    monkeypatch.setattr(TerrainService, 'get_instance', classmethod(instance))
    client = TestClient(app)
    assert client.get('/terrain/summary').json()['site_id'] == 'Site04'
    for site, service in sites.items():
        service._ensure_loaded()
        x, y = service._transform @ (12.5, 12.5)
        for endpoint in ['site', 'summary']:
            response = client.get(f'/terrain/{endpoint}', params={'site_id': site})
            assert response.status_code == 200
            assert response.json()['site_id'] == site
        response = client.post('/terrain/point', json={'site_id': site, 'easting_m': x, 'northing_m': y})
        assert response.status_code == 200
        assert response.json()['site_id'] == site
        response = client.post('/terrain/horizon', json={'site_id': site, 'observer_x': x, 'observer_y': y,
                                                        'azimuths_deg': [90], 'max_range_m': 30})
        assert response.status_code == 200
        assert response.json()['site_id'] == site
    assert client.get('/terrain/summary?site_id=missing').status_code == 404
    assert client.get('/terrain/site?easting_m=1').status_code == 422
    sites['Site11']._loaded = False
    (sites['Site11'].raw_dir / ('Site11' + LOLA_CORE_PRODUCTS['slope'])).unlink()
    assert client.get('/terrain/summary?site_id=Site11').status_code == 503


def test_incomplete_and_wrong_site(tmp_path):
    raw = source_suite(tmp_path, 'Site11', (20, 24), Affine(5, 0, 1, 0, -5, 200), 0)
    with pytest.raises(FileNotFoundError):
        load_site_dataset(raw, 'Site23')
    (raw / ('Site11' + LOLA_CORE_PRODUCTS['slope'])).unlink()
    with pytest.raises(FileNotFoundError):
        load_site_dataset(raw, 'Site11')
    with pytest.raises(UnknownSiteError):
        TerrainService(site_id='../Site04')


def test_misaligned_layer_and_checksum_association(tmp_path):
    raw = source_suite(tmp_path, 'Site11', (20, 24), Affine(5, 0, 1, 0, -5, 200), 0)
    dataset = load_site_dataset(raw, 'Site11', True)
    assert np.isnan(dataset.elevation.data[0, 0])
    assert dataset.observation_count.data[1, 0] == 0
    require_compatible_grid(dataset)
    manifest = {'sites': {'Site11': {'products': {k: {'sha256': r.metadata.sha256_hash} for k, r in dataset.rasters.items()}}}}
    (tmp_path / 'download_manifest.json').write_text(json.dumps(manifest))
    verify_source_association(dataset, tmp_path)
    manifest['sites']['Site11']['products']['slope']['sha256'] = dataset.elevation.metadata.sha256_hash
    (tmp_path / 'download_manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='association'):
        verify_source_association(dataset, tmp_path)
    with rasterio.open(raw / ('Site11' + LOLA_CORE_PRODUCTS['slope']), 'r+') as dst:
        dst.transform = Affine(5, 0, 6, 0, -5, 200)
    with pytest.raises(ValueError, match='grid'):
        require_compatible_grid(load_site_dataset(raw, 'Site11'))


def test_service_cache_isolation(monkeypatch):
    monkeypatch.setattr(TerrainService, '_instance', None)
    monkeypatch.setattr(TerrainService, '_instances', {})
    first = TerrainService.get_instance('Site11')
    assert TerrainService.get_instance('Site11') is first
    assert TerrainService.get_instance('Site23') is not first
    assert TerrainService.get_instance().site_id == 'Site04'


def test_known_roughness_survives_missing_slope(sites):
    service = sites['Site11']
    for key, code in [('slope', 0), ('roughness_small', 3)]:
        with rasterio.open(service.processed_dir / f'Site11_hazard_{key}.tif', 'r+') as src:
            values = src.read(1)
            values[12, 12] = code
            src.write(values, 1)
    service._ensure_loaded()
    point = service.query_point(*(service._transform @ (12.5, 12.5)))
    assert point['hazard_classification']['physical_hazard_code'] == 3


def test_processed_source_association(sites):
    service = sites['Site11']
    with rasterio.open(service.processed_dir / 'Site11_roughness_15m.tif', 'r+') as src:
        src.update_tags(SOURCE_DEM_SHA256='wrong-site-or-stale-dem')
    with pytest.raises(ValueError, match='association'):
        service._ensure_loaded()
