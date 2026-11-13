# System Architecture — LUNA-SCOPE

## Architecture style

Start with a modular monolith. Keep scientific and mission-engine boundaries explicit; split services only if performance or deployment evidence justifies it.

## Product configuration

- Mission planning and comparison across landing sites and dates/times.
- Two equipment modes: a general-purpose configuration and configurable mission-specific lander/rover equipment.
- Integrated simulation environment.
- AI Mission Copilot grounded in actual structured scenario outputs; it must not invent scientific values.

## Proposed stack

- Frontend: React + TypeScript + Vite
- 3D: Three.js / React Three Fiber
- Backend: Python + FastAPI
- Scientific computing: NumPy, SciPy, SpiceyPy
- Geospatial: Rasterio, GDAL, PyProj
- Storage: PostgreSQL + PostGIS when persistent spatial querying is required
- Charts: Plotly
- Deployment: Docker

## Logical layers

1. **Presentation:** mission control dashboard, 3D terrain explorer, site/date/equipment comparison, timeline and report views.
2. **API/orchestration:** site, terrain, celestial, mission assessment, scenario comparison, equipment and AI tool routing.
3. **Scientific engines:** ephemeris, terrain preprocessing, local horizon, illumination, solar power, thermal and RF link budget.
4. **Mission engines:** site scoring, mobility, scheduling, optimization and contingency simulation.
5. **Data/storage:** source metadata, processed terrain, kernel inventory, equipment profiles, scenario inputs and results.

## First alpha vertical slice

The first integrated demonstration should be deliberately narrow and evidence-driven:

1. A real Shackleton rim regional DEM is acquired and its metadata verified.
2. The terrain pipeline produces a georeferenced processed tile plus elevation/slope and local-horizon inputs.
3. SPICE computes Sun and Earth geometry for a documented lunar observer and epoch.
4. Horizons provides independent reference values for matching observer/time/frame settings.
5. Terrain horizon analysis determines whether the Sun/Earth are obstructed by nearby relief; geometric and terrain-aware visibility remain separate outputs.
6. The 3D explorer displays the actual processed terrain and selected site/observer.
7. Mission assessment consumes these results plus explicit equipment/mission assumptions and reports feasibility, constraints, provenance and unknowns.

Malapert Massif is the next comparison region after the Shackleton slice is reproducible.

## Integration interfaces

The initial API contracts are documented in `docs/API_CONTRACTS.md`:
- `GET /terrain/site`
- `GET /celestial/positions`
- `POST /mission/assess`

These are design contracts, not claims that the endpoints have already been implemented.

## Scientific integrity

- The frontend must not independently reimplement scientific calculations.
- Every result carries units, coordinate/time frame, source/kernel/model provenance and limitations.
- Never label mock data as observed lunar data.
- Unknown data remains unknown; do not treat missing terrain coverage as clear visibility or safe landing.
- Keep ideal geometric visibility distinct from terrain-obstructed visibility and RF link feasibility.
- Keep source observations distinct from model predictions and user assumptions.
