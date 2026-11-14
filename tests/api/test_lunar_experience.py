from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from pyproj import Proj

from app.main import app
from app.scientific_engines.terrain.lunar_context import CACHE, RADIUS, open_polar, polar_lonlat, polar_xy

client = TestClient(app)


def test_site04_native_window_matches_raster_and_profile():
    url = "/terrain/explorer/grid?max_dimension=32&easting_m=-1000&northing_m=-7000"
    response = client.get(url)
    assert response.status_code == 200
    grid = response.json()
    assert grid["resolution"] == [5, 5]
    assert grid["width"] == grid["height"] == 32
    assert grid["sampling"]["stride"] == 1
    col, row, width, height = grid["sampling"]["window"]
    with rasterio.open(Path("data/processed/terrain/site04/Site04_processed_elevation.tif")) as src:
        window = rasterio.windows.Window(col, row, width, height)
        assert grid["transform"] == list(src.window_transform(window))[:6]
        np.testing.assert_array_equal(grid["elevation"]["values"], src.read(1, window=window).ravel())
        np.testing.assert_array_equal(grid["valid"], src.read_masks(1, window=window).ravel() != 0)

    site = client.get("/terrain/explorer/context").json()["site04"]
    point = {key: site[key] for key in ("latitude", "longitude")}
    assert polar_xy(point["latitude"], point["longitude"]) == pytest.approx((-1000, -7000))
    # The footprint centre is exactly on a cell boundary. Profile a cell centre
    # so the expected nearest sample does not depend on a floating point tie.
    longitude, latitude = polar_lonlat(-997.5, -7002.5)
    point = {"longitude": longitude, "latitude": latitude}
    profile = client.post("/terrain/explorer/profile", json={"start": point, "end": point, "level": "site04"}).json()
    assert profile["distance_m"] == 0
    assert len(profile["elevation_m"]) == 128
    assert profile["elevation_m"][0] == grid["elevation"]["values"][16 * 32 + 16]
    assert client.get("/terrain/explorer/grid?easting_m=-1000").status_code == 422
    assert client.get("/terrain/explorer/grid?easting_m=9000&northing_m=-7000").status_code == 422


def test_global_and_regional_products_use_documented_registration():
    if not (CACHE / "ldem_4.tif").is_file() or not (CACHE / "ldem_85s_40m.img").is_file():
        pytest.skip("Download the NASA datasets with scripts/download_lunar_experience.py.")
    global_response = client.get("/terrain/explorer/moon/elevation")
    assert global_response.status_code == 200
    values = np.frombuffer(global_response.content, dtype="<f4").reshape(720, 1440)
    assert values.min() == pytest.approx(-8878.5)
    assert values.max() == pytest.approx(10504.001)
    assert client.get("/terrain/explorer/moon/albedo").headers["content-type"] == "image/jpeg"

    with open_polar() as source:
        lon, lat = -171.86989764584402, -89.76681145215035
        assert polar_xy(lat, lon) == pytest.approx(Proj(source.crs)(lon, lat))
        for detail, step in (("overview", 640), ("approach", 160)):
            grid = client.get(f"/terrain/explorer/polar?detail={detail}").json()
            assert grid["resolution"] == [step, step]
            assert grid["source_nodata"] == -32768
            transform = rasterio.Affine(*grid["transform"])
            x, y = transform @ (24.5, 11.5)
            row, col = source.index(x, y)
            assert source.xy(row, col) == (x, y)
            height = next(source.sample([(x, y)]))[0] * 0.5
            assert grid["elevation"]["values"][11 * grid["width"] + 24] == height

    response = client.post("/terrain/explorer/profile", json={
        "start": {"latitude": 0, "longitude": 179},
        "end": {"latitude": 0, "longitude": -179},
        "level": "moon",
    })
    assert response.status_code == 200
    assert response.json()["distance_m"] == pytest.approx(np.radians(2) * RADIUS)
