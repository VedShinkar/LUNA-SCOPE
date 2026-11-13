# API Contracts — Team Agreement

These contracts are the first integration target for the alpha vertical slice. They are proposed interface agreements until implemented; do not describe them as live endpoints before code and tests exist.

## Cross-module conventions

The exact lunar coordinate frame, latitude convention, longitude direction/range, altitude datum, body-fixed frame and UTC-to-ET conversion must be finalized in `docs/SCIENTIFIC_METHODOLOGY.md` by Members 1 and 2 before numerical integration.

- API timestamps: ISO 8601 with explicit UTC offset; normalize to UTC at the API boundary.
- SPICE internal time: convert UTC to ET using the loaded LSK; return the input epoch and conversion/provenance metadata.
- Distances: metres unless explicitly declared otherwise.
- Angles: include units in field names or schema metadata; never infer degrees vs radians.
- Power: watts; energy: watt-hours or joules, explicitly stated.
- Missing/unknown data: `null` plus a reason/status; never silently substitute zero.
- Every scientific output must include source/kernel identifiers, model version, frame, epoch, units and limitations as applicable.
- Distinguish measured/source data, ephemeris-derived values, terrain-derived values, model estimates, synthetic fixtures and user assumptions.

## Alpha API endpoints

### `GET /terrain/site`

Purpose: return terrain metadata and analysis for a requested site/region.

Initial query fields:
- `site_id`
- `latitude`, `longitude` (only after coordinate convention is frozen)
- `region` or bounding area
- optional `include` list for elevation, slope, roughness and local-horizon products

Response should include:
- site and coordinate metadata
- DEM product identifier, source, footprint, pixel spacing, CRS, vertical datum, units and nodata handling
- elevation/slope/roughness summaries where computed
- local horizon/profile reference where available
- provenance, processing version and limitations

### `GET /celestial/positions`

Purpose: return Sun and Earth geometry for a lunar observer and epoch.

Initial query fields:
- observer latitude, longitude and altitude
- UTC epoch
- requested targets (Sun, Earth)

Response should include:
- normalized epoch and SPICE ET
- target direction/state and range where supported
- local azimuth/elevation with explicit convention and units
- reference frame, kernel inventory and coverage
- ideal-horizon visibility
- validation/provenance metadata and limitations

### `POST /mission/assess`

Purpose: assess one mission scenario using supplied or retrieved terrain and environment results.

Request should include:
- site and epoch
- equipment configuration identifier and configurable parameters
- mission constraints and scoring weights
- references to terrain and celestial/environment results or explicit synthetic fixtures

Response should include:
- hard-constraint pass/fail/unknown results separately from weighted score
- criterion-level score contributions
- feasibility status and reasons
- missing inputs and uncertainty/limitations
- source/result references and schema version

## Supporting endpoints

- `GET /health`
- `GET /sites`
- `POST /scenarios/compare` (after the single-scenario assessment contract is stable)

## Contract ownership

- Terrain/geospatial output and local horizon products: Member 1
- SPICE/ephemeris and geometry output: Member 2
- Mission assessment, API orchestration and frontend integration: Member 3 + project lead
- Shared schema review and versioning: all members

## Integration rule

Member 3 should build against agreed schemas and synthetic fixtures first. Do not connect unstable module outputs directly. Validate every request/response at module boundaries.
