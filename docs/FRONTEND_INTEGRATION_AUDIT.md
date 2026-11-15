# Frontend integration audit

Reviewed the worktree on `feature/horizons-validation-pilot` before redesign. Existing modified and untracked files span the lunar survey, terrain, celestial, solar, Earth, timeline, Horizons validation and mission decision code. The React app has one URL entry point and switches views in `LunarExperience`. There is no client-side router. FastAPI includes the terrain, celestial, illumination, communication and timeline routers.

| Frontend view | Existing data and interaction |
| --- | --- |
| Opening survey and polar approach | LOLA and lunar imagery, native point and profile requests, site locator, retained site selection. The globe's visual lighting is illustrative. |
| Site terrain | Site-specific native and display grids, layer controls, NoData and uncertainty indicators, point inspector, horizon, cross-sections, camera controls and measurement history. |
| Comparative Terrain Analysis | Native site grids and statistics plus archived full-raster metrics. The old archive includes unavailable placeholder rows for solar availability, Earth visibility and feasibility. |
| Celestial Geometry | Backend geometry and series, UTC selection, local horizon and terrain selection, frames and kernel provenance. |
| Solar Illumination | Point, series and region requests. The comparison runs the same existing series request for each site. |
| Earth Communication | Point, series and region requests with visibility criteria, an independent antenna mask and uncertainty information. |
| Operations timeline | Real site and three-site results, UTC intervals and brackets, local profile save/load, manual events, reports and exports. The browser inspects the returned timeline locally and requests refinement through the calculation options. |
| Scientific reports and measurement history | Report dialogs use native API data and the verified CSV and browser print paths. Measurement history uses local storage. Individual reports are contextual to the analysis that generated them. |
| Mission Intelligence, Scenario Comparison, Mission Copilot | Feature directories contain documentation only. The Python decision engine and Copilot response functions exist, but no mounted HTTP route exposes them. |

The following inventory describes the mounted routes, as read from `backend/app/main.py` and `backend/app/api/routes`. Generated documentation endpoints are omitted.

| API prefix | Methods and paths | Existing contract |
| --- | --- | --- |
| Root | GET `/health` | Service status. |
| `/terrain` | GET `/site`, `/summary`; POST `/point`, `/horizon` | Site selection and typed terrain point, horizon and summary responses. |
| `/terrain/explorer` | GET `/context`, `/moon/albedo`, `/moon/elevation`, `/polar`, `/surface`, `/statistics`, `/comparison`, `/grid`; POST `/profile`, `/cross-section` | Global and polar context, image, raster grids, native samples, statistics and sampled paths. Profile and cross-section accept typed point lists. |
| `/terrain/explorer/celestial` | GET `/metadata`; POST `/geometry`, `/series` | Metadata and typed observer, UTC geometry, kernel and frame results. |
| `/terrain/explorer/illumination` | POST `/point`, `/series`, `/region` | Typed observer, UTC or series, and bounded native region inputs. Outputs include solar-centre classification, duration, quality flags and provenance. |
| `/terrain/explorer/communication` | GET `/metadata`; POST `/point`, `/series`, `/region` | Typed physical Earth visibility and antenna-eligibility evidence, criterion settings, temporal and spatial summaries. |
| `/terrain/explorer/mission-timeline` | GET/POST `/profile`; POST `/site`, `/compare`, `/inspect`, `/refine` | Typed profile, timeline, comparison and inspection results. |

## Missing contracts and provenance

`decision_engine/engine.py` provides preliminary `assess_site` and `compare_sites` functions. Its adapter reads native terrain, solar and Earth evidence and records the distinction between provisional and insufficient data. The current public API has no assessment, scenario, equipment configuration or profile catalog route for this engine. `ai_copilot/copilot.py` exposes structured Python helpers for terrain, illumination, communication and assessments. The app does not mount an assistant endpoint or define an HTTP conversation contract. No browser request can invoke the Python helpers directly. The existing Horizons validation modules likewise have no mounted public endpoint.

The decision-engine test suite uses synthetic fixtures to exercise scoring, provenance and missing inputs. The served science views use backend results, and the Demonstration timeline profile supplies assumptions to real calculations. The globe's illustrative light and the manual events are not scientific observations. There is no shared provenance enum across routers. Preserve each service's dataset, reference-frame, quality and state fields.

## Visual findings and order of work

The terrain viewport uses a three-column instrument layout, while the observatories use a separate page shell with repeated navigation, large headings and blue panel fills. Site state comes from the survey on entry but becomes local in each science view. Switching views can lose a science site's observer selection. The terrain controls, locator, viewport toolbar and inspector compete for visual priority on smaller screens.

1. Unify post-entry navigation and retain the active site and projected observer within the existing React view flow.
2. Apply a secondary-only graphite palette and reuse the current controls, using CSS for pointer-reactive glass.
3. Refine the terrain layout and expose existing analysis, reports and history from it. Preserve the viewport renderer and scientific clients.
4. Add clear availability states for assessment, scenario and Copilot. Live integration depends on a mounted, agreed HTTP contract.
5. Verify the existing flows with the local application and run frontend, backend, build and diff checks.
