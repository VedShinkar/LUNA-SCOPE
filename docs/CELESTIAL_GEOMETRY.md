# Phase 3.1 Celestial Geometry Observatory

The existing observatory provided terrain grids, picking and a celestial workspace shell. The backend included a SpiceyPy dependency and an ephemeris module stub. The implementation adds a SPICE engine and connects the existing workspace and terrain renderer to it. Phase 1 and Phase 2 endpoints and terrain calculations retain their existing contracts.

## Observer and local reference frame

PGDA product 78 specifies south-polar stereographic coordinates in the DE421 Mean Earth frame. The observer resolver uses the site's existing processed LOLA elevation, verifies its spherical datum, units and frame tags, and reports the raw product URL and recorded source SHA-256. The default point is the exact raster centre used in the survey. Its coordinates agree with NASA's Lunar Surface Data Book to the published precision.

| Site | Planetocentric latitude (°) | East-positive longitude (°) | Height (m) |
| --- | ---: | ---: | ---: |
| Site04 Shackleton Rim | −89.76681145 | −171.86989765 | 767.97864 |
| Site11 de Gerlache Rim | −88.68341815 | −67.93210044 | 1793.66443 |
| Site23 Malapert Massif | −85.99478468 | −0.23578377 | 4783.62939 |

For a selected terrain point, the full raster affine locates the containing native cell, using the raster library's half-open pixel indexing. The projected coordinates of the selected point determine its latitude and longitude. The cell gives radial height above the 1,737,400 m reference sphere with no interpolation. Out-of-raster and masked or nonfinite samples fail explicitly. The observer uses surface height with no added instrument height. Terrain previews are decimated, so the rendered surface and native-height marker may differ slightly near steep features.

## Frames, vectors and time

1. Convert input UTC into SPICE ET, measured in TDB seconds past J2000. Inputs require seconds and either `Z` or `+00:00`, with optional microseconds. Pre-1972 calendar times use SPICE's extrapolated UTC convention. Future times use the loaded leap-second kernel. The API cannot express an inserted leap second using the `:60` notation, and series increment civil UTC timestamps.
2. Take the position of the observer relative to the Moon centre in `MOON_ME_DE440_ME421`. The radius equals 1,737.4 km plus the native LOLA height in kilometres. NAIF's frame kernel aligns this DE440 Mean Earth realization to the DE421 Mean Earth axes. The static alignment preserves the terrain longitude/latitude convention while the orientation uses the DE440 binary PCK.
3. SPICE `spkcpo` returns the Sun or Earth centre relative to this fixed observer in J2000/ICRF. `CN+S` applies converged one-way reception light-time and stellar aberration. `pxform` rotates the resulting direction into the lunar body-fixed frame at the observer epoch.
4. Project the body-fixed unit vector onto east, north and radial up at the observer. For latitude `φ` and longitude `λ`, the row vectors are `(-sin λ, cos λ, 0)`, `(-sin φ cos λ, -sin φ sin λ, cos φ)`, and `(cos φ cos λ, cos φ sin λ, sin φ)`. Azimuth is `atan2(east,north)` clockwise from true north and normalized to [0°,360°). Elevation is `atan2(up,hypot(east,north))` above the local radial horizontal plane. Azimuth is undefined at zenith and nadir.
5. Angular diameter is `2 asin(equatorial radius / observer–target range)`, using the PCK equatorial radius and a spherical disk. The sky chart uses the returned angles. The terrain arrows rotate the returned local unit vectors into the south-polar stereographic grid axes, accounting for convergence. The horizontal ring and rays are directional guides. Their display size is arbitrary.

This model omits refraction, relativistic deflection, limb visibility and terrain obstruction. Centre elevation, including a positive sign, never establishes direct illumination or a communications window. The API provides provenance and quality flags. Formal per-result angular uncertainty is unavailable.

## Kernel inventory and setup

Run `python scripts/download_spice_kernels.py` in the project environment. Kernels are stored under the Git-ignored `data/cache/ephemeris/`. The downloader and runtime both compare SHA-256 against the pins in [kernels.py](../backend/app/scientific_engines/ephemeris/kernels.py). To use a different cache, pass `--directory` when downloading and set `LUNA_SPICE_KERNEL_DIR` before launching the API. Each worker loads and verifies its kernel pool once. Missing or mismatched inputs return HTTP 503 for computations.

| Kernel | Use |
| --- | --- |
| [de440s.bsp](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp) | Short DE440 Sun, Earth, Moon and Earth–Moon barycentre ephemerides |
| [moon_pa_de440_200625.bpc](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc) | DE440 lunar principal-axis orientation |
| [moon_de440_250416.tf](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf) | Lunar frame definitions and DE421 Mean Earth alignment |
| [naif0012.tls](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls) | UTC and leap-second conversion |
| [pck00011.tpc](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc) | Target equatorial radii |

The raw DE440s trajectory coverage runs from 1849-12-26 through 2150-01-22, and the binary lunar orientation coverage runs from 1549-12-31 through 2650-01-25. These kernel boundaries are midnight TDB. The frame and constants kernels have no independent time intervals.

API coverage comes from the intersection of the individual SPK coverage windows and the lunar binary PCK window. The resolved coverage with these pins is 1849-12-26 00:19:18.816175 through 2150-01-21 23:58:48.815541 using the loaded UTC convention. It reserves 1,200 seconds at the start for retarded target epochs and two seconds at the end for neighboring states used by SPICE. The coverage tests exercise both published endpoints and just outside each.

## HTTP interface

| Path under `/terrain/explorer/celestial` | Input and result |
| --- | --- |
| `GET /metadata` | Site observers, kernel inventory, coverage, conventions and request limits. Missing data is represented as null with an error. |
| `POST /geometry` | `site_id`, `utc`, optional `point` with `easting_m` and `northing_m`. One epoch. |
| `POST /series` | `site_id`, `start_utc`, `end_utc`, `step_seconds` and the same optional point. Returns samples from start through the last increment at or before end. |

Successful calculations include the resolved observer, convention metadata, kernel inventory, flags and up to 241 epochs. Each epoch includes UTC, ET, both body directions, body-fixed XYZ and local ENU unit vectors, distance in km, angular diameter in degrees, one-way light time in seconds and the body centre's relationship to the local horizontal. Series accept integer increments from 60 to 604,800 seconds. HTTP 404 identifies an unsupported site, 422 an invalid timestamp, range or point, and 503 unavailable scientific inputs. Exact schemas are available in FastAPI's OpenAPI documentation.

## Independent JPL Horizons validation

Six live Horizons queries covered both bodies at each site. Each query returned three epochs. The [reference fixture](../tests/scientific_validation/fixtures/celestial_horizons.json) records the requests, Horizons observer headers, reference values and residuals from 2026-11-15 UTC. Run `python scripts/validate_celestial_horizons.py` to reproduce the live check.

Epochs were 2025-06-21 12:00:00 UTC, 2026-01-01 00:00:00 UTC and 2026-01-15 06:00:00 UTC. The Horizons headers reported DE441 trajectories, a high-precision Mean Earth observer and a 1,737.4 km sphere. The queries used the same surface height, east-positive longitude, UTC, airless apparent body-centre azimuth and elevation, and equatorial disk diameter. Horizons includes relativistic light bending. SPICE CN+S in this application omits it.

| Absolute maximum in arcsec | Sun, 9 cases | Earth, 9 cases |
| --- | ---: | ---: |
| Wrapped azimuth difference | 0.0000164 | 0.0019352 |
| Elevation difference | 0.00000261 | 0.00015945 |
| Great-circle separation | 0.0000164 | 0.00190543 |
| Equatorial diameter difference | 0.000461 | 0.000484 |

The regression limits are 2 arcsec for direction separation and each angle, and 0.01 arcsec for diameter. These are engineering checks for the sampled geometry. The angle budget allows for comparing different ephemeris releases and models, including the roughly 1.75 arcsec scale of solar-limb light deflection. The sampled bodies are near the horizontal, where azimuth is well conditioned. The disk budget is ten times Horizons' 0.001 arcsec output increment. Neither limit bounds errors at untested epochs or certifies terrain visibility.

[NASA PGDA product 78](https://pgda.gsfc.nasa.gov/products/78) · [NASA Lunar Surface Data Book](https://ntrs.nasa.gov/citations/20250002845) · [NAIF SPKCPO reference](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/spkcpo_c.html) · [JPL Horizons manual](https://ssd.jpl.nasa.gov/horizons/manual.html)
