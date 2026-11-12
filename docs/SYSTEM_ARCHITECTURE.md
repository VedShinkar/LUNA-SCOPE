# System Architecture — Initial Proposal

## Architecture style
Start with a modular monolith. Keep module boundaries explicit; split services only if justified by performance or deployment needs.

## Proposed stack
- Frontend: React + TypeScript + Vite
- 3D: Three.js / React Three Fiber
- Backend: Python + FastAPI
- Scientific computing: NumPy, SciPy, SpiceyPy
- Geospatial: Rasterio, GDAL, PyProj
- Storage: PostgreSQL + PostGIS
- Charts: Plotly
- Background work: worker queue when required
- Deployment: Docker

## Logical layers
1. Presentation: mission control UI, explorer, maps, timelines, comparison views.
2. API/orchestration: mission, site, scenario, equipment, reports, AI tool routing.
3. Scientific engines: ephemeris, terrain, horizon, illumination, power, thermal, RF.
4. Mission engines: mobility, scheduling, optimization, contingencies.
5. Data/storage: source metadata, processed terrain, scenario results, equipment profiles.

## Integration rule
Scientific calculations must be exposed through documented interfaces. The frontend must not reimplement scientific calculations independently.
