# Phase 3.4 Final Acceptance Report

Session date: 2026-11-15 UTC

## A. Implementation status

Acceptance began on `main`, tracking `origin/main`. The starting diff included 25 modified tracked files and additional untracked work from earlier phases, including the Phase 3.4 implementation. The final browser retry found the shared workspace on `feature/horizons-validation-pilot`. It used the same running local services and did not change branches. This acceptance work changed the compact chart's left margin after reproducing clipped track labels in Chrome, and added this report.

FastAPI started at `http://127.0.0.1:8000` and Vite reported `http://127.0.0.1:5173/`. Both use the documented default ports. The existing Python environment, frontend dependencies and five pinned kernels were available. The API ran scientific requests with the existing kernel cache. Both service sessions were left running.

## B. Automated verification

| Check | Previously reported | This session |
| --- | --- | --- |
| Full backend suite | 192 passed | 192 passed on `main` and 216 passed on the later `feature/horizons-validation-pilot` checkout, with 8 warnings in each run |
| Frontend suite | 25 passed | 25 passed |
| Production build | Passed | Passed, with Vite's large chunk warning |
| `git diff --check` | Passed | Passed, with line-ending conversion notices |

## C. Browser verification checklist

Desktop Google Chrome opened the actual Vite URL. The desktop browser work used the current default analysis period displayed in the evidence, 2026-11-15 08:52:00 UTC to 2026-11-16 08:52:00 UTC. The historical demonstration was independently replayed through the running Vite proxy.

| Criterion | Status | Evidence |
| --- | --- | --- |
| Analysis → Operations timeline opens | PASS | Opened through the real Analysis menu and reached the workspace. |
| Loading state and empty state | PASS | Observed the initial form before results and the calculating message during a request. |
| Fatal JavaScript or missing-response errors | PASS | The exercised workspace, calculations and report workflows completed visibly. The browser console itself was not audited. |
| Error state in the workspace | NOT VERIFIED | The backend failure response is covered by the existing API suite. |
| Five tracks, readable labels, legend and shared UTC axis | PASS | Observed the single-site chart and all three compact comparison charts after the label fix. |
| Time cursor, next/previous and zoom | NOT VERIFIED | The inspector displayed the cursor and controls. A complete navigation round trip was not recorded. |
| Start/end UTC and sampling controls | NOT VERIFIED | Controls rendered with UTC values and the hourly schedule ran. A custom range and sampling edit was not verified through the browser. |
| Event inspection boundaries, duration and source UTCs | PASS | The Site11 inspector showed an 08:52–09:52 UTC interval of 1 h and matching solar and Earth source times at the inspected epoch. |
| Nonempty transition bracket selection | NOT VERIFIED | The observed export and inspector range had no transition bracket to select. |
| Native terrain point selection and pixel identity against both upstream views | NOT VERIFIED | Two explicit point selections matched the upstream services through live APIs, as recorded in section F. Equivalent selection across all three browser views was not exercised. |
| Invalidation or recalculation after changing observer | NOT VERIFIED | Browser mutation was not completed. |
| Demonstration assumptions visible | PASS | The form, results and report explicitly showed the demonstration profile. |
| Edit solar, Earth-disc, elevation-mask and minimum-duration criteria | NOT VERIFIED | Controls were present. The API regression verifies that an elevation-mask change preserves the physical solar and Earth tracks. |
| Favourable, unfavourable, conditional, unresolved and invalid labels | PASS | All five labels were visible and the chart differentiated unresolved hatching from a confirmed unfavourable band. |
| Live examples of all five combined classifications | NOT VERIFIED | The desktop range showed confirmed unfavourable mission intervals and unresolved source tracks. Live unresolved mission intervals were verified in the January API replay. |
| Manual mission events | NOT VERIFIED | The empty form was visible. Add and remove were not exercised. |
| Shackleton Rim standalone run | PASS | Loaded Site04, distinct native observer values and five tracks. |
| de Gerlache Rim standalone run | NOT VERIFIED | Its card and inspector were observed in the three-site run. |
| Malapert Massif standalone run | NOT VERIFIED | Its card and five tracks were observed in the three-site run. |
| Three-site comparison | PASS | The three named sites shared the time axis and profile and showed distinct observer coordinates, elevations and evidence. |
| January 1 demonstration through the browser form | NOT VERIFIED | The same comparison was reproduced through the live Vite API, as recorded in section F. |
| Save, refresh, load and overwrite profile | NOT VERIFIED | Save and Load controls were visible. The full persistence cycle was not exercised. |
| Malformed or inaccessible local storage | NOT VERIFIED | Browser storage failure was not induced. |

## D. Export verification

| Export check | Status | Evidence |
| --- | --- | --- |
| Single-site CSV download and file inspection | PASS | The actual downloaded file opened as UTF-8 with a BOM and the expected headers. It contains 25 unique hourly Site04 samples with matching observation and source UTC values, five classification fields, units in field names, observer coordinates, source raster and SHA-256, methods and quality flags. |
| Comparison CSV download and file inspection | PASS | The actual downloaded file opened as UTF-8 with a BOM. It contains 75 sample rows, with 25 unique UTC values per site, matching solar and Earth source timestamps, and the corresponding raster for each site. The fields preserve the different track states and site provenance. |
| Export of nonempty transition brackets and invalid classifications | NOT VERIFIED | The downloaded files used a period with no observed transition brackets or invalid rows. The frontend unit test checks bracket columns and uncertainty flags. |
| Comparison report preview | PASS | Observed the title, profile, UTC interval, evidence summaries, native observer and provenance. |
| Comparison PDF saved, reopened and inspected | PASS | Used Chrome's **Print / Save PDF** and **Save as PDF**. Reopened the saved file and visually inspected all three rendered pages. Tracks and units were legible and each chart remained on a single page. Site04's transition and interval text continues on page 2 before Site11. All sites, profile, limitations, provenance and reported durations were present. The verified PDF period had no nonempty transition brackets. |
| Single-site report preview | PASS | Observed the report title, UTC period, assumptions, Site04 observer, chart and source metadata. |
| Single-site PDF saved, reopened and inspected | PASS | A fresh Chrome window on the confirmed local URL completed the workflow after the earlier attempt lost URL identification. The saved file covers Site04 from 2026-11-15 11:49 UTC to 2026-11-16 11:49 UTC. Both pages reopened and were visually inspected. The chart, UTC range, observer, assumptions, durations and provenance were readable on page 1. The transition and favourable-interval sections continued on page 2 without clipping. This period had no transition bracket or favourable interval. |

For nonempty bracket coverage, use a run that shows a bracket in its inspector before exporting and compare its UTC bounds with the rendered report and CSV.

## E. Responsive verification

| Layout | Status | Evidence |
| --- | --- | --- |
| Desktop | PASS | The 1366 × 720 Chrome window showed the form, full single-site timeline, three-column comparison, inspector and report controls after the label fix. The captured page area was approximately 1366 × 633 screen pixels, excluding Chrome's browser controls. CSS viewport dimensions were not measured separately. |
| Tablet layout rendering | PASS | Chrome DevTools emulated 768 × 800 CSS pixels. The single-site timeline and inspector appeared in a single column. |
| Tablet readability and time controls | NOT VERIFIED | DevTools scaled down the preview. Repeated foreground changes interrupted attempts to enlarge it and exercise controls. |
| Narrow/mobile controls and timeline scrolling | PASS | Chrome DevTools emulated 400 × 546 CSS pixels. The observed controls fit in the single column, all five labels remained visible at the left edge, and horizontal scrolling reached the last UTC tick without shifting the outer results card. |
| Narrow/mobile full interaction checklist | NOT VERIFIED | A full selector, inspector and three-site comparison interaction cycle was not performed at this viewport. |

## F. Scientific integrity

The service resolves one native terrain observer per site, passes the same object to both observation engines and rejects mismatched observer or terrain identities during alignment. The API replay verified the native pixel identities, distinct terrain sources and 25 matching solar and Earth UTC timestamps per site on the original hourly schedule. Existing regression tests exercise mismatches, unavailable inputs, transition brackets, duration arithmetic and profile changes that preserve physical tracks. No scientific algorithms changed.

A separate live check compared the integrated response with the explicit solar-point and Earth-point responses. The two Site04 requests snapped to pixels (1595, 1605) and (1597, 1607). All three endpoints agreed on row, column, projected coordinates and elevation at each point. A Site23 run from January 1 through January 12 UTC with a six-hour nominal step and refinement enabled returned a bracket on January 10 for antenna eligibility changing from satisfied to below the mask. The bracket was found through the API. Its browser selection and export remain open.

The Vite proxy replay used the Demonstration v1 profile, raster-centre observers, a one-hour nominal increment and a UTC period of 2026-01-01 00:00 through 2026-01-02 00:00.

| Site | Native row, column | Elevation (m) | Favourable (h) | Unfavourable (h) | Unresolved (h) |
| --- | --- | ---: | ---: | ---: | ---: |
| Shackleton Rim, Site04 | 1600, 1600 | 767.98 | 0 | 24 | 0 |
| de Gerlache Rim, Site11 | 1600, 1600 | 1793.66 | 0 | 0 | 24 |
| Malapert Massif, Site23 | 2100, 2100 | 4783.63 | 0 | 11 | 13 |

All three totals match the previous implementation report and each sums to 24 hours. The replay kept Site11's unresolved hours in the unresolved field. The browser exports use the different November period recorded in section C.

## G. Screenshots

| Evidence | Captured UTC | Chrome window | Exact path |
| --- | --- | --- | --- |
| Workspace and UTC controls | 08:53:24 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-desktop-controls.jpg` |
| Defect before correction | 08:53:59 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-comparison-before-label-fix.jpg` |
| Site11 inspection | 08:54:10 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-inspector.jpg` |
| Profile controls | 08:54:44 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-profile-controls.jpg` |
| Corrected comparison showing all three sites | 08:54:49 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-comparison.jpg` |
| Comparison report preview | 08:55:03 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-comparison-report.jpg` |
| Standalone Shackleton five-track chart | 08:58:09 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-shackleton.jpg` |
| Single-site report preview | 08:59:40 | 1035 × 361 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-single-report.jpg` |
| Narrow controls, emulated 400 × 546 | 11:57:18 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-narrow-controls.jpg` |
| Narrow five-track chart, emulated 400 × 546 | 11:57:36 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-narrow-chart.jpg` |
| Narrow chart after horizontal scroll, emulated 400 × 546 | 11:57:47 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-narrow-scrolled.jpg` |
| Tablet chart and inspector, emulated 768 × 800 | 12:04:46 | 1366 × 720 | `C:/Users/Dell/.codex/visualizations/2026/11/13/01a1d6ac-f26b-7670-9535-89aebde7f943/phase34-tablet-chart.jpg` |

Exports are preserved in the same evidence directory as `phase34-comparison.pdf`, `phase34-single.pdf`, `phase34-comparison.csv` and `phase34-single.csv`. The reopened PDF page renders are `phase34-comparison-page-1.png` through `phase34-comparison-page-3.png` and `phase34-single-page-1.png` through `phase34-single-page-2.png`.

## H. Defects and corrective changes

- In Chrome, compact chart bars covered the ends of “Antenna elevation” and “Mission condition.” Increased the compact SVG's left plotting margin from 115 to 147 viewBox units, matching the full chart. Confirmed complete labels in Chrome and across the saved comparison PDF. File changed: `frontend/src/features/lunar-explorer/MissionTimelineChart.tsx`.
- Added `docs/PHASE_3_4_FINAL_ACCEPTANCE_REPORT.md`.

## I. Remaining work

- Verify readability and time controls at tablet width and complete the remaining narrow/mobile interactions.
- Complete the pending browser interactions in section C, including observer mutation, profile persistence and storage errors, time controls, manual events, standalone Site11 and Site23 runs, and the January period through the form.
- Exercise a period with a nonempty transition bracket and verify its browser selection and exported UTC bounds. Verify invalid classifications in a suitable browser or export case.

## J. Final status

**IMPLEMENTATION COMPLETE, ACCEPTANCE PARTIALLY VERIFIED.**
