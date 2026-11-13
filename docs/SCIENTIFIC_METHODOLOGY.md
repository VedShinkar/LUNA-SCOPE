# Scientific Methodology — Working Agreement

This document is the shared authority for scientific conventions. Members 1 and 2 must finalize the TBD items together before combining terrain and ephemeris calculations.

## Decisions to finalize

- Lunar latitude convention: planetocentric or planetographic, explicitly selected per source/product and transformed where necessary.
- Longitude direction and range: specify east/west convention and wrap range.
- Lunar body-fixed reference frame and realization: identify the exact SPICE frame/kernel realization.
- Inertial reference frame: identify the exact frame used for reported target vectors.
- Time scales: UTC input, SPICE ET/TDB conversion and leap-second kernel version.
- Reference lunar radius and elevation datum: record product-specific vertical datum; do not assume one global datum.
- Terrain projection and map units: record each source product's CRS and any reprojection parameters.
- Observer altitude/height: define reference surface and whether antenna/instrument height is above local terrain.
- Local horizon: define azimuth convention, sampling interval, observer location and terrain coverage.
- Solar illumination: define surface-normal source, incidence convention, shadow/ray-tracing method and time step.
- Earth visibility: distinguish ideal geometric horizon, terrain obstruction and RF link feasibility.
- Solar-array/battery, RF and thermal model assumptions: expose parameters and uncertainty.

## Required traceability for every result

Record inputs and units; source dataset/product or SPICE kernel identifiers and versions; coordinate and time conventions; model version and assumptions; output units; known limitations; validation test and reference result.

## Evidence classes

Every displayed result must be classed as one of:
1. Source observation / source-derived product
2. Ephemeris-derived result
3. Terrain-derived result
4. Model estimate
5. Synthetic development fixture
6. User-supplied mission assumption

## Validation principles

- Compare SPICE geometry with Horizons only when observer definition, epoch/time scale, target, frame/plane, corrections and units match.
- Do not present placeholder values or visually plausible estimates as validated scientific results.
- Missing terrain coverage, kernel coverage or model inputs must produce unknown/not evaluated, not an optimistic pass.
- Preserve uncertainty and known product limitations in downstream mission assessments.
