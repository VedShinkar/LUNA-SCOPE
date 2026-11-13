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
