# API Contracts — Team Agreement

Complete this document before connecting modules.

## Shared conventions
- Coordinates: TBD (document latitude/longitude convention and units)
- Time input/output: TBD (recommend ISO 8601 with explicit UTC offset or `Z`)
- Distances: metres unless an endpoint explicitly documents otherwise
- Angles: specify degrees or radians in every schema; do not infer
- Power: watts; energy: watt-hours or joules, explicitly stated
- Missing data: use null plus a documented reason; do not silently substitute zero

## Initial conceptual endpoints
- `GET /health`
- `GET /sites`
- `POST /geometry/sun-earth`
- `POST /terrain/sample`
- `POST /illumination/evaluate`
- `POST /communication/visibility`
- `POST /scenarios/compare`

These are proposals, not implemented endpoints. Agree on request/response schemas before coding.

## Example conceptual site request
```json
{
  "site_id": "custom-site-001",
  "latitude_deg": null,
  "longitude_deg": null,
  "coordinate_convention": "TBD"
}
```

## Contract ownership
- Terrain and geospatial outputs: Member 1
- Ephemeris and geometry outputs: Member 2
- API integration and application contracts: Member 3 + project lead
