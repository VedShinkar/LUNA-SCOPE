# Phase 4 integration completion report

## Implemented

The Phase 4 API exposes the existing decision engine and structured Copilot services. Site Assessment, Scenario Comparison and Mission Copilot are available from the existing Site Analysis navigation. The workspace uses the current graphite styling and existing terrain and observatory layouts.

| Method | Endpoint |
| --- | --- |
| GET | `/terrain/explorer/mission-intelligence/defaults` |
| POST | `/terrain/explorer/mission-intelligence/assessment` |
| POST | `/terrain/explorer/mission-intelligence/compare` |
| POST | `/terrain/explorer/mission-intelligence/copilot` |

Assessment resolves the same native observer as the Operations Timeline and calls the existing terrain, solar and Earth measurement adapters. The HTTP path opts into a common endpoint-inclusive sample schedule. The score formulas and existing Python call defaults are preserved. It returns the existing preliminary score, per-criterion contributions, warnings, missing inputs, provenance and an independent operational window screen.

Scenario Comparison pairs site-bound observers with one UTC selection and scoring configuration. Each scenario can specify a mission profile and a named antenna mask. Results include the changes relative to the first scenario. Preliminary ranking is withheld for incomplete or incompatible evidence.

Copilot uses explicit evidence actions routed to the existing Python helpers, with a separate observation snapshot or timeline where appropriate. The frontend passes the selected site, projected point, UTC, profile and antenna settings. Scientific evidence and assessment are looked up on the server. The browser keeps a short response history within the view.

A minimal assessment request is `{"site_id":"Site04"}`. The response includes this excerpt.

```json
{
  "observer": {"site_id": "Site04", "source_pixel_row": 1600},
  "assessment": {"assessment_label": "PRELIMINARY"},
  "operational_screen": "unavailable",
  "timeline": null
}
```

A Copilot request of `{"site_id":"Site11","action":"timeline"}` returns `missing_inputs: ["UTC start and end"]`. See [the API contracts](PHASE_4_API_CONTRACTS.md) for request examples and field semantics and [the service audit](PHASE_4_API_INTEGRATION_AUDIT.md) for the original data flow and compatibility decisions.

## Tested

- Full Python suite with `pytest -q` passed 249 tests, including 14 new API cases, with nine warnings.
- The focused API and Python integration run passed 33 tests with two warnings.
- `npm --prefix frontend test` passed all 26 frontend tests.
- `npm --prefix frontend run build` succeeded. Vite reported a bundle-size advisory for the OrbitControls chunk.
- `git diff --check` exited successfully.

The API tests compare native observer coordinates and timeline summary with the existing route and compare the complete assessment evidence against the existing Python engine. They also exercise all three native sites, point and UTC changes, profile and antenna mask changes, unresolved intervals, NoData, missing terrain, invalid requests, service failures, unavailable comparison rows and incomplete Copilot requests.

## Browser verified

Five checks passed in Google Chrome with an isolated profile, Vite at `http://127.0.0.1:5176/` and FastAPI at `http://127.0.0.1:8018`.

- Editing the Site04 observer cleared its previous assessment. Resubmission moved the native observer from row 1600 to row 1595, column 1605, applied the new end time of `2026-01-01T03:30:00Z`, and used the `any_disc` Earth criterion and 12° antenna mask.
- Switching to Site11 cleared Site04's coordinates and resolved Site11's centre pixel.
- Scenario Comparison returned Site04, Site11 and Site23 together with an alternative 90° antenna mask at Site11 and explanations for changed assumptions.
- Copilot explained the Site11 assessment with the shared profile and reported the UTC range as missing when the timeline action received terrain-only context.
- Terrain-only context persisted when switching from Copilot to Mission Intelligence. At 390 px viewport width the workspace stayed within the viewport. Chrome reported no uncaught page errors during the run.

## Not verified

This milestone does not evaluate antenna hardware performance, RF link margin, or mission-level readiness.

## Blocked

The existing production services do not have an equipment catalog beyond the geometric antenna mask, a definitive mission feasibility model, free-form language generation, or a server conversation store. These capabilities were outside the existing service contracts and are not presented as live results.
