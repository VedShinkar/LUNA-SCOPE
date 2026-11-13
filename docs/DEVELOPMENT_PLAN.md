# LUNA-SCOPE Development Plan

**Status:** Initial execution plan  
**Team:** 3 developers  
**Planning basis:** The team's approved role and initial-task allocation.  
**Schedule convention:** Relative phases, not calendar dates. Set calendar deadlines only after the hackathon submission/demo deadline is confirmed.

## Product objective

Build a scientifically traceable lunar mission-planning and site-comparison platform, beginning with Shackleton and Malapert Massif. The first vertical slice should combine measured regional terrain, Sun/Earth geometry, illumination and visibility analysis, and a transparent mission assessment.

## Team ownership

| Owner | Primary responsibility | Initial output |
|---|---|---|
| Member 1 | Lunar terrain, data processing and 3D visualization | Shackleton regional terrain rendered from a real DEM, with basic elevation/slope analysis |
| Member 2 | Celestial mechanics and scientific simulation | SPICE-derived Sun/Earth positions for a specified lunar observer, cross-checked against Horizons |
| Member 3 | Mission intelligence and AI integration | Mock-data mission assessment engine with constraints, scoring and scenario comparison |
| Shared | Coordinate conventions, data contracts, integration, tests, Git workflow and demo | Consistent interfaces and a reproducible end-to-end workflow |

## Execution phases and exit gates

### Phase 0 — Team and scientific foundations (start immediately)
Issues: #1, #3, #4, #24, #16

- Agree coordinate/time conventions before mixing terrain and ephemeris results.
- Member 2 studies Horizons and prepares reproducible reference queries.
- Member 3 creates synthetic fixtures, explicitly labelled as synthetic.
- Adopt feature branches, pull requests and review rules.
- Define versioned JSON contracts and provenance requirements.

**Exit gate:** Coordinate conventions and initial data contracts are reviewed by all three members; mock fixtures validate; Git workflow is understood.

### Phase 1 — First independent vertical slices (parallel)
Terrain: #2, #5, #6, #7  
Geometry: #10, #11, #15  
Mission intelligence: #17

- Member 1 selects candidate areas, acquires a suitable regional DEM and imagery, then builds the processing pipeline.
- Member 2 sets up SPICE, calculates Sun/Earth positions and validates results against matching Horizons settings.
- Member 3 implements explainable scoring and hard constraints against synthetic fixtures.

**Exit gate:** Each workstream produces a tested, reviewable output that follows the shared conventions. At least one Shackleton DEM is verified locally; geometry examples are reproducible; scoring distinguishes hard failures from weighted preferences.

### Phase 2 — Terrain-aware environmental analysis
Issues: #8, #9, #12, #13, #14

- Render the processed regional DEM in the 3D explorer.
- Produce elevation, slope and a documented roughness metric.
- Combine geometry with terrain horizons for obstruction-aware visibility.
- Add first-order solar power, communication link-budget and thermal estimates.
- Keep geometric visibility separate from terrain obstruction and RF link feasibility.

**Exit gate:** A selected site/time can produce terrain context, Sun/Earth geometry, visibility and clearly labelled model estimates with units and provenance.

### Phase 3 — Mission-level intelligence
Issues: #18, #19, #20, #21

- Compare sites, dates/times and equipment configurations.
- Add operations scheduling and contingency scenarios after power/communication outputs are available.
- Integrate the Copilot only after structured scenario outputs and schemas are stable.
- Generate reports from structured results, including assumptions and limitations.

**Exit gate:** The system can compare at least two candidate scenarios and explain metric changes, constraint failures, missing inputs and provenance.

### Phase 4 — Integration, verification and demonstration
Issues: #22, #23, #25

- Integrate terrain, geometry and mission-assessment engines.
- Run unit, integration and scientific regression tests.
- Reproduce the selected demo scenario from saved inputs.
- Rehearse the demonstration and prepare fallback fixtures for unavailable external services.

**Exit gate:** A clean checkout can run the documented demo workflow; every shown number is sourced, calculated, or explicitly marked synthetic/modelled.

## Dependency map

- #1 Coordinate conventions → #3 Horizons study, #10 SPICE setup, #7 terrain processing, #11 geometry and #16 data contracts.
- #2 Regional study → #5 LOLA acquisition and #6 LROC imagery.
- #5 LOLA acquisition + #1 conventions → #7 terrain pipeline → #8 3D explorer and #9 terrain analysis.
- #10 SPICE + #3 Horizons → #11 Sun/Earth positions → #12 horizon visibility.
- #7 terrain pipeline + #11 geometry → #12 terrain-aware visibility.
- #9 terrain analysis + #12 visibility → #13 solar power estimation.
- #11/#12 → #14 communication and thermal models.
- #4 mock data + #16 schemas + outputs from #9/#13/#14 → #17 site scoring → #18 scenario comparison.
- #18 + #13 + #14 → #19 operations/contingencies.
- #16 schemas + #18 → #20 Copilot.
- #15 validation + #18 → #21 reports.
- Stable outputs from #7/#11/#12/#13/#14/#16/#17/#18 → #22 integration.
- #16 → #23 test framework; tests expand as each module lands.
- #22/#23 plus #8/#20/#21 → #25 final demo. Copilot can be omitted from the live demo if it threatens core scientific reliability.

## Critical engineering rules

1. **Do not integrate unstable interfaces.** Agree and version JSON contracts before connecting independently developed modules.
2. **Do not treat synthetic data as lunar observations.** Mark mock fixtures as synthetic in every fixture and UI.
3. **Do not overstate dataset resolution or coverage.** Record the actual product, footprint, projection, resolution, vertical datum and nodata value.
4. **Separate evidence classes:** source-observed data, ephemeris-derived values, terrain-derived values, model estimates and user assumptions.
5. **Unknown is not zero or safe.** Missing terrain coverage, kernel coverage or model inputs must remain unknown/not evaluated.
6. **Keep large data outside Git.** Store retrieval scripts, metadata, provenance and checksums; ignore raw DEMs, imagery, kernels and caches.
7. **Use issue-linked branches and pull requests.** Example branch: `feat/7-terrain-processing-pipeline`; PR must reference `Closes #7`.
8. **Review scientific outputs as well as code.** Check units, frames, epoch, coordinate convention, provenance and validation evidence.

## Definition of Done

An issue is complete only when:
- Its acceptance criteria are satisfied.
- Code/documentation is committed on an issue-specific branch.
- Relevant automated tests pass.
- Data sources, assumptions, units and limitations are documented.
- A pull request is reviewed and merged.
- The Project item is moved to Done after verification.

## Schedule management

No fixed submission or demonstration date is encoded in this plan because none was supplied with the task allocation. Use the phases and dependency gates above as the schedule backbone. Once the actual deadline is known, assign calendar dates by backward-planning from the demo and reserve time for integration, validation and rehearsal.
