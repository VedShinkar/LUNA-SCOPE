# Data Sources & Acquisition Register

This register records the preferred source for each data type and the role it plays in the first LUNA-SCOPE vertical slice. Product identifiers, exact coverage, resolution, coordinate reference system, vertical datum and licence/use notes must be filled from the metadata of the exact downloaded product. Do not infer these from a dataset family name.

## Preferred source-selection workflow

| Need | Preferred source | Use in LUNA-SCOPE | Status / cautions |
|---|---|---|---|
| Regional elevation | NASA PGDA / LOLA regional 5 m/pixel DEM products | First real terrain model, beginning with Shackleton rim; then Malapert Massif | Candidate product family selected. Verify exact product, footprint, pixel spacing, CRS, vertical datum, units and nodata before use. 5 m/pixel is product-specific, not a blanket claim for all LOLA data. |
| Terrain discovery | LROC QuickMap | Explore Shackleton and Malapert, identify candidate areas and inspect available layers | Discovery and visual inspection tool; record source product IDs for any data used in analysis. |
| Lunar surface visualization/context | NASA Moon Trek and available WMTS layers | Contextual visualization and candidate-site exploration | Treat rendered map layers as visualization unless a downloadable scientific product and metadata are explicitly identified. |
| High-resolution imagery | LROC NAC products | Surface texture/context and local feature inspection | Check acquisition geometry, illumination, pixel scale, coverage and registration against the selected DEM. |
| Ephemeris reference | NASA JPL Horizons | Independent reference for Sun/Earth position calculations at a documented lunar observer | Record target, observer definition, epoch/time scale, reference frame/plane, corrections and output units for reproducibility. |
| Local ephemeris engine | NAIF SPICE kernels with SpiceyPy | Runtime Sun/Earth vectors, lunar orientation and frame transformations | Pin kernel filenames/versions and coverage. Record LSK, SPK, PCK and frame kernels actually loaded. |
| Thermal context | Diviner Lunar Radiometer Experiment products | Evidence/context for surface thermal environment and model validation | Record exact product, spatial/temporal coverage, calibration/processing level and units. Do not treat a simplified equipment thermal model as a Diviner measurement. |
| Mission context | Canadian Space Agency (CSA) lunar exploration resources | Mission/equipment context and requirements background | Contextual reference; not a substitute for measured terrain or ephemeris data. |
| Other derived layers | NASA PDS and traceable published products | PSR, volatile/resource or supplementary science layers when needed | Add only when the exact product, provenance, resolution and limitations are documented. |

## Initial region order

1. **Shackleton rim:** first target for the initial terrain vertical slice and the first end-to-end demo.
2. **Malapert Massif:** second target for comparative terrain and scenario work.

Do not claim both regions have identical data availability. Confirm product coverage separately.

## First alpha data path

1. Use QuickMap and Moon Trek to discover and inspect candidate terrain.
2. Select and download a suitable Shackleton regional LOLA DEM from PGDA.
3. Inspect the actual raster metadata and generate processed terrain products.
4. Use LROC NAC imagery as supporting context/texture only when coverage and registration are suitable.
5. Use SPICE for Sun/Earth geometry; use Horizons as an independent validation reference.
6. Combine terrain-derived local horizon information with SPICE geometry for terrain obstruction and shadow analysis.
7. Preserve all source metadata and provenance through the mission assessment.

## Data handling requirements

- Store large source DEMs, imagery and SPICE kernels outside Git.
- Keep download/setup scripts, product identifiers, metadata, retrieval dates and checksums in the repository.
- Record processing parameters and software versions.
- Never assume different products share identical projections, datums, resolutions or coordinate conventions.
- Preserve source files unchanged; place derived products in the processed-data area.
- Clearly label source observations, ephemeris-derived values, terrain-derived values, model estimates, synthetic fixtures and user assumptions.


## Terrain dataset selection — confirmed PGDA products

The selected primary source is NASA GSFC PGDA Product 78, **High-Resolution LOLA Topography for Lunar South Pole Sites**:
https://pgda.gsfc.nasa.gov/products/78

The first three comparison regions and their archive identifiers are:
- `Site04` — Shackleton rim (P0)
- `Site11` — de Gerlache rim (P1)
- `Site23` — Malapert massif (P1)

For each site, the core acquisition set is:
1. LDEM surface elevation (`*_surf.tif`, metres): base terrain surface.
2. LDEC observation count (`*_ldec.tif`, LOLA spots/pixel): measurement support and sampling-density context.
3. Slope (`*_slp.tif`, degrees): supplied slope layer and validation reference.
4. Total Z uncertainty (`*_toterr.tif`, metres RMS): vertical uncertainty.
5. Slope uncertainty (`*_slperr.tif`, degrees RMS): slope uncertainty.

The archive also lists adjusted XYZI point clouds, 100 DEM error-realisation clones, and ROI shapefile archives for selected regions. These are documented in `docs/TERRAIN_DATA_GUIDE.md` and `data/metadata/terrain/dataset_catalog.json`. Point clouds and clone ensembles are optional large downloads; they are not omitted from the data plan.

**Interpretation caution:** PGDA states that the rasters are 5 m/pixel GeoTIFFs with south-polar stereographic X/Y coordinates in metres, in the `MOON_ME` reference frame associated with DE421. A 5 m pixel is not necessarily an independent 5 m LOLA observation; preserve and inspect LDEC and uncertainty layers.

## Complementary terrain data

NASA PGDA Product 104 provides Shape-from-Shading DEM products that combine LOLA geodetic control with LROC NAC imagery. The archive includes SDEM elevation, hillshade, orthomosaic, image-coverage/solar-bin counts, best input resolution, SDEM–LDEM differences, slope and roughness products. It is a complementary higher-detail source; verify that the exact regional footprint overlaps our chosen sites and reconcile its CRS/frame/vertical reference before use:
https://pgda.gsfc.nasa.gov/products/104
https://doi.org/10.5281/zenodo.17954508

LROC NAC calibrated imagery remains a separate supporting source for local visual context and potential small-feature inspection. Record exact PDS product IDs and imaging geometry. QuickMap and Moon Trek are discovery/visualisation tools, not replacements for numerical DEMs.

For download commands, file explanations, folder layout and optional products, see `docs/TERRAIN_DATA_GUIDE.md`.

## Phase 5 source provenance

NASA [PGDA Product 78](https://pgda.gsfc.nasa.gov/products/78) explicitly identifies Site04 as Shackleton rim, Site11 as de Gerlache rim, and Site23 as Malapert massif. Each uses its own SURF, LDEC, SLP, TOTERR and SLPERR product URL in the catalog. `download_manifest.json` records exact local SHA-256 identities and new acquisition timestamps; Site04's original download time was not retained and is unknown. `*_phase5_report.json` records embedded metadata, source URLs, native bounds/CRS/transform, units, validation and actual processing status. No reprojection/resampling or terrestrial EPSG substitution is performed. Source values are preserved on disk; source masks are applied in memory. See [execution/provenance limitations](PHASE5_IMPLEMENTATION.md).
