# LUNA-SCOPE Terrain Data Guide

This guide records the terrain datasets selected for the first LUNA-SCOPE comparison workflow. It explains what each file is, why we need it, where it belongs, and what it cannot tell us.

## 1. Primary terrain regions

| PGDA code | Region | LUNA-SCOPE role | Priority |
|---|---|---|---|
| `Site04` | Shackleton rim | First end-to-end development region | P0 |
| `Site11` | de Gerlache rim | Comparison region | P1 |
| `Site23` | Malapert Massif | Comparison region | P1 |

These are separate regional products. Do not assume they have identical footprints or that a coordinate inside one region is covered by another.

**Primary archive:** https://pgda.gsfc.nasa.gov/products/78  
**Data directory index:** https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/

PGDA identifies the products as 5 m/pixel GeoTIFFs, using south-polar stereographic X/Y coordinates in metres and the `MOON_ME` reference frame associated with ephemeris DE421. Verify the exact raster metadata and product README after download.

## 2. Core LOLA files — download these for all three regions

The downloader retrieves five co-registered rasters per selected site.

| Product | Filename pattern | Meaning | Why LUNA-SCOPE needs it |
|---|---|---|---|
| LDEM / surface elevation | `{SITE}_final_adj_5mpp_surf.tif` | Surface-interpolated elevation, metres | Base terrain mesh, elevation queries, slope/horizon calculations |
| LDEC / observation count | `{SITE}_final_adj_5mpp_ldec.tif` | Number of LOLA spots contributing to each pixel | Shows measurement support; helps identify sparse/interpolated areas |
| Slope | `{SITE}_final_adj_5mpp_slp.tif` | Slope in degrees | Landing/traverse screening and validation of our independently computed slope |
| Total Z uncertainty | `{SITE}_final_adj_5mpp_toterr.tif` | RMS elevation uncertainty, metres | Carries vertical uncertainty into terrain/horizon assessments |
| Slope uncertainty | `{SITE}_final_adj_5mpp_slperr.tif` | RMS slope uncertainty, degrees | Indicates confidence in slope-derived decisions |

**Scientific caution:** 5 m/pixel is the raster grid spacing, not a guarantee of independent 5 m laser measurements. The PGDA product description reports that a large fraction of the polar LDEM pixels are interpolated because LOLA track spacing is wider than the raster grid. Always use LDEC and uncertainty layers when interpreting fine-scale features.

## 3. Supporting LOLA products — retained in the acquisition plan

These are real parts of the PGDA product suite, but they are not needed for the first working DEM pipeline. Download them when the relevant analysis is ready.

### 3.1 XYZI point cloud (`{SITE}_final_adj.xyzi`) — optional, potentially large

- Four binary double-precision columns: X, Y, Z and ID, according to the PGDA product description.
- X/Y are south-polar stereographic coordinates in metres; Z is surface height in metres; ID identifies the LOLA RDR.
- Useful for inspecting the underlying altimetry samples, track density, and how interpolated raster cells relate to observations.
- Not required for basic raster visualisation because LDEC already provides a per-pixel observation-count layer.
- Enable with `--include-point-clouds`.

### 3.2 DEM error-realisation clones — optional, large ensemble

- PGDA lists 100 clones for the regional products.
- The Site04 links use the path `Clones/{SITE}_final_adj_5mpp_0001_err.tif` through `0100_err.tif` (same naming pattern for the selected sites).
- These are alternative DEM realisations used to study uncertainty in height, slope and illumination.
- They are valuable for uncertainty propagation, for example running horizon/illumination calculations over multiple plausible terrain realisations.
- They are not 100 independent new terrain surveys and should not be averaged blindly into a new DEM.
- Enable with `--include-clones`. This can multiply download volume substantially; do not run it until disk space and processing needs are understood.

### 3.3 ROI GIS shapefiles — ancillary

- PGDA Product 78 lists `Site04_ROIs.tgz` and `Site11_ROIs.tgz`.
- These contain GIS shapefiles defining regions of interest used in the source study.
- Useful for reproducing study-area summaries and masking/identifying named subregions.
- The Product 78 page does not list a `Site23_ROIs.tgz` entry; the downloader records that rather than inventing a file.
- ROI archives are attempted by default for sites where listed.

## 4. Complementary terrain products to evaluate after the LOLA baseline

### 4.1 NASA PGDA Shape-from-Shading DEM products (SDEM)

Source: https://pgda.gsfc.nasa.gov/products/104  
Archive: https://doi.org/10.5281/zenodo.17954508

The 2025 SDEM product family combines LOLA geodetic control with LROC Narrow Angle Camera (NAC) images and shape-from-shading reconstruction. The archive includes elevation rasters, hillshades, maximum-illumination orthomosaics, image-coverage and solar-bin counts, best-input-resolution maps, SDEM-minus-LDEM difference maps, multi-baseline slope and roughness products, and processing ancillary files.

Why it matters:
- Can add shorter-scale terrain detail where LOLA tracks are sparse.
- Provides independent/complementary terrain products for slope and roughness work.
- Image coverage and illumination conditions vary; do not assume every pixel has the same reconstruction quality.
- Before using an SDEM for a LUNA-SCOPE site, confirm that the exact archive region spatially overlaps our Site04/Site11/Site23 area and that its coordinate frame, grid, vertical reference and product metadata can be reconciled with the LOLA DEM.
- Treat it as a complementary validation/enhancement dataset, not an automatic replacement for the baseline LOLA DEM.

### 4.2 LROC NAC imagery

Discovery and product access:
- https://www.lroc.asu.edu/
- https://pds-imaging.jpl.nasa.gov/

Use for visual context and, where image resolution/coverage/illumination permit, inspection of small craters, boulders and local surface features. Record the exact NAC product ID, pixel scale, acquisition geometry, incidence/emission angles, map projection and registration method. A rendered QuickMap/Moon Trek tile or screenshot is not a substitute for a calibrated image product.

### 4.3 LROC QuickMap and NASA Moon Trek

- QuickMap: https://quickmap.lroc.asu.edu/
- Moon Trek: https://trek.nasa.gov/moon/
- Moon Trek tile API documentation: https://trek.nasa.gov/tiles/apidoc/

Use these for discovery, visual cross-checks and map context. Do not use rendered map tiles as numeric elevation inputs unless a documented downloadable scientific product is explicitly obtained.

## 5. Datasets outside the terrain module

These belong to other LUNA-SCOPE workstreams and should not be duplicated into the terrain download folder.

| Dataset/service | Owner/use | Why it is separate |
|---|---|---|
| NAIF SPICE kernels | Anushka: ephemerides, lunar orientation, Sun/Earth vectors | Time-dependent celestial geometry, not terrain |
| JPL Horizons | Anushka: independent ephemeris validation | Reference service, not a terrain raster |
| Diviner thermal products | Thermal/environment workstream | Surface temperature context, not topography |
| Mission/equipment profiles | Mahati: mission feasibility and scoring | User-defined engineering assumptions, not measured terrain |

## 6. Local folder layout

```text
data/
├── raw/
│   └── terrain/
│       ├── site04/
│       ├── site11/
│       └── site23/
├── processed/
│   └── terrain/
│       ├── site04/
│       ├── site11/
│       └── site23/
└── metadata/
    └── terrain/
        ├── download_manifest.json
        ├── site04_inspection.json
        ├── site11_inspection.json
        └── site23_inspection.json
```

Keep raw NASA files unchanged. Put reprojected/cropped/derived rasters in `data/processed/terrain/`. The repository `.gitignore` intentionally excludes raw and processed scientific data. Do not force-add large rasters to Git.

## 7. Download instructions

From the LUNA-SCOPE repository root:

```powershell
python scripts/download_lola_terrain.py
```

This downloads the five core rasters for Site04, Site11 and Site23, plus ROI archives where listed.

Optional point clouds:

```powershell
python scripts/download_lola_terrain.py --include-point-clouds
```

Optional 100-clone uncertainty ensemble:

```powershell
python scripts/download_lola_terrain.py --include-clones
```

To download only Shackleton:

```powershell
python scripts/download_lola_terrain.py --sites Site04
```

The script writes a SHA-256 manifest to `data/metadata/terrain/download_manifest.json`. Re-running it skips already valid files and retries incomplete downloads.

Inspect Shackleton after downloading:

```powershell
pip install rasterio numpy
python scripts/inspect_lola_site.py --site Site04
```

## 8. What counts as complete?

For the first terrain milestone, Site04 is complete when:
- The five core rasters are downloaded and pass file validation.
- A local SHA-256 manifest is written.
- Raster CRS, dimensions, transform, bounds, NoData and units are inspected.
- The five rasters' grids are checked for alignment.
- The exact PGDA product metadata and assumptions are recorded.
- A first elevation visualisation can be generated from the actual DEM.

Site11 and Site23 are comparison regions. Download their five core rasters before cross-site analysis, but finish and validate the Site04 pipeline first.

## 9. References and citation

- Barker, M. K. et al. (2021), *Improved LOLA Elevation Maps for South Pole Landing Sites: Error Estimates and Their Impact on Illumination Conditions*, Planetary and Space Science, 203, 105119. https://doi.org/10.1016/j.pss.2020.105119
- Mazarico, E. et al. (2011), *Illumination conditions of the lunar polar regions using LOLA topography*, Icarus, 211(2), 1066–1081. https://doi.org/10.1016/j.icarus.2010.10.030
- Bertone, S. et al. (2025), *Enhanced Topography Models for selected Lunar South Pole regions with Shape-from-Shading*, The Planetary Science Journal. https://doi.org/10.3847/PSJ/ae5b70
- NASA GSFC PGDA, *High-Resolution LOLA Topography for Lunar South Pole Sites*, Product 78: https://pgda.gsfc.nasa.gov/products/78
- NASA GSFC PGDA, *Enhanced Topography Models ... with Shape-from-Shading*, Product 104: https://pgda.gsfc.nasa.gov/products/104

## Multi-site execution

Run `python scripts/download_lola_terrain.py --sites Site11 Site23 --skip-roi`, then `python scripts/process_lola_sites.py --sites Site04 Site11 Site23`. The second command stops each site at any failed prerequisite and records the error without inventing products. Sources remain under `data/raw/terrain/<site>/`; outputs remain under `data/processed/terrain/<site>/`. Per-site metadata and `multisite_comparison.json` are under `data/metadata/terrain/`. Use only reports marked PROCESSED. Native grids may differ across sites. See [Phase 5](PHASE5_IMPLEMENTATION.md).
