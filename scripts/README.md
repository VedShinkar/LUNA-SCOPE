# Scripts

Store reproducible data acquisition, validation, and preprocessing scripts here. Document source product/version, inputs/outputs, command-line arguments, coordinate system, units, network requirements, and validation steps.

## Multi-site terrain processing

`python scripts/process_lola_sites.py --sites Site04 Site11 Site23` verifies source association and Phase 1 before running the existing terrain/hazard pipeline. It writes per-site validation and Phase 2/3/5 reports, native GeoTIFFs, and a consolidated comparison. No downloads occur during processing or unit tests. Acquire sources first with `download_lola_terrain.py`. See `docs/PHASE5_IMPLEMENTATION.md`.
