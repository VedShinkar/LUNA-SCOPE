# Phase 4 API contracts

All routes are under `/terrain/explorer/mission-intelligence`. Other API paths keep their existing contracts.

| Method | Path | Request | Result |
| --- | --- | --- | --- |
| GET | `/defaults` | None | Existing score weights, thresholds, site IDs and supported equipment control |
| POST | `/assessment` | Site, optional native point and time, mission profile, equipment, weights and thresholds | Native observer and elevation, engine assessment, criterion contributions, operational screen, timeline or instant evidence, and limitations |
| POST | `/compare` | Two to six named scenarios with a common time selection, weights and thresholds | Results per scenario, unavailable inputs, changed assumptions, and preliminary score groups when appropriate |
| POST | `/copilot` | Assessment input plus a supported `action` | Existing structured explanation, context, provenance, missing inputs and associated assessment or comparison when applicable |

### Assessment

```json
{
  "site_id": "Site04",
  "point": {"easting_m": -975, "northing_m": -6975},
  "start_utc": "2026-01-01T00:00:00Z",
  "end_utc": "2026-01-01T02:30:00Z",
  "step_seconds": 3600,
  "profile": {"name": "Disc criterion", "earth_requirement": "any_disc"},
  "equipment": {"name": "Raised mask", "minimum_antenna_elevation_deg": 10}
}
```

Omitting the point uses the site's raster centre pixel. The server obtains the resolved pixel coordinates, elevation, frame and terrain hash from the same native observer implementation as the timeline. Site IDs are `Site04`, `Site11` and `Site23`. Submit UTC in ISO 8601 with seconds and a UTC designator. A range needs both endpoints and a positive duration. The existing sampling bound is 241 epochs including any partial final step. Use `utc` instead of a range for point evidence. A point or terrain-only request has no duration-based scores.

The response includes an `assessment` with `assessment_label: "PRELIMINARY"`, `overall_data_status`, `preliminary_score`, `criteria`, `missing_criteria`, `quality_notes` and the terrain, illumination and communication evidence. Each criterion supplies its raw value, unit, score and weight. `contributions` contains the engine's raw weighted scores. The engine divides the sum of available contributions by the sum of available weights. This can yield a partial score even when the result has insufficient data. `request` echoes weights and thresholds, and `effective_profile` shows the applied assumptions.

The timeline is separate evidence. Its `operational_screen` is `met` if a confirmed favourable window meets the configured minimum, `not_met` if there is no qualifying window and the timeline is determinate, `unresolved` if uncertainty prevents that conclusion, or `unavailable` without range evidence. The screen describes the operational constraint, not total mission feasibility. The only supported equipment parameter is a geometric antenna elevation mask. It overrides the timeline profile mask when a named configuration is supplied. The Earth criterion drives the geometric visibility score, and the mask affects operational eligibility independently.

### Comparison

```json
{
  "start_utc": "2026-01-01T00:00:00Z",
  "end_utc": "2026-01-02T00:00:00Z",
  "scenarios": [
    {"name":"Shackleton","site_id":"Site04"},
    {"name":"de Gerlache","site_id":"Site11"},
    {"name":"Malapert","site_id":"Site23","equipment":{"name":"Raised mask","minimum_antenna_elevation_deg":10}}
  ]
}
```

The response preserves the scenario order. An unavailable observer produces an `unavailable` reason and a null `result` for that scenario. Each available result carries its own terrain and observer provenance. Every scenario uses the same requested time, interval, weight and threshold settings. Ranking and score deltas are withheld if criteria are missing, the Earth scoring criteria differ, or scored temporal evidence includes unresolved duration. Ranking otherwise sorts the engine's preliminary scores, keeping ties together. `differences` identifies changed assumptions relative to the first scenario.

### Copilot

```json
{"site_id":"Site11","action":"timeline"}
```

This returns `missing_inputs: ["UTC start and end"]` and no generated findings. Supported actions are `assessment`, `terrain`, `solar`, `earth`, `timeline` and `compare_sites`. The comparison applies the selected profile and equipment to all sites and uses the selected coordinates only for the matching site. The request carries inputs, not client-computed scientific findings. The backend obtains the findings, assessment and timeline itself. The Python service has no free-form prompt model or server conversation store. The browser keeps a short list of evidence responses while the Copilot view is open.

### Errors

Malformed or incompatible inputs, including invalid ranges, unrecognized actions, duplicate names and invalid native points, return HTTP 422. Missing native terrain, unavailable services and busy workers return HTTP 503 for single requests. Comparison carries expected observer failure per scenario. Existing partial or unresolved scientific data remains in the response with its evidence status and limitations.
