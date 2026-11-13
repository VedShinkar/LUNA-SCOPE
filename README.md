# LUNA-SCOPE

**Lunar Unified Navigation, Analysis & Site Optimization for Comparative Operational Planning and Evaluation**

LUNA-SCOPE is an AI-assisted lunar mission-planning and decision-support platform combining NASA lunar terrain data, celestial geometry, solar illumination, direct-to-Earth communication analysis and integrated mission simulation to evaluate and compare lunar landing sites, dates and equipment configurations.

## Current agreed alpha scope

- Research-grade implementation using real NASA terrain data from the beginning.
- First south-pole regions: Shackleton rim, followed by Malapert Massif.
- Regional LOLA elevation products for terrain geometry; LROC NAC imagery for context and surface-feature inspection.
- SPICE/NAIF with SpiceyPy as the primary local celestial-geometry engine; NASA JPL Horizons as an independent validation reference.
- Terrain-aware horizon, shadow and visibility analysis.
- Solar illumination and configurable power estimates, Earth communication geometry/link budget, and first-order thermal modelling.
- Comparison across different landing locations, dates/times and two equipment modes: general-purpose and configurable mission-specific equipment.
- Integrated simulation environment and an AI Mission Copilot grounded in verified structured outputs.
- Modular-monolith architecture.

## First alpha vertical slice

A reproducible Shackleton scenario that combines a verified regional DEM, processed terrain and local horizon, SPICE Sun/Earth geometry, Horizons validation, terrain-aware illumination/visibility, a 3D regional explorer and transparent mission assessment. Malapert is the next comparison region.

## Repository structure

```text
frontend/       React + TypeScript application and 3D visualization
backend/        FastAPI services and scientific/mission engines
shared/         API schemas and shared contracts
data/           Dataset metadata and local data mount points
docs/           Product, science, data, architecture, API and delivery plans
scripts/        Data acquisition and processing utilities
tests/          Unit, scientific regression and integration tests
```

## Project management

- [Development plan and dependency map](docs/DEVELOPMENT_PLAN.md)
- [Scientific methodology](docs/SCIENTIFIC_METHODOLOGY.md)
- [Data sources register](docs/DATA_SOURCES.md)
- [System architecture](docs/SYSTEM_ARCHITECTURE.md)
- [API contracts](docs/API_CONTRACTS.md)
- [Team workflow](docs/TEAM_WORKFLOW.md)
- [GitHub Project setup and metadata bootstrap](docs/GITHUB_PROJECT_SETUP.md)

GitHub repository issues: https://github.com/VedShinkar/LUNA-SCOPE/issues  
Engineering board: https://github.com/users/VedShinkar/projects

## Development status

This repository currently contains the starter scaffold, planning documents and engineering issues. Do not describe scientific modules as implemented until code, tests and validation evidence exist.

## Team workflow

1. Take an issue from the Project board.
2. Create a short-lived issue-specific feature branch.
3. Implement the change and add tests.
4. Open a pull request to `main`, referencing the issue (for example, `Closes #7`).
5. Request review and merge only after tests and scientific checks pass.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Data policy

Do not commit large DEMs, imagery archives, SPICE kernels, credentials or bulky derived datasets. Store retrieval instructions, product identifiers, source URLs, checksums, licence/use notes and processing metadata in the repository. Keep local datasets outside version control.

## Scientific integrity

Every result must identify its evidence class: source observation, ephemeris-derived value, terrain-derived value, model estimate, synthetic fixture or user assumption. Record units, coordinate/time frames, provenance, assumptions, uncertainty and limitations. Unknown data must remain unknown; it must not be treated as zero, clear visibility or safe landing.
