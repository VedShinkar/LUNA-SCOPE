# Terrain scientific engine

This package owns raster ingestion, terrain-derived measurements and local terrain-horizon products.

## Data source

Use the NASA GSFC PGDA LOLA south-pole regional products documented in:
- `docs/TERRAIN_DATA_GUIDE.md`
- `data/metadata/terrain/dataset_catalog.json`

The first target is Site04 (Shackleton rim), followed by Site11 (de Gerlache rim) and Site23 (Malapert massif).

## Acquisition and inspection

From the repository root:

```powershell
python scripts/download_lola_terrain.py
pip install rasterio numpy
python scripts/inspect_lola_site.py --site Site04
```

Raw downloads are kept under `data/raw/terrain/` and are intentionally excluded from Git. Derived products belong under `data/processed/terrain/`.

## Engineering rules

- Preserve source rasters unchanged.
- Verify CRS, grid transform, dimensions, NoData, units and pixel registration before combining layers.
- Preserve LDEC, elevation uncertainty and slope uncertainty; do not treat every 5 m grid cell as an independent LOLA measurement.
- Keep source elevation and derived products distinct.
- Do not assume a DEM coordinate system is latitude/longitude. The PGDA products use south-polar stereographic X/Y coordinates in metres, in the MOON_ME frame associated with DE421.
- Terrain hazard outputs are screening indicators, not certified landing-safety determinations.
- Local horizon calculations must document observer height, azimuth convention, radial sampling, maximum distance, curvature treatment and DEM coverage.

## Multi-site support

`TerrainService.get_instance("Site11")` selects a catalog site; Site04 remains the default. `scripts/process_lola_sites.py` orchestrates the existing validation and computation functions for each configured site. Source association uses the acquisition manifest and derived grids preserve the site's own transform and lunar CRS. See `docs/PHASE5_IMPLEMENTATION.md` and `docs/api_terrain.md`.
