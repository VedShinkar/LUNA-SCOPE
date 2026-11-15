# LUNA-SCOPE

**Lunar Unified Navigation, Analysis & Site Optimization for Comparative Operational Planning and Evaluation**

LUNA-SCOPE is a lunar landing-site exploration and mission-planning prototype for the lunar south pole. It brings terrain, Sun/Earth geometry, illumination and communication visibility, site comparison, and mission decision support into one workflow.

The goal is to help a mission planner explore candidate locations and understand the trade-offs behind a site choice—not to certify a landing site or replace mission engineering review.

## The challenge

A lunar landing site must offer more than a flat patch of ground. Terrain hazards, local horizons, solar access, Earth line-of-sight, equipment assumptions and uncertainty all affect mission operations. These factors are often studied in separate tools. LUNA-SCOPE is designed to bring them together so that candidate sites can be explored and compared in a consistent interface.

## What the prototype includes

- **Terrain analysis:** NASA Lunar Orbiter Laser Altimeter (LOLA) elevation products, terrain derivatives, data-quality and uncertainty information, and preliminary hazard screening.
- **Candidate regions:** Shackleton rim (Site04), de Gerlache rim (Site11), and Malapert Massif (Site23), subject to the availability and completeness of each site's local data products.
- **Celestial analysis:** Sun and Earth geometry using the project's SPICE/NAIF and NASA JPL Horizons workflows.
- **Operational timeline:** Time-based solar and Earth visibility tracks, including unresolved intervals rather than silently treating missing data as clear conditions.
- **Mission intelligence:** Mission profiles, feasibility checks, weighted comparisons and scenario summaries.
- **AI Mission Copilot:** A deterministic natural-language interface that routes questions to project tools and explains returned information. It is not currently a live large-language-model assistant.

## Important scientific status

This is a research and hackathon prototype. Some Mission Intelligence assessment examples still use synthetic fixtures. Those scores are illustrative and must not be represented as NASA-derived site rankings or validated landing probabilities. Terrain metrics, geometric calculations and model estimates have different evidence classes; the interface and reports should retain those distinctions.

A preliminary hazard screen is not a landing-safety certification. Unresolved or missing inputs remain unknown. Results depend on source coverage, coordinate and time conventions, model assumptions and validation limits.

## NASA data and technical resources

- **NASA LOLA / Planetary Data System Geosciences Node (PGDA):** Regional lunar elevation and associated terrain products used in the terrain workflow. The repository's terrain catalogue and download manifest record product-level details.
- **NASA/JPL SPICE (NAIF):** Kernels and geometry tooling used by the celestial-analysis workflow.
- **NASA JPL Horizons:** Ephemeris service used for celestial geometry and comparison/validation workflows.
- **LROC:** Imagery is part of the broader research context where available; only list specific imagery products in the final submission if they were actually used in the submitted build.

See [Data Sources](docs/DATA_SOURCES.md), [Terrain Data Guide](docs/TERRAIN_DATA_GUIDE.md), and the metadata under `data/metadata/` for source and processing details.

## Technology

- Python scientific and geospatial processing
- FastAPI backend and Python mission/science services
- React, TypeScript and browser-based visualization
- SPICE/SpiceyPy and NASA JPL Horizons workflows
- Raster terrain processing and automated tests

Check the current dependency files and application setup instructions before running the project; this README is an overview, not a substitute for environment-specific installation steps.

## Run and develop

1. Clone this repository and follow the setup instructions in the backend and frontend directories.
2. Obtain the required NASA source products and SPICE kernels using the documented scripts and manifests.
3. Keep large raster files, kernels, credentials and local environment files out of Git.
4. Run the documented test suites before changing scientific or integration code.

## Project documentation

- [Development plan](docs/DEVELOPMENT_PLAN.md)
- [Scientific methodology](docs/SCIENTIFIC_METHODOLOGY.md)
- [Data sources](docs/DATA_SOURCES.md)
- [System architecture](docs/SYSTEM_ARCHITECTURE.md)
- [API contracts](docs/API_CONTRACTS.md)
- [Team workflow](docs/TEAM_WORKFLOW.md)
- [Terrain data guide](docs/TERRAIN_DATA_GUIDE.md)
- [NASA Space Apps submission draft](docs/NASA_SPACE_APPS_SUBMISSION.md)

## Team and project links

- Repository: https://github.com/VedShinkar/LUNA-SCOPE
- Issues: https://github.com/VedShinkar/LUNA-SCOPE/issues
- Engineering projects: https://github.com/users/VedShinkar/projects

## Scientific integrity and responsible use

For every displayed result, identify whether it is a source observation, ephemeris-derived value, terrain-derived value, model estimate, synthetic fixture or user assumption. Preserve units, coordinate/time frames, provenance, uncertainty and limitations. Do not convert unknown data into zero, clear visibility or a claim of safety.
