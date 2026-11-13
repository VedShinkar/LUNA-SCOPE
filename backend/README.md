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
