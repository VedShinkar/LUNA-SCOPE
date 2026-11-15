# Phase 3.3 Earth Communication Observatory

## Audit and implementation plan

The existing project provided topocentric Earth vectors and apparent diameter from Phase 3.1, and native LOLA data access, lunar curvature, affine ray traversal, and interval accounting from Phase 3.2. The communication workspace was a placeholder. Phase 3.3 extracts a body-neutral ray entry point while retaining the solar wrapper, adds Earth centre and finite-disc evidence, applies a separate antenna mask, and integrates point, series, region and metadata endpoints with the existing terrain renderer. Phase 1 and Phase 2 navigation, measurements and terrain analysis remain available.

## Earth geometry and observer

The service evaluates Phase 3.1 SPICE at the centre and height of the containing native LOLA pixel. The resolved observer and requested location are returned separately. Each of Site04, Site11 and Site23 uses its own 5 m raster and optional aligned elevation RMS band. The point and region calculations use native elevation at the true pixel centres. The renderer reuses the existing local terrain mesh and applies the result only to the corresponding native cells. [NASA LOLA landing-site products](https://pgda.gsfc.nasa.gov/products/78)

The Earth direction uses DE440s, the `MOON_ME_DE440_ME421` frame, airless apparent CN+S corrections and the observer's local east, north and radial up axes. Azimuth is clockwise from true north. Elevation is measured from the plane perpendicular to radial up. The apparent disc is circular in angular space using the Earth equatorial angular radius from Phase 3.1. UTC and future leap-second limits follow the existing [celestial geometry guide](CELESTIAL_GEOMETRY.md).

## Terrain obstruction and angular clearance

The centre and limb rays reuse the Phase 3.2 great-circle traversal. The solver intersects the south-polar stereographic great circle with native pixel boundaries using the full inverse affine. It evaluates the maximum elevation angle within each constant-height spherical cell interval. Lunar curvature is included explicitly. The radial horizontal bounds the local native horizon from below. The horizontal and the surrounding terrain's elevations can diverge on sloping ground because the radial-cell model represents the containing pixel as a spherical patch. Subpixel slopes and obstacles remain unresolved. [Terrain-ray method](SOLAR_ILLUMINATION.md)

The clearance values are `direction elevation − centre-bearing native horizon` in degrees. Positive values lie above that sampled reference. Upper and lower elevations are the vertical extrema of the apparent disc. The centre-bearing reference does not describe terrain variation across the disc. At zenith or nadir the centre bearing and associated clearances are undefined. An unresolved ray may still report the maximum angle of its known cells with explicit NoData and coverage flags.

The shared numerical grazing tolerance is ±0.0001°. The trace is limited to 40 km and ends earlier at the native footprint edge or the 12,000 m adopted radial clearance ceiling. A known blocker remains valid when another part of the ray crosses NoData. An outward ray that reaches unknown terrain before it clears the radial ceiling cannot be confirmed visible. In particular, positive Earth elevation and a positive native clearance may still yield unresolved visibility at polar sites. Centre-bearing RMS scenarios perturb the observer and terrain heights in opposite ±1 RMS directions. They indicate sensitivity under that height scenario and provide no probabilistic confidence. [LOLA terrain uncertainty study](https://ntrs.nasa.gov/citations/20205009660)

## Finite disc and antenna eligibility

| Disc state | Sufficient evidence in the native-cell model |
| --- | --- |
| Fully obscured | The upper limb is below the radial horizontal or below a conservative all-bearing obstruction bound from the complete eight-cell ring around the observer. |
| Fully visible | The lower limb clears a conservative maximum-height envelope in a complete, valid native window that contains every disc ray until its radial clearance ceiling. |
| Partially visible | At least one distinct direction is confirmed visible and another is confirmed obstructed among the centre and eight angular small-circle rim probes. |
| Unresolved | Available ray or envelope evidence cannot support a whole-disc classification. |

The envelope bounds the polar stereographic scale over the search disk, transforms its projected extent through the inverse affine, and checks every pixel in a bounding window. For clearance it divides the maximum height difference by a lower bound on horizontal distance beyond the origin pixel, with curvature omitted only for this conservative upper angle bound. For obstruction the enclosing ring provides a minimum blocking height for every bearing; the farthest projected origin-pixel corner bounds the exit distance. The rim probes include the vertical limb directions and azimuth offsets. Probe agreement alone establishes neither whole-disc visibility nor whole-disc obstruction. The model provides no illuminated or visible disc-area fraction.

The antenna elevation test is `Earth centre elevation ≥ configured minimum`, with an inclusive boundary and an allowed range of 0–90°. The default 0° is an editable assumption. This test uses only geometric elevation and remains independent of terrain and disc visibility. A satisfied elevation constraint does not establish a functioning radio link.

## Series and native-window statistics

The time series evaluates Earth geometry at every requested epoch and at the exact end, including a shorter final increment where needed. The selected criterion may be the centre, any visible disc, the entire disc, or the centre with the antenna mask. A single confirmed visible direction can satisfy the any-disc criterion. A single confirmed blocked direction can disqualify the entire-disc criterion. Under the combined criterion, `obstructed` time includes timestamps that fail the assumed antenna elevation constraint.

Intervals with matching classified endpoints contribute to sampled duration totals. Mixed or unresolved endpoints contribute to unresolved time. When classified samples show opposite states, optional bisection targets a 60-second bracket. It stops at unresolved terrain evidence or the budget of 24 added evaluations. The overall maximum remains 241 evaluations. The output reports brackets with both observed states, including brackets that span unresolved samples. Additional changes can occur between samples.

Regions contain 2–12 contiguous native pixels per side. Each valid pixel receives its own observer, geometry and terrain evaluation. NoData cells remain distinct from valid cells with unresolved visibility. Percentages divide by valid-elevation cells, including unresolved cells. Centre, disc and antenna mask counts describe separate dimensions and should be read independently. The UI compares equal-sized windows and matched UTC timestamps. Site04 and Site11 use 16 × 16 km ray footprints and Site23 uses a 21 × 21 km ray footprint.

## HTTP interface

Paths are under `/terrain/explorer/communication`. FastAPI exposes the typed request and response schemas.

| Endpoint | Inputs and outputs |
| --- | --- |
| `GET /metadata` | Supported sites and Phase 3.1 observer references, kernel provenance, coverage and Earth visibility limits. |
| `POST /point` | Site, UTC, optional projected point, mask and criterion. Returns resolved observer, geometry, terrain evidence, and independent classifications. |
| `POST /series` | Site, UTC start and end, step seconds, optional point, mask, criterion and `refine_transitions`. Returns samples, intervals, durations and transition brackets. |
| `POST /region` | Site, UTC, side length, optional projected centre, mask and criterion. Returns the native window affine and parallel observer and visibility arrays, with counts and percentages. |

Optional projected coordinates are `easting_m` and `northing_m`. The shared terrain cache retains one raster pair and up to 2,048 point-time evaluations across solar and Earth analyses. Physical Earth evaluations are cached independently of the antenna mask and criterion, which are applied to the cached sample. Two requests can execute concurrently per process through the Earth API. Unsupported sites return HTTP 404, invalid input returns HTTP 422, and unavailable required science inputs or saturated workers return HTTP 503.

## Validation

The synthetic suite exercises flat terrain, a ridge with an obstructed centre but partially visible disc, whole-disc obstruction and clearance, limb grazing, angular wrap, the inclusive antenna threshold, NoData and raster edges, temporal refinement and class denominators. Live-raster API tests verify all three site observers and compare the returned azimuth, elevation and radius against Phase 3.1 at the same coordinates. The Phase 3.1 Horizons fixture and the Phase 3.2 ray and API tests are part of the full regression suite. [JPL Horizons angular conventions](https://ssd.jpl.nasa.gov/horizons/manual.html)
