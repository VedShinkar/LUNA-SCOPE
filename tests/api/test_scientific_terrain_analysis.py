from fastapi.testclient import TestClient
import numpy as np
import pytest
from rasterio.io import MemoryFile

from app.main import app
from app.scientific_engines.terrain.analysis import raster_statistics
from app.scientific_engines.terrain.lunar_context import polar_lonlat


@pytest.mark.parametrize('site_id', ['Site04', 'Site11', 'Site23'])
def test_live_site_statistics_and_profiles(site_id):
    with TestClient(app) as client:
        stats_response = client.get('/terrain/explorer/statistics', params={'site_id': site_id, 'layer': 'slope', 'threshold': 15})
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats['site_id'] == site_id and stats['file'].startswith(site_id)
        assert stats['valid'] + stats['invalid'] == stats['total']
        assert stats['minimum'] <= stats['mean'] <= stats['maximum']
        assert sum(stats['histogram']['counts']) + stats['histogram']['outside'] == stats['valid']
        assert stats['screening']['threshold'] == 15
        assert stats['screening']['within'] + stats['screening']['exceeds'] == stats['valid']
        west, south, east, north = stats['bounds']
        midpoint = (west + east) / 2, (south + north) / 2
        points = [polar_lonlat(midpoint[0] + shift, midpoint[1]) for shift in (0, 21, 43)]
        result = client.post('/terrain/explorer/cross-section', json={'site_id':site_id,'vertices':[{'longitude':lon,'latitude':lat} for lon,lat in points]})
        assert result.status_code == 200
        profile = result.json()
        assert profile['source_file'].startswith(site_id)
        assert 42 <= profile['distance_m'] <= 43.01
        assert max(np.diff(profile['distance_along_m'])) <= 5.00001
        assert len(profile['coordinates']) == len(profile['elevation_m'])
        assert None not in profile['elevation_m']


def test_native_statistics_intersect_masks():
    with MemoryFile() as dem_file, MemoryFile() as layer_file:
        meta = dict(driver='GTiff', width=2, height=2, count=1, dtype='float32', nodata=-999)
        with dem_file.open(**meta) as dem, layer_file.open(**meta) as layer:
            dem.write(np.array([[1,2],[-999,4]], dtype='float32'), 1)
            layer.write(np.array([[0,-999],[4,2]], dtype='float32'), 1)
            stats = raster_statistics(dem, layer, 'coverage', 'returns')
            screening = raster_statistics(dem, layer, 'roughness', 'm', threshold=0)['screening']
    assert stats['valid'] == 2
    assert stats['invalid'] == 2
    assert stats['mean'] == 1
    assert stats['direct'] == 1
    assert screening == {'threshold': 0, 'within': 1, 'exceeds': 1}
