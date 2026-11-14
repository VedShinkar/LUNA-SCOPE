# Terrain Intelligence API (Phase 4)

This document describes the public HTTP endpoints that expose validated Site04 terrain data.
It follows the contract defined in **docs/API_CONTRACTS.md** and is meant for downstream
celestial‑ and mission‑intelligence modules.

---

## Base URL
All routes are prefixed with `/terrain`.
The service is served by the FastAPI application defined in `backend/app/main.py`.

### 1. `GET /terrain/site`
**Purpose**: Return either a site‑level summary or a point‑level terrain query.

**Query parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| `site_id` | `string` (default: `"Site04"`) | Landing‑site identifier (only `Site04` is supported). |
| `easting_m` | `float` (optional) | Projected Easting in metres (Lunar South‑Polar Stereographic). |
| `northing_m` | `float` (optional) | Projected Northing in metres. |
| `include` | `list[string]` (optional) | Names of additional products to embed (e.g., `elevation`, `slope`, `roughness`, `horizon`). |

**Responses**
- **Site summary** (no coordinates supplied):
  ```json
  {
    "site_id": "Site04",
    "site_name": "Shackleton Crater Rim",
    "region": "Lunar South Pole",
    "coordinate_system": { ... },
    "spatial_grid": { ... },
    "elevation_summary": { ... },
    "slope_summary": { ... },
    "roughness_summary": { ... },
    "epistemic_quality_and_observation": { ... },
    "hazard_screening_summary": { ... },
    "data_provenance": { ... },
    "scientific_limitations": [ ... ]
  }
  ```
- **Point query** (coordinates supplied):
  ```json
  {
    "site_id": "Site04",
    "coordinates": {
      "easting_m": 12345.0,
      "northing_m": -54321.0,
      "coordinate_system": "Lunar South-Polar Stereographic",
      "reference_frame": "MOON_ME associated with DE421 ephemeris",
      "units": "metre"
    },
    "within_bounds": true,
    "is_valid": true,
    "raster_indices": {"col": 256, "row": 128},
    "elevation_m": 1234.567,
    "slope_deg": 7.89,
    "aspect_deg": 45.0,
    "aspect_description": "Clockwise from grid North (+Y Northing). Flat terrain coded as -1.0.",
    "roughness": {
      "roughness_15m_m": 0.31,
      "roughness_35m_m": 0.78,
      "roughness_75m_m": 1.45,
      "scale_classification": "provisional_analytical_scales",
      "metric": "unbiased_sample_elevation_standard_deviation_ddof1"
    },
    "hazard_classification": {
      "physical_hazard_class": "MODERATE",
      "physical_hazard_code": 2,
      "epistemic_quality_class": "HIGH",
      "epistemic_quality_code": 3,
      "combined_screening_class": "MODERATE",
      "combined_screening_code": 2,
      "policy": "Option B: Decoupled Decisional Screening"
    },
    "uncertainty_and_observation": {
      "lola_observation_count": 0,
      "elevation_uncertainty_m_rms": 0.12,
      "slope_uncertainty_deg_rms": 0.34,
      "is_interpolated": true,
      "is_direct_observation": false
    },
    "provenance": { ... }
  }
  ```

### 2. `POST /terrain/point`
**Purpose**: Same as the point query above but uses a JSON body.

**Request body** (`TerrainPointQueryRequest`)
```json
{ "easting_m": 12345.0, "northing_m": -54321.0 }
```
**Response** – identical to the point‑query payload of `GET /terrain/site`.

### 3. `POST /terrain/horizon`
**Purpose**: Compute a 360° local terrain‑horizon profile for an observer.

**Request body** (`TerrainHorizonRequest`)
```json
{
  "observer_x": 12345.0,
  "observer_y": -54321.0,
  "azimuth_step_deg": 1.0,          // default 1° sampling
  "azimuths_deg": null,             // optional explicit list
  "observer_height_m": 2.0,         // sensor height above ground
  "max_range_m": 5000.0,            // radial search limit
  "sample_interval_m": 5.0,         // step along each ray (matches DEM resolution)
  "include_curvature": true        // apply lunar spherical curvature correction
}
```
**Response** (`TerrainHorizonResponse`)
```json
{
  "status": "SUCCESS",
  "is_valid": true,
  "site_id": "Site04",
  "observer_coordinates": {"easting_m": 12345.0, "northing_m": -54321.0, "coordinate_system": "Lunar South-Polar Stereographic", "reference_frame": "MOON_ME associated with DE421 ephemeris"},
  "observer_ground_elevation_m": 124.5,
  "observer_height_m": 2.0,
  "observer_eye_elevation_m": 126.5,
  "azimuth_convention": "Degrees clockwise from grid North (+Y Northing axis): 0=North, 90=East, 180=South, 270=West. Elevation angle in degrees above local horizontal tangent plane.",
  "max_range_m": 5000.0,
  "sample_interval_m": 5.0,
  "spherical_curvature_corrected": true,
  "lunar_radius_m": 1737400.0,
  "azimuths_deg": [0,1,2,...,359],
  "horizon_angles_deg": [0.0,0.0,0.1,...],
  "horizon_distances_m": [5000,5000,5000,...],
  "horizon_obstacle_elevations_m": [124.5,124.5,125.0,...],
  "summary_statistics": {
    "min_elevation_angle_deg": 0.0,
    "max_elevation_angle_deg": 12.3,
    "mean_elevation_angle_deg": 2.4,
    "median_elevation_angle_deg": 2.0,
    "valid_azimuth_count": 360,
    "total_azimuth_count": 360
  },
  "scientific_limitations": [
    "This interface computes geometric terrain obstruction angles from the 5m LOLA DEM.",
    "This is NOT a solar or Earth visibility calculation; ephemeris and celestial body angular diameter belongs to the celestial module.",
    "Obstructions beyond max_range_m or outside the DEM bounding box are truncated at raster boundaries.",
    "Sub‑pixel micro‑topography (<5 m) and boulders are unresolved by the DEM."
  ]
}
```
**Key geometry notes**
- **Azimuth convention** – degrees clockwise from grid North (`+Y` axis). 0 = North, 90 = East.
- **Distance units** – metres, matching the DEM pixel spacing.
- **Lunar curvature** – optional spherical correction using a radius of 1 737 400 m (`include_curvature=true`). The curvature drop is `d²/(2 R)` where `d` is the ray distance.
- **NoData handling** – rays that encounter a NoData pixel are discarded; the profile reports `null` for that azimuth and a `ray_exit_reason` of `nodata_encountered`.
- **Termination** – a ray stops when the maximum range is reached, the raster boundary is crossed, or no further valid samples exist.

### 4. `GET /terrain/summary`
**Purpose**: Shortcut to retrieve the full site‑level summary (same payload as the summary part of `GET /terrain/site`).

---

## Coordinate System & Units
- **Projection**: Lunar South‑Polar Stereographic (meters).
- **Axes**: `+X` – Easting, `+Y` – Northing (grid row index increases Southward).
- **Units**: All linear quantities are in metres; angular quantities are in degrees.
- **NoData**: Represented as `null` in JSON responses. The raster uses a dedicated NoData value (e.g., 255) which is masked to `NaN` internally.

## Limitations & Caveats
- The horizon profile is purely geometric; it does **not** include solar or Earth visibility calculations – those belong to the celestial module.
- The DEM resolution (5 m) limits detectable features; sub‑pixel obstacles are omitted.
- Curvature correction assumes a perfect sphere; local lunar topography deviations are not modeled.
- Hazard classifications follow **Option B: Decoupled Decisional Screening** – physical hazard, epistemic quality, and combined screening are reported separately.

---

### Example Python client (using `requests`)
```python
import requests
BASE = "http://localhost:8000"
# Point query
payload = {"easting_m": 12345.0, "northing_m": -54321.0}
resp = requests.post(f"{BASE}/terrain/point", json=payload)
print(resp.json())
# Horizon profile
horizon_payload = {
    "observer_x": 12345.0,
    "observer_y": -54321.0,
    "azimuth_step_deg": 5,
    "observer_height_m": 2.0,
    "include_curvature": True,
}
resp = requests.post(f"{BASE}/terrain/horizon", json=horizon_payload)
print(resp.json())
```

---

*This document is maintained in the repository at `docs/api_terrain.md` and should be updated whenever the API contract changes.*
