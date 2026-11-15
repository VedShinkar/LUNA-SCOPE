"""Reproduce the live Phase 3.1 JPL Horizons cross-check."""
import csv
from datetime import datetime, timezone
import json
from math import atan2, degrees, radians, sin, cos
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.scientific_engines.ephemeris.geometry import geometry_at, utc_datetime
from app.scientific_engines.ephemeris.observer import resolve_observer
from app.scientific_engines.terrain.catalog import list_site_ids

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
EPOCHS = ("2025-06-21T12:00:00Z", "2026-01-01T00:00:00Z", "2026-01-15T06:00:00Z")
ANGLE_LIMIT_ARCSEC = 2
DIAMETER_LIMIT_ARCSEC = 0.01


def query(observer, target):
    settings = {
        "COMMAND": target, "CENTER": "coord@301", "COORD_TYPE": "GEODETIC",
        "SITE_COORD": f"{observer.longitude_deg_east % 360:.12f},{observer.latitude_deg:.12f},{observer.elevation_m / 1000:.12f}",
        "TLIST": " ".join(f"'{time[:-1].replace('T', ' ')}'" for time in EPOCHS),
        "TIME_TYPE": "UT", "EPHEM_TYPE": "OBSERVER", "OBJ_DATA": "NO",
        "APPARENT": "AIRLESS", "QUANTITIES": "4,13", "CSV_FORMAT": "YES", "EXTRA_PREC": "YES",
    }
    parameters = {"format": "json", **{key: f"'{value}'" if key != "TLIST" else value for key, value in settings.items()}}
    url = f"{API}?{urlencode(parameters)}"
    with urlopen(url, timeout=40) as response:
        data = json.load(response)
    if "error" in data:
        raise RuntimeError(data["error"])
    text = data["result"]
    header, table = text.split("$$SOE", 1)
    records = list(csv.reader(table.split("$$EOE", 1)[0].strip().splitlines()))
    if len(records) != len(EPOCHS) or "MEAN_ME (high precision)" not in header or "1737.4, 1737.4, 1737.4" not in header or "NO (AIRLESS)" not in header:
        raise RuntimeError("Horizons response does not match the expected observer or epochs.")
    return url, [line.strip() for line in header.splitlines() if line.startswith(
        ("Target body name", "Center body name", "Center pole/equ", "Center geodetic", "Center radii", "Atmos refraction"))], records


def enu(azimuth_deg, elevation_deg):
    azimuth, elevation = radians(azimuth_deg), radians(elevation_deg)
    return np.array([sin(azimuth) * cos(elevation), cos(azimuth) * cos(elevation), sin(elevation)])


def main():
    comparisons, queries = [], []
    for site in list_site_ids():
        observer = resolve_observer(site)
        for body, target in (("sun", "10"), ("earth", "399")):
            url, lines, records = query(observer, target)
            queries.append({"site_id": site, "target": body, "url": url, "horizons_header": lines})
            for timestamp, record in zip(EPOCHS, records, strict=True):
                actual_time = datetime.strptime(record[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
                if actual_time != utc_datetime(timestamp):
                    raise RuntimeError(f"Horizons returned an unexpected epoch: {record[0]}.")
                azimuth, elevation, diameter = map(float, record[3:6])
                local = geometry_at(observer, actual_time)[body]
                reference = enu(azimuth, elevation)
                direction = local["enu_unit_vector"]
                comparisons.append({
                    "site_id": site, "body": body, "utc": timestamp,
                    "azimuth_deg": azimuth, "elevation_deg": elevation, "diameter_arcsec": diameter,
                    "azimuth_delta_arcsec": ((local["azimuth_deg"] - azimuth + 180) % 360 - 180) * 3600,
                    "elevation_delta_arcsec": (local["elevation_deg"] - elevation) * 3600,
                    "direction_delta_arcsec": degrees(atan2(np.linalg.norm(np.cross(reference, direction)), np.dot(reference, direction))) * 3600,
                    "diameter_delta_arcsec": local["angular_diameter_deg"] * 3600 - diameter,
                })
    print(json.dumps({"retrieved_utc": datetime.now(timezone.utc).isoformat(), "queries": queries, "comparisons": comparisons}, indent=2))
    return int(any(max(abs(case[key]) for key in ("azimuth_delta_arcsec", "elevation_delta_arcsec", "direction_delta_arcsec")) > ANGLE_LIMIT_ARCSEC or abs(case["diameter_delta_arcsec"]) > DIAMETER_LIMIT_ARCSEC for case in comparisons))


if __name__ == "__main__":
    raise SystemExit(main())
