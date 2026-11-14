# Phase 5: multi-site terrain intelligence

## Audit and scope

The initial checkout contained uncommitted explorer/frontend work, including edits to
`backend/app/api/routes/terrain.py` and `backend/app/models/terrain.py`. Those changes
were preserved. No frontend implementation is part of Phase 5.

The existing catalog already identified Site04 (Shackleton rim), Site11 (de Gerlache
rim), and Site23 (Malapert massif). These identities were checked against
[NASA PGDA Product 78](https://pgda.gsfc.nasa.gov/products/78), rather than inferred
from identifiers. Initially only Site04's five sources and derived products existed.

Audited components: `loader.py`, `validation.py`, `elevation.py`, `slope.py`,
`aspect.py`, `roughness.py`, `uncertainty.py`, `hazards.py`, `pipeline.py`, `horizon.py`,
`service.py`, terrain models/routes, acquisition/inspection scripts, catalog,
Phase 1–3 reports, API contracts, and unit/API/scientific tests. Dependencies remain
NumPy, SciPy, Rasterio, PyProj, FastAPI/Pydantic and pytest. Matplotlib is optional.

## Implemented behavior

`catalog.py` resolves repository-relative paths and rejects unknown site IDs.
`TerrainService.get_instance(site_id="Site04")` caches isolated instances under a
lock; loading is also locked. Explicit constructor directories remain supported
for offline fixtures. Production loading verifies every source checksum against
the acquisition manifest. Sources must use the selected site's filenames and
compatible native grids. Derived grids are checked against the site's DEM; newly
generated products carry its SHA-256. Reports must identify the selected site.

The service requires all sources and its derived products rather than returning
incomplete placeholders. Missing/unreadable/misassociated products yield HTTP 503;
unknown site IDs yield 404. Site04 remains the omitted-ID default. POST point and
horizon bodies add optional `site_id`; GET site/summary already had this parameter.
Point responses include the established hazard inspection. Existing explorer
endpoints remain explicitly scoped to Site04 and were not generalized in this phase.

`scripts/process_lola_sites.py` gates processing on source association and Phase 1,
runs the existing Phase 2 and Phase 3 functions, validates output grids/value domains,
and exercises real point/horizon queries. Sites are processed sequentially. Phase 3
reuses newly generated, checksum-associated roughness rasters and retains NASA SLP
as its slope indicator, preserving the established decisional policy and thresholds.

Original files stay in `data/raw/terrain/<site>/`. Terrain and hazard GeoTIFFs stay
in `data/processed/terrain/<site>/`, separated by the existing filename conventions.
Metadata/reports stay in `data/metadata/terrain/`. No parallel data tree was added.

## Small justified corrections

- Source masks/finite NoData sentinels become NaN only in analysis memory. Original
  bytes and georeferencing are unchanged; valid LDEC zero is retained.
- Grid compatibility compares geometry, not numeric dtype: an integer count raster
  can share a grid with a floating elevation raster.
- Phase 1 no longer requires 100% populated elevation or unequal validity/observation
  masks. It checks disjoint support categories; missing observation support is explicit.
  LDEC histograms exclude missing counts, and empty uncertainty subsets report null.
- Removed Site04-specific coverage percentages and geographic labels from reusable
  reports. Software versions are read from the actual runtime.
- Terrain GeoTIFF blocks use valid TIFF block sizes for small/non-multiple dimensions.
  Slope/aspect tags now say degrees, matching existing numeric values and filenames.
- Physical summaries/point inspection retain known MODERATE/HIGH evidence when
  another physical indicator is missing, matching the unchanged Option B combiner.
  Point inspection reads persisted physical indicators rather than reconstructing
  them using a different slope source and duplicated thresholds.
- Phase 3 diagnostic rendering now imports Rasterio explicitly.

## Reproduction

From the repository root (PowerShell):

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe -u scripts/download_lola_terrain.py --sites Site11 Site23 --skip-roi
.venv/Scripts/python.exe -u scripts/process_lola_sites.py --sites Site04 Site11 Site23
.venv/Scripts/python.exe -m pytest tests/unit tests/api tests/scientific_validation -q
```

The downloader retains previous manifest entries and records UTC acquisition times
for newly downloaded files. Existing Site04 acquisition timestamps were not retained
by the old downloader: they remain unknown, distinct from validation timestamps.
Local SHA-256 establishes file identity, not an independently published NASA checksum.

## Evidence and limits

Per-site `*_phase5_report.json` includes identity, acquisition provenance, raster
metadata, densified geographic bounds in the source lunar geodetic CRS, Phase 1
validation, terrain distributions/comparison, hazard counts/percentages, configuration,
output validation, representative point/horizon results, elapsed time and status.
`multisite_comparison.json` collates actual reports and never ranks mission safety.

The first Site04 rerun took 71.581 seconds. All 16 existing derived raster value
arrays matched byte-for-byte; container metadata changes are intentional. Its slope
comparison MAE was 0.001155 degrees and RMSE 0.065393 degrees, with maximum absolute
difference 25.878507 degrees. Aggregate agreement must not conceal local discrepancies.

The horizon algorithm retains Phase 4 behavior, including its existing coordinate
sampling convention, nearest-finite fallback, and skipping unavailable ray samples.
It is a local sampled obstruction estimate, not a guarantee that missing terrain
contains no obstacle. No new ephemeris/illumination or mission feasibility model is
claimed. Analytical synthetic plane tests check geometry independently of NASA;
agreement with NASA SLP is a same-source numerical comparison, not independent lunar
ground-truth validation. Whole-grid comparisons have different footprints/support.

The processing uses full native arrays with sequential sites; it is not an out-of-core
engine. Each service caches its own arrays. Replacing source/derived files requires a
service restart. Raw/processed binary data remain Git-ignored and must be acquired and
processed separately when reproducing a checkout.

## Execution record

Initial tests could not collect four API modules because FastAPI was absent.
Sandboxed dependency/acquisition attempts failed DNS resolution (Errno 11001).
Dependencies and downloads were retried with approved network access. TestClient
then hung in Windows asyncio's socketpair creation inside the sandbox; a 20-second
faulthandler traceback identified that cause. Those runs were interrupted, not
counted as passing. Running the complete suite outside the sandbox completed with
117 passed in 40.62 seconds before the final metadata/physical-summary refinements.
Subsequent verification is recorded with the final execution results.
