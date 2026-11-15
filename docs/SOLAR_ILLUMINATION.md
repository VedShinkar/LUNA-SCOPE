# Phase 3.2 Solar Illumination Observatory

The observatory uses the existing LUNA-SCOPE terrain renderer, the Phase 3.1 JPL DE440s geometry engine, and each site's own processed NASA LOLA elevation. Its three HTTP endpoints share the same ray solver. The earlier grid-bearing horizon tool remains available for terrain inspection.

## Terrain and solar ray

The native elevation rasters are 5 m per pixel in south-polar stereographic coordinates with DE421 Mean Earth axes and heights relative to the 1,737,400 m sphere. Site04 and Site11 rasters cover 16 × 16 km in projected coordinates. Site23 covers 21 × 21 km. The service verifies the expected projection, units, frame and source provenance, then reads each cell with its native mask. A selected point uses its containing native pixel centre and height. The response preserves both the requested projected coordinates and the resolved observer. The model uses a surface-level observer. [NASA PGDA data](https://pgda.gsfc.nasa.gov/products/78)

The Earth/Sun engine supplies the airless apparent Sun direction and equatorial angular diameter at each requested instant and observer. The terrain solver uses the solar azimuth measured clockwise from true local north. The surface-normal vector and the corresponding horizontal bearing define a radial plane through the Moon's centre. Its intersection with the reference sphere is a great circle. Projecting that great circle into south-polar stereographic coordinates and applying the full inverse affine gives rational pixel row and column functions in `u = tan(θ/2)`, where `θ` is the central angle from the observer. Solving the crossings at native row and column boundaries finds each interval traversed by the ray without a fixed distance-step skip. [Phase 3.1 frames and geometry](CELESTIAL_GEOMETRY.md)

The DEM is modeled as one constant radial height per pixel footprint, with discontinuities at pixel boundaries. For each crossed valid cell, its radial height `r` gives the apparent angle relative to the observer of radius `r₀` as `atan2(r cos θ − r₀, r sin θ)`. The solver maximizes that angle over the cell's interval. The geometric horizontal is the tangent plane to the observer's own spherical cell. The limiting native horizon is the maximum of zero and the other valid cell angles. This construction includes lunar curvature directly. Short-range horizons can be sensitive to the step between adjacent pixels, and subpixel slopes and features are unresolved. The base elevation product itself includes estimated heights between LOLA returns. [LOLA uncertainty and illumination study](https://ntrs.nasa.gov/citations/20205009660)

## Classification

| State | Interpretation |
| --- | --- |
| Shadowed centre | The centre lies below the local radial horizontal or intersects a known native terrain cell. A known blocker remains a blocker even when another part of the ray crosses NoData. |
| Confirmed sun centre | The centre ray clears complete native terrain and then exceeds the adopted lunar elevation ceiling, or points exactly radially up. This statement is conditional on the terrain model and ceiling. |
| Clear within raster | The ray clears all native cells it traverses before reaching the footprint boundary. The overall classification is unresolved because a farther ridge could still obstruct it. |
| Unresolved | A centre ray grazes the horizon, crosses NoData without a known blocker, or leaves the terrain before clearing the adopted ceiling. |
| NoData | The region's observer pixel has no valid elevation. |

The numerical grazing band is ±0.0001° around the tested horizon. It is a numerical threshold separate from DEM and ephemeris uncertainty. Native NoData gaps are left unresolved and are never filled. An unobstructed outward ray needs terrain coverage until it reaches 12,000 m above the reference sphere. This modeling ceiling is 1,208 m above the 10,792 m topographic maximum measured by LOLA. The search limit of 40 km exceeds the diameter of each supported site raster. Low Sun angles commonly require terrain beyond even that distance. The present implementation leaves such rays unresolved when it can establish only native-footprint clearance. [LOLA lunar topographic extrema](https://ntrs.nasa.gov/api/citations/20160008718/downloads/20160008718.pdf)

The API reports the solar angular radius and evaluates the centre ray. Disc visibility, limb visibility, reflected illumination and Earth occultation are outside Phase 3.2. The optional aligned LOLA elevation RMS band supports two sensitivity scenarios. Moving the terrain up and the observer down by their respective RMS values produces an upper horizon scenario. The opposite perturbation produces a lower one. The range shows whether the ray's nominal outcome is sensitive to these changes. It is not a statistical confidence interval and does not silently change the nominal class. Incomplete RMS data or a ray with a NoData gap yields no RMS scenario.

## Duration and spatial statistics

The point series evaluates an independent SPICE epoch at every requested time and also evaluates the exact end when it falls between steps. Adjacent samples with the same classified state contribute their time difference to that state. A changed or unresolved endpoint leaves the entire bracket unresolved. Transitions are reported as brackets between disagreeing classified samples. A shadow gap is an observed run of shadow samples surrounded by light samples, and its duration between first and last shadow sample and its enclosing bracket are both reported. Faster changes may occur between observations. Separate native-footprint estimates use the same accounting with native-clear states. Illuminated time fractions exclude unresolved brackets from their denominator.

Each region is a contiguous native window centred on the requested cell and shifted inward near data edges. The returned affine starts at its northwest corner. Every native pixel centre in the window gets its own solar direction and ray. Map counts are by native cells. Confirmed lit percentage uses all valid elevation cells as the denominator, including unresolved cells. The response also reports the percentage among classifiable cells. Neither denominator includes NoData. The matched-epoch UI compares equally sized native windows at each site centre and shows the different ray footprints. These windows sample different terrain and do not establish relative site suitability.

## API and limits

All requests go to `/terrain/explorer/illumination`. Each response reports site, time, source raster URL and hash, affine, native resolution, units and datum, uncertainty provenance, ephemeris and kernels, model settings, counts and quality flags.

| Endpoint | Input |
| --- | --- |
| `POST /point` | `site_id`, `utc`, optional projected `point` with `easting_m` and `northing_m`. |
| `POST /series` | `site_id`, optional `point`, `start_utc`, `end_utc`, integer `step_seconds`. At most 241 evaluated epochs including the end, and increments from 60 seconds to seven days. |
| `POST /region` | `site_id`, optional projected `point`, `side` from 2 to 16, and up to six strictly increasing `times_utc`. At most 768 centre rays per request. |

Each process caches one immutable native terrain pair and at most 2,048 sample results for it. Two concurrent illumination requests can execute per process. The API reports HTTP 422 for invalid locations, times or limits, HTTP 404 for unknown site IDs, and HTTP 503 for unavailable inputs or saturated compute slots. An HTTP 200 with an unresolved classification has valid scientific inputs with inadequate coverage or separation to assign a state.

## Reproducible checks

At 2026-01-15 06:00 UTC, the independently validated Phase 3.1 geometry was evaluated again at the nearest native observer pixel to each raster centre. Shackleton's solar elevation was 1.3310° and its native horizon was 33.8267°. At de Gerlache the corresponding values were 1.5248° and 3.7349°. Both were terrain-blocked in the native-cell model. Malapert's Sun centre was 1.9505° below the radial horizontal. Each 12 × 12 window had 144 valid model-shadowed cells at that epoch.

Synthetic tests cover centre rays on flat terrain, a known ridge, grazing, NoData, raster boundaries, RMS sensitivity, a rotated affine checked against a separate geodesic projection, interval accounting and spatial denominators. The point endpoint is also compared against the Phase 3.1 geometry endpoint at each resolved native observer.
