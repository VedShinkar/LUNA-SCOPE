# Backend

Planned stack: Python, FastAPI, NumPy, SciPy, SpiceyPy, Rasterio, PyProj.

The backend is organized as a modular monolith:
- `api/`: HTTP endpoints and request validation
- `scientific_engines/`: terrain, ephemeris, horizon, illumination, power, communication, thermal
- `mission/`: decision engine, mobility, operations, contingencies, optimization
- `ai_copilot/`: controlled natural-language interface to verified results
- `models/`: shared backend data models
- `services/`: orchestration and integration

Run locally from `backend/` after installing dependencies:
`python -m uvicorn app.main:app --reload`

Scientific engines must remain independent of HTTP request handling.

For celestial calculations, run `python scripts/download_spice_kernels.py` from the repository root. The [Celestial Geometry Observatory guide](../docs/CELESTIAL_GEOMETRY.md) documents kernel coverage, the HTTP interface and the Horizons comparison.

The [Solar Illumination Observatory guide](../docs/SOLAR_ILLUMINATION.md) covers native terrain ray tracing, time and regional analysis, and the distinction between terrain clearance and unresolved illumination.

The [Earth Communication Observatory guide](../docs/EARTH_VISIBILITY.md) documents finite-disc evidence, the independent antenna elevation assumption and the visibility API.

The [Mission Timeline guide](../docs/MISSION_TIMELINE.md) documents integrated UTC sampling, mission profiles and matched three-site operational window comparisons.
