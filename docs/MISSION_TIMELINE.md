# Mission timeline and operational windows

The Operations timeline in Analysis combines the [solar illumination](SOLAR_ILLUMINATION.md) and [Earth visibility](EARTH_VISIBILITY.md) engines. Both use the same native LOLA pixel centre and [celestial geometry](CELESTIAL_GEOMETRY.md). The original manual events are still available below the analysis workspace.

The service resolves the observer and terrain once per site, schedules shared epochs, composes the evidence and its UTC intervals, then supplies the workspace, inspector and reports. It reuses the existing kernel, terrain and physical sample caches. An optional projected coordinate selects a native pixel; leaving coordinates blank uses the raster centre. The comparison covers Shackleton Rim (Site04), de Gerlache Rim (Site11) and Malapert Massif (Site23), each with its own terrain and observer but the same UTC schedule, profile and classification rules.

## Profile and classification

The version 1 **Demonstration** profile requires confirmed direct sunlight at the solar centre, geometric visibility of the Earth centre, an antenna elevation of at least 0° and a continuous favourable interval of at least one hour. The workspace starts with a 24-hour period and a one-hour nominal increment. These values are examples. Solar illumination can be tracked without requiring it, and Earth eligibility can instead require any part or all of the disc. The antenna elevation mask stays independent of physical obstruction: the threshold applies to geometric elevation of the Earth centre. Save/Load stores the profile, UTC period, increment and refinement choice in the current browser. It does not save observer selection or analysis results.

Required invalid evidence takes precedence; otherwise a definitive required failure gives **Unfavourable**. Without a definitive failure, a missing observation or unresolved required condition gives **Unresolved**. Once all required conditions pass, an enabled full-disc preference gives **Conditional** if full-disc visibility is unconfirmed. The result is otherwise **Favourable**. Requiring the full disc as a hard constraint uses the upstream Earth criterion directly; partial visibility can then establish failure. A favourable window's minimum duration is evaluated separately without changing the state of its constituent intervals.

## UTC and bounds

Samples align on exact UTC instants. The composer rejects mismatched observers or terrain versions, conflicting duplicate samples and source observations outside the requested period. Missing evidence at a scheduled or source epoch stays unresolved; no binary track is interpolated. Adjacent observations with matching states support the sampled interval estimate. A change in a required track brackets a possible transition; a stable independent failure can still establish an unfavourable interval. Transition dates are UTC brackets, never estimated event times. The API returns non-overlapping intervals, includes the requested end exactly even when the nominal step does not divide the period, and sums durations from actual boundaries. Individual changes across the five tracks are listed as brackets; the summary transition count is for the combined track.

Requests accept nominal increments from one minute to seven days, with at most 241 epochs including the final endpoint and any refinement. When enabled, up to 24 additional common instants can be used to narrow detected brackets toward 60 seconds, within that overall limit. Refinement can end early at inconclusive observations or the sample limit. All compared sites are evaluated at each additional instant. Cached results are keyed by observer selection, UTC range, sampling, profile, refinement choice, terrain and uncertainty file versions and kernel fingerprints. Concurrent work is bounded. The workspace can stop waiting for a request; a started backend calculation may still finish.

Matching endpoint classifications cannot rule out shorter events between samples. Native footprint exits, missing terrain, uncertain obstruction and partial disc evidence retain the upstream engines' limits. A favourable result describes sampled environmental and geometric conditions; it does not establish panel output, link performance or mission success.

## API and reports

All operations are under `/terrain/explorer/mission-timeline`:

| Method and path | Purpose |
| --- | --- |
| GET `/profile` | Get the demonstration profile |
| POST `/profile` | Validate and normalize a versioned profile |
| POST `/site` | Calculate for `site_id` and optional projected `point` |
| POST `/compare` | Calculate all three sites with optional projected `points` keyed by site |
| POST `/inspect` | Get the interval, endpoint observations and intersecting brackets at `inspect_utc` |
| POST `/refine` | Repeat a site analysis with bounded refinement enabled |

Calculation requests accept `start_utc`, `end_utc`, `step_seconds`, `profile` and `refine_transitions`. Responses identify the observer, terrain, kernels, methods, applied profile, sample UTCs, classifications, quality flags, brackets and durations. Failure to obtain upstream scientific inputs returns an error for the request.

The workspace provides single-site and three-site reports with UTC tracks and physical assumptions. CSV exports contain sample and bracket rows and identify the profile, source raster, methods and flags. Print / Save PDF uses the existing scientific report dialog and print stylesheet.
