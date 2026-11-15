# Frontend

The lunar observatory and Site04 explorer use React, TypeScript, Vite, and React Three Fiber. GSAP drives camera flights and reuses two tweens for pointer parallax. OrbitControls handles drag, zoom, and touch gestures.

The `src/` structure separates reusable UI, feature modules, API clients, visualization utilities, and shared types. The frontend should display backend results and should not independently reimplement scientific calculations.

## Run locally

With the backend requirements installed and the Site04 raw and processed rasters in their usual repository paths, run this from the repository root:

```powershell
python scripts/download_lunar_experience.py
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open [the local explorer](http://127.0.0.1:5173). The Vite server proxies `/terrain` to the local backend. Set `LUNA_TERRAIN_API` to change that backend address. For a built deployment, serve `dist/` and route `/terrain` to FastAPI on the same origin. Run `npm test` and `npm run build` from this directory.

## Landing-site display grids

`GET /terrain/explorer/grid?site_id=Site11&max_dimension=256` returns a row-major grid with source and output affine coefficients in Rasterio order `[a,b,c,d,e,f]`. Site04 remains the API default for older clients. The catalog also registers Site23. A vertex at column `c` and row `r` maps to the output affine at `(c+0.5,r+0.5)`. The source and output grid use the same lunar CRS. The payload includes resolution, dimensions, WKT, NoData, observation support, layer provenance, and the sampling stride and offset. Unknown sites return 404; unavailable grids return 503.

Sampling selects exact native cell values at a regular stride. The 256-sample bound yields a 246 × 246 mesh with 65 m spacing on Site04. Each sampled cell has a validity flag, and each display quad is masked if any native elevation cell it spans is invalid. Scientific and hazard overlays use the same sample indices and preserve their own nulls. Small features can be missed by display sampling.

Hover shows the displayed mesh elevation. Selecting a point queries the selected site's native grid with its projected coordinates. The 200 m contours follow the displayed mesh. The local horizon is a point profile returned by the existing backend. The landing assessment uses the existing combined screening classes and a configurable slope-only mission assumption. The browser does not infer candidate regions from these layers.

## Lunar context

The initial view uses the [NASA SVS CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/). Its zero-centred cylindrical `ldem_4.tif` provides 1440 × 720 pixel-centred elevations at 0.25° spacing. The server converts kilometre offsets to metres relative to the 1,737.4 km reference sphere. The 2025 appearance image uses LROC WAC between 70°S and 70°N and LOLA reflectance towards the poles. It is a visual layer. The camera and graticule use planetocentric latitude and east-positive longitude. The Sun direction is illustrative.

The regional source is [NASA PDS LOLA LDEM_85S_40M V2.0](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/), nominally 85°S to the pole. The PDS label specifies a 7,584 × 7,584 pixel-registered grid, 40 m spacing, a DE421 mean-Earth/polar-axis frame, and 0.5 m per stored unit above a 1,737,400 m reference sphere. The loader retains the PDS affine and masks -32768. It serves two bounded windows with display spacing of 640 m and 160 m. The renderer transforms projected samples to spherical positions, blends display heights across window margins, and draws the result as one connected mesh. The central polar view uses neutral shading to avoid stretching the coarse appearance raster around the pole. Site04 enters as a separate inspection workspace after the spherical approach. Its native queries, masks, and scientific layers remain authoritative.

Global hover and selection intersect the rendered mesh, convert the hit to body-fixed planetocentric coordinates, and request `GET /terrain/explorer/surface` for the nearest native LOLA cell. The returned elevation can differ from the interpolated mesh height. The interface requests the native polar source at or below 85°S once polar data is loaded; elsewhere it uses the global source. Use Ctrl+K (Cmd+K on macOS) for destinations, layers, and actions. The observatory also accepts decimal `latitude, longitude` in the palette.

The [Dayward, Thermo, and Glass AI references](https://threeui.com/buttons?sort=recent) and [Liquid Glass gallery](https://21st.dev/community/components/explore/liquid-glass-ui-components) informed the control review. The [Liquid Metal reference](https://www.jolyui.dev/docs/components/buttons/liquid-metal-button) suggested a clear primary treatment; the app uses a static CSS gradient with a short hover transition instead of mounting a shader for each button. Secondary controls use dark translucent surfaces. Both share focus, pressed, and disabled states and respect reduced motion.

The Deep Space Observatory uses three sparse point clouds in the lunar scene, with varied size and brightness and different camera follow rates. The sky is illustrative and stays still when the renderer is idle. A fixed key, subdued fill and narrow rim highlight show relief; they are not an illumination or visibility model. Malapert Massif and de Gerlache Rim 1 are navigation targets from [NASA’s Lunar Surface Data Book](https://ntrs.nasa.gov/citations/20230007818) (R23 and R11). The native terrain workspace remains Site04.

Two-point profiles use the short spherical geodesic and 128 evenly spaced samples from the selected source. Each sample uses the nearest native cell. Nulls appear as gaps. A profile represents the sampled path at the source resolution and can miss features between samples.

In any local terrain workspace, select a point and choose **Inspect selected area at 5 m** to load a 256 × 256 native window with its aligned science layers. The window is clamped to that site's raster bounds. The full site grid remains decimated for display. NASA supplied slope and calculated slope are separate layers. Site23's uncertainty GeoTIFFs have equivalent projection parameters but different CRS encodings; identical affine and dimensions are still required, and no resampling is performed.

The site comparison displays archived whole-grid metrics, not statistics from the current display mesh. Operations timeline events are entered by the user and held for the workspace session. Celestial geometry, illumination and communication pages mark calculations unavailable until validated ephemerides are configured.

The [Joly UI Liquid Metal Button](https://www.jolyui.dev/docs/components/buttons/liquid-metal-button) informed the featured action, which uses the published Paper Shaders implementation in a small, pixel-bounded canvas. The button has a CSS fallback; secondary actions and repeated inspection controls do not create WebGL contexts. The nebula is an original in-scene adaptation of the [Interactive Nebula reference](https://21st.dev/community/components/dhiluxui/liquid-shader), and uses the Moon’s demand-driven render loop. The illustrative [Celestial Sphere reference](https://preview.21st.dev/%40dhileepkumargm/components/celestial-sphere) informed a separate original shader and point field; that workspace replaces the lunar viewport and stops its animation when hidden or when reduced motion is requested. The illustrative effects are separate from scientific calculations.
