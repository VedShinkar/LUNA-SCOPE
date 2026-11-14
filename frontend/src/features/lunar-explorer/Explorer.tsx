import {
  Aperture, ArrowLeft, ArrowUp, Compass, Crosshair, Eye, Flag, Layers3, Maximize, Minimize, Mountain,
  PanelLeftClose, PanelLeftOpen, PanelRightOpen, RotateCcw, Ruler, ScanLine, SlidersHorizontal,
} from 'lucide-react'
import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { getGrid, getHorizon, getPoint, type Horizon, type LayerName, type MapPoint, type TerrainGrid, type TerrainPoint } from '../../services/terrain'
import type { Hit, Selected } from '../../visualization/TerrainScene'
import { Inspector, format, type Result } from './Inspector'
import { LandingPanel } from './LandingPanel'
import { layerBand, layerNames, layerStyle, sampleLabel } from './layers'
import { loadProfile, type Coordinates, type Profile } from '../../services/lunar'
import { polarCoordinates } from '../../visualization/lunar-coordinates'
import { ProfilePlot } from './ProfilePlot'

const TerrainScene = lazy(() => import('../../visualization/TerrainScene'))

const modes = [
  { name: 'Explore', icon: Compass, layer: 'elevation' },
  { name: 'Analyze', icon: ScanLine, layer: 'slope' },
  { name: 'Landing Assessment', icon: Flag, layer: 'hazards' },
] as const
type Mode = typeof modes[number]['name']
const analysisLayers: LayerName[] = ['elevation', 'slope', 'aspect', 'roughness', 'horizon', 'coverage', 'uncertainty', 'elevation_uncertainty']
const landingLayers: LayerName[] = ['hazards', 'suitability', 'uncertainty']

class ViewportBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed ? <p className="viewport-message" role="alert">The 3D viewport could not start. Check WebGL 2 support and reload.</p> : this.props.children
  }
}

function Legend({ grid, layer, threshold }: { grid: TerrainGrid; layer: LayerName; threshold: number }) {
  const { colors, labels, categorical } = layerStyle(grid, layer, threshold)
  return <div className="legend">
    <div className="legend-title"><Layers3 size={14} /> {layerNames[layer]}{layer === 'roughness' ? ' · 15 m' : ''}</div>
    {categorical ? <div className="legend-swatches">{labels.map((label, index) =>
      <span key={label}><i style={{ background: colors[index] }} />{label}</span>)}
      {layer === 'aspect' && <span><i style={{ background: '#464b57' }} />Flat / unknown</span>}
    </div> : <>
      <div className="legend-gradient" style={{ background: `linear-gradient(90deg, ${colors.join(',')})` }} />
      <div className="legend-labels">{labels.map(label => <span key={label}>{label}</span>)}</div>
    </>}
  </div>
}

function Metadata({ grid }: { grid: TerrainGrid | undefined }) {
  return <footer className="metadata" aria-label="Terrain metadata">
    {grid ? <>
      <div><span>Source dataset</span><a href={grid.source_url} target="_blank" rel="noreferrer">{grid.source}</a></div>
      <div><span>Site</span><strong>{grid.site_id}</strong></div>
      <div><span>Native resolution</span><strong>{grid.source_resolution.join(' × ')} m</strong></div>
      <div><span>Coordinate reference</span><strong title={grid.crs_wkt}>{grid.crs}</strong></div>
      <div><span>Source grid</span><strong>{grid.source_width.toLocaleString()} × {grid.source_height.toLocaleString()}</strong></div>
      <div><span>{grid.sampling.window ? 'Window NoData' : 'NoData'}</span><strong>{format(grid.nodata_percent, 3)}%</strong></div>
      <div title={`${grid.sampling.method}, ${grid.pixel_registration} samples from ${grid.source_file}`}><span>{grid.sampling.window ? 'Display grid · native window' : 'Display grid · decimated'}</span><strong>{grid.width} × {grid.height} · {grid.resolution[0]} m step</strong></div>
    </> : <p>Source metadata appears when the terrain grid loads.</p>}
  </footer>
}

export default function Explorer({ onExit, initialGrid }: { onExit: () => void; initialGrid?: TerrainGrid }) {
  const [mode, setMode] = useState<Mode>('Explore')
  const [layer, setLayer] = useState<LayerName>('elevation')
  const [left, setLeft] = useState(true)
  const [right, setRight] = useState(() => window.innerWidth > 850)
  const [resolution, setResolution] = useState(256)
  const [nativeCentre, setNativeCentre] = useState<MapPoint>()
  const [exaggeration, setExaggeration] = useState(1)
  const [threshold, setThreshold] = useState(15)
  const [contours, setContours] = useState(false)
  const [reset, setReset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [heading, setHeading] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [expandedViewport, setExpandedViewport] = useState(false)
  const [gridState, setGridState] = useState<Result<TerrainGrid>>({ data: initialGrid })
  const [hover, setHover] = useState<Hit | null>(null)
  const [selected, setSelected] = useState<Selected | null>(null)
  const [point, setPoint] = useState<Result<TerrainPoint>>({})
  const [horizon, setHorizon] = useState<Result<Horizon>>({})
  const [measure, setMeasure] = useState(false)
  const [path, setPath] = useState<Coordinates[]>([])
  const [profile, setProfile] = useState<Result<Profile>>({})
  const viewport = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (path.length !== 2) return
    const controller = new AbortController()
    loadProfile(path[0], path[1], 'site04', controller.signal).then(data => setProfile({ data })).catch(error => {
      if (!controller.signal.aborted) setProfile({ error: error.message })
    })
    return () => controller.abort()
  }, [path])
  useEffect(() => {
    if (initialGrid && resolution === 256 && retry === 0 && !nativeCentre) {
      setGridState({ data: initialGrid })
      return
    }
    const controller = new AbortController()
    getGrid(nativeCentre ? 256 : resolution, controller.signal, nativeCentre).then(data => setGridState({ data })).catch(error => {
      if (!controller.signal.aborted) setGridState({ error: error.message })
    })
    return () => controller.abort()
  }, [resolution, retry, initialGrid, nativeCentre])
  useEffect(() => {
    if (!selected) return
    const controller = new AbortController()
    getPoint(selected, controller.signal).then(data => setPoint({ data })).catch(error => {
      if (!controller.signal.aborted) setPoint({ error: error.message })
    })
    return () => controller.abort()
  }, [selected])
  useEffect(() => {
    if (!selected || layer !== 'horizon') return
    const controller = new AbortController()
    getHorizon(selected, controller.signal).then(data => setHorizon({ data })).catch(error => {
      if (!controller.signal.aborted) setHorizon({ error: error.message })
    })
    return () => controller.abort()
  }, [selected, layer])
  useEffect(() => {
    const changed = () => setFullscreen(document.fullscreenElement === viewport.current)
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpandedViewport(false)
    }
    document.addEventListener('fullscreenchange', changed)
    window.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('fullscreenchange', changed)
      window.removeEventListener('keydown', escape)
    }
  }, [])

  const selectPoint = useCallback((hit: Hit) => {
    if (measure) {
      setProfile({})
      const coordinates = polarCoordinates(hit.easting, hit.northing)
      setPath(previous => previous.length === 2 ? [coordinates] : [...previous, coordinates])
    }
    setPoint({})
    setHorizon({})
    setSelected({ easting: hit.easting, northing: hit.northing, elevation: hit.elevation })
    setRight(true)
  }, [measure])
  async function toggleFullscreen() {
    if (expandedViewport) {
      setExpandedViewport(false)
      return
    }
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else if (viewport.current?.requestFullscreen) await viewport.current.requestFullscreen()
      else setExpandedViewport(true)
    } catch {
      setExpandedViewport(true)
    }
  }
  function changeLayer(next: LayerName) {
    setLayer(next)
    setHover(null)
    if (next === 'horizon') setRight(true)
  }

  const grid = gridState.data
  const renderLayer = layer === 'horizon' || (grid && !layerBand(grid, layer)) ? 'elevation' : layer
  const activeLayers = mode === 'Explore' ? ['elevation'] as const : mode === 'Analyze' ? analysisLayers : landingLayers
  const status = grid ? 'Terrain loaded' : gridState.error ? 'Terrain unavailable' : 'Loading terrain'

  return <div className="app-shell">
    <a href="#terrain-viewport" className="skip">Skip to terrain viewport</a>
    <header className="topbar">
      <div className="identity"><span className="brand-icon"><Aperture size={22} strokeWidth={1.6} /></span><strong>LUNA-SCOPE</strong></div>
      <div className="top-divider" />
      <h1>Lunar Explorer</h1>
      <div className="top-actions">
        <button className="lunar-return" aria-label="Return to lunar south pole" onClick={onExit}><ArrowLeft size={15} /> <span>South pole</span></button>
        <span className="site-chip">{grid?.site_id ?? 'Site04'}</span>
        <span className={`data-status ${gridState.error ? 'bad' : ''}`} role="status"><i />{status}</span>
        <button className="icon-button" aria-label="Full screen" title="Full screen" onClick={toggleFullscreen}><Maximize size={17} /></button>
      </div>
    </header>
    <main className={`workspace ${left ? '' : 'left-closed'} ${right ? '' : 'right-closed'}`}>
      {left && <aside className="side controls" aria-label="Terrain controls">
        <div className="panel-heading"><span>Workspace</span><button className="icon-button" aria-label="Collapse controls" title="Collapse controls" onClick={() => setLeft(false)}><PanelLeftClose size={17} /></button></div>
        <div className="panel-body">
          <div className="eyebrow">Operating mode</div>
          <div className="mode-list">
            {modes.map(({ name, icon: Icon, layer: initial }) => <button key={name} className="mode"
              aria-pressed={mode === name} onClick={() => { setMode(name); changeLayer(initial) }}>
              <Icon size={17} /><span>{name}</span>
            </button>)}
          </div>
          <div className="control-group">
            <div className="eyebrow"><Layers3 size={14} /> Terrain layers</div>
            <div className="layer-list">
              {activeLayers.map(item => <button key={item} className="layer" aria-pressed={layer === item} onClick={() => changeLayer(item)}>
                <span>{layerNames[item]}{item === 'roughness' ? ' · 15 m' : ''}</span>
                {grid && item !== 'horizon' && !layerBand(grid, item) ? <small>Unavailable</small> : <Eye size={15} />}
              </button>)}
            </div>
            {grid && layer !== 'horizon' && !layerBand(grid, layer) && <p role="status" className="error">{grid.unavailable[layer === 'suitability' ? 'slope' : layer] ?? 'Layer unavailable.'} Showing elevation.</p>}
          </div>
          {mode === 'Landing Assessment' && <LandingPanel threshold={threshold} onChange={value => { setThreshold(value); changeLayer('suitability') }} />}
          <div className="control-group display-controls">
            <div className="eyebrow"><SlidersHorizontal size={14} /> Display</div>
            <label htmlFor="exaggeration">Vertical exaggeration <output>{exaggeration.toFixed(1)}×</output></label>
            <input id="exaggeration" type="range" min="1" max="4" step="0.1" value={exaggeration}
              onChange={event => { setExaggeration(Number(event.target.value)); setHover(null) }} />
            <label htmlFor="detail">Display detail</label>
            <select id="detail" value={resolution} disabled={Boolean(nativeCentre)} onChange={event => {
              setResolution(Number(event.target.value)); setGridState({}); setHover(null)
            }}>
              <option value={128}>Coarse · up to 128</option>
              <option value={256}>Standard · up to 256</option>
              <option value={384}>Fine · up to 384</option>
            </select>
            {mode === 'Explore' && <label className="checkbox"><input type="checkbox" checked={contours} onChange={event => setContours(event.target.checked)} /> 200 m contours</label>}
            <button className="layer native-window" disabled={!selected && !nativeCentre} onClick={() => {
              setGridState({}); setHover(null)
              setNativeCentre(nativeCentre ? undefined : selected ?? undefined)
            }}>{nativeCentre ? 'Show full Site04' : 'Inspect selected area at 5 m'}</button>
            {!selected && !nativeCentre && <p className="muted">Select a point to load a native 5 m window.</p>}
          </div>
          <div className="control-group">
            <button className="layer" aria-pressed={measure} onClick={() => { setMeasure(value => !value); setPath([]); setProfile({}) }}>
              <Ruler size={15} /> Measure a path
            </button>
            {measure && (profile.data ? <ProfilePlot profile={profile.data} /> :
              <p className={profile.error ? 'error' : 'muted'}>{profile.error ?? (path.length === 2 ? 'Sampling native Site04 elevations…' : path.length ? 'Select the end point.' : 'Select two points on the terrain.')}</p>)}
          </div>
        </div>
      </aside>}
      <div className={`viewport ${expandedViewport ? 'viewport-expanded' : ''}`} id="terrain-viewport" ref={viewport} tabIndex={-1}>
        <div className="viewport-heading">
          {!left && <button className="icon-button" aria-label="Expand controls" title="Expand controls" onClick={() => setLeft(true)}><PanelLeftOpen size={18} /></button>}
          <div><div className="eyebrow"><Mountain size={15} /> South polar region</div><h2>{grid?.site_name ?? 'Shackleton Rim'}</h2></div>
        </div>
        <div className="viewport-actions">
          <button className="icon-button" aria-label="Reset camera" title="Reset camera" onClick={() => { setReset(value => value + 1); setHover(null) }}><RotateCcw size={17} /></button>
          <button className="icon-button" aria-label={fullscreen || expandedViewport ? 'Exit full screen' : 'Full screen viewport'} title={fullscreen || expandedViewport ? 'Exit full screen' : 'Full screen viewport'} onClick={toggleFullscreen}>{fullscreen || expandedViewport ? <Minimize size={17} /> : <Maximize size={17} />}</button>
          {!right && <button className="icon-button" aria-label="Expand inspector" title="Expand inspector" onClick={() => setRight(true)}><PanelRightOpen size={18} /></button>}
        </div>
        {grid ? <ViewportBoundary><Suspense fallback={<p className="viewport-message" role="status">Preparing the 3D viewport…</p>}><TerrainScene grid={grid} layer={renderLayer} threshold={threshold}
          exaggeration={exaggeration} contours={contours} reset={reset} selected={selected}
          onHover={setHover} onSelect={selectPoint} onHeading={setHeading} fromGlobe={Boolean(initialGrid)} /></Suspense></ViewportBoundary> :
          <div className="viewport-message" role="status">
            {gridState.error ? <><p>{gridState.error}</p><button onClick={() => { setGridState({}); setRetry(value => value + 1) }}>Retry terrain load</button></> : 'Loading the processed Site04 elevation grid…'}
          </div>}
        {grid && <>
          <div className="north-compass" title="Grid north"><span>N</span><ArrowUp size={23} strokeWidth={1.5} style={{ transform: `rotate(${heading}deg)` }} /></div>
          <Legend grid={grid} layer={renderLayer} threshold={threshold} />
          <div className="gestures"><Crosshair size={13} /> Drag to orbit · Right-drag to pan · Scroll to zoom</div>
          {hover && <div className="hover-tooltip" style={{ left: `clamp(8px, ${hover.x + 14}px, 100% - 204px)`, top: `clamp(76px, ${hover.y + 12}px, 100% - 85px)` }}>
            <strong>{format(hover.elevation, 1)} m <small>mesh elevation</small></strong>
            <span>E {format(hover.easting, 1)} · N {format(hover.northing, 1)}</span>
            {renderLayer !== 'elevation' && <span>{sampleLabel(renderLayer, layerBand(grid, renderLayer)?.values[hover.index], threshold)}</span>}
          </div>}
        </>}
      </div>
      {right && <Inspector grid={grid} selected={selected} point={point} horizon={horizon} showHorizon={layer === 'horizon'}
        landing={mode === 'Landing Assessment'} threshold={threshold} close={() => setRight(false)} />}
    </main>
    <Metadata grid={grid} />
  </div>
}
