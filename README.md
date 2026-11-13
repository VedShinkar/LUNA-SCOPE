# LUNA-SCOPE

**Lunar Unified Navigation, Analysis & Site Optimization for Comparative Operational Planning and Evaluation**

LUNA-SCOPE is an AI-assisted lunar mission planning and decision-support platform combining NASA lunar terrain data, celestial geometry, solar illumination, direct-to-Earth communication analysis, and integrated mission simulation to evaluate and compare lunar landing sites, dates, and equipment configurations.

## Project goals
- Explore lunar locations using measured NASA terrain products.
- Calculate Sun and Earth geometry for selected lunar coordinates and times.
- Evaluate terrain-aware illumination and direct-to-Earth visibility.
- Estimate power, thermal, communication, and mobility constraints using explicit models.
- Compare landing-site, landing-date, and equipment scenarios.
- Provide traceable explanations through an AI Mission Copilot.

## Repository structure
```text
frontend/       React + TypeScript application and 3D visualization
backend/        FastAPI services and scientific/mission engines
shared/         API schemas and shared contracts
data/           Dataset metadata and local data mount points (not large source datasets)
docs/           Product, science, data, architecture, and API documentation
scripts/        Data acquisition and processing utilities
tests/          Cross-module and integration tests
```

## Development status
This repository is a starter scaffold. Scientific calculations and data products must be validated before being presented as mission-planning results. Do not use placeholder values as scientific outputs.

## Team workflow
1. Create a feature branch for each task.
2. Make focused commits.
3. Open a pull request into `main`.
4. Request review and run relevant tests.
5. Merge only after review and validation.

See [CONTRIBUTING.md](CONTRIBUTING.md) and the documents in `docs/`.

## Data policy
Do not commit large DEMs, imagery archives, SPICE kernels, credentials, or other bulky datasets to Git. Store acquisition scripts, product identifiers, source URLs, checksums, licences/usage notes, and processing metadata in the repository. Keep local datasets outside version control unless the team explicitly agrees otherwise.

## Scientific conventions
Before integrating modules, the team must agree on lunar coordinate conventions, reference frames, time scales, elevation datum/units, terrain projections, and visibility definitions. Record decisions in `docs/SCIENTIFIC_METHODOLOGY.md` and `docs/API_CONTRACTS.md`.
