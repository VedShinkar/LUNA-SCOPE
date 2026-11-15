import {
  Aperture, ArrowLeft, ArrowUp, Compass, Crosshair, Eye, Flag, Layers3, Maximize, Minimize, Mountain,
  PanelLeftClose, PanelLeftOpen, PanelRightOpen, RotateCcw, Ruler, ScanLine, SlidersHorizontal,
} from 'lucide-react'
import { Component, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { LunarLocator } from './LunarLocator'
import { layerPresets, supportedLayers, type LayerPreset, type Measurement } from './survey-tools'
import { getGrid, getHorizon, getPoint, type Horizon, type LayerName, type MapPoint, type TerrainGrid, type TerrainPoint } from '../../services/terrain'
import type { Hit, Selected } from '../../visualization/TerrainScene'
import { Inspector, format, type Result } from './Inspector'
import { LandingPanel } from './LandingPanel'
import { layerBand, layerNames, layerStyle, sampleLabel } from './layers'
import { loadCrossSection, type Coordinates, type LunarSite, type Profile } from '../../services/lunar'
import { ReportActions } from './ScientificReport'
import { polarCoordinates, polarPosition } from '../../visualization/lunar-coordinates'
import { ProfilePlot } from './ProfilePlot'
import { CommandPalette } from '../../components/CommandPalette'
import { LiquidMetalButton } from '../../components/ui/liquid-metal-button'
import { GlassSurface, LiquidGlassButton } from '../../components/ui/liquid-glass'
import { siteCode, siteName } from './copy'
import { WorkspaceNavigation, type ScienceSelection, type WorkspaceId } from './WorkspaceNavigation'
import './analysis-workspace.css'

const TerrainScene = lazy(() => import('../../visualization/TerrainScene'))

const modes = [
  { name: 'Elevation', icon: Compass, layer: 'elevation' },
  { name: 'Terrain Metrics', icon: ScanLine, layer: 'slope' },
  { name: 'Landing Assessment', icon: Flag, layer: 'hazards' },
] as const
type Mode = typeof modes[number]['name']
const analysisLayers: LayerName[] = ['elevation', 'slope', 'nasa_slope', 'aspect', 'roughness', 'roughness_35m', 'roughness_75m', 'horizon', 'coverage', 'uncertainty', 'elevation_uncertainty']
const landingLayers: LayerName[] = ['hazards', 'suitability', 'roughness_screen', 'coverage', 'elevation_uncertainty', 'uncertainty']

class ViewportBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onError() }
  render() {
    return this.state.failed ? <p className="viewport-message" role="alert">The 3D viewport could not start. Check WebGL 2 support and reload.</p> : this.props.children
  }
}

function Legend({ grid, layer, threshold, range, ramp, roughness }: { grid: TerrainGrid; layer: LayerName; threshold: number; range?:[number,number]; ramp:'default'|'ice'; roughness:number }) {
  const { colors, labels, categorical } = layerStyle(grid, layer, threshold, range, ramp, roughness)
  const band = layerBand(grid,layer)
  return <div className="legend">
    <div className="legend-title"><Layers3 size={14} /> {layerNames[layer]}{layer === 'roughness' ? ' · 15 m' : ''}</div>
    {categorical ? <div className="legend-swatches">{labels.map((label, index) =>
      <span key={label}><i style={{ background: colors[index] }} />{label}</span>)}
      {layer === 'aspect' && <span><i style={{ background: '#464b57' }} />Flat / unknown</span>}
    </div> : <>
      <div className="legend-gradient" style={{ background: `linear-gradient(90deg, ${colors.join(',')})` }} />
      <div className="legend-labels">{labels.map(label => <span key={label}>{label}</span>)}</div>
    </>}
    {grid.layer_sources[layer] && <div className="legend-provenance" title={grid.layer_sources[layer]?.file}>{layer === 'uncertainty' || layer === 'elevation_uncertainty' ? 'NASA-supplied RMS uncertainty raster' : grid.layer_sources[layer]?.kind === 'raw' ? 'NASA source raster' : 'Processed LOLA layer'}</div>}
    <div className="legend-provenance">NoData · gray or gaps{band?.range && ` · Display samples ${format(band.range[0],2)}–${format(band.range[1],2)} ${band.unit}`}</div>
  </div>
}

function Metadata({ grid }: { grid: TerrainGrid | undefined }) {
  return <footer className="metadata" aria-label="Terrain metadata">
    {grid ? <>
      <div><span>Source dataset</span><a href={grid.source_url} target="_blank" rel="noreferrer">{grid.source}</a></div>
      <div><span>Site</span><strong>{siteCode(grid.site_id)}</strong></div>
      <div><span>Terrain Resolution</span><strong>{grid.source_resolution.join(' × ')} m/px</strong></div>
      <div><span>Coordinate reference</span><strong title={grid.crs_wkt}>{grid.crs}</strong></div>
      <div><span>Source grid</span><strong>{grid.source_width.toLocaleString()} × {grid.source_height.toLocaleString()}</strong></div>
      <div><span>{grid.sampling.window ? 'Window NoData' : 'NoData'}</span><strong>{format(grid.nodata_percent, 3)}%</strong></div>
      <div><span>Direct LOLA support</span><strong>{grid.observation_support ? `${format(grid.observation_support.direct_percent, 1)}%` : 'Unavailable'}</strong></div>
      <div title={`${grid.sampling.method}, ${grid.pixel_registration} samples from ${grid.source_file}`}><span>{grid.sampling.window ? 'Display grid · native window' : 'Display grid · decimated'}</span><strong>{grid.width} × {grid.height} · {grid.resolution[0]} m step</strong></div>
    </> : <p>Source metadata appears when the terrain grid loads.</p>}
  </footer>
}

export default function Explorer({ onExit, initialGrid, initialView, site, sites, onSiteChange, onSave, onHistory, historyPanel, restored, initialPoint, onSelection, onWorkspace }: {
  onExit: () => void; initialGrid?: TerrainGrid; site: LunarSite; sites: LunarSite[]; onSiteChange: (site: LunarSite) => void
  initialView?:'close'|'overhead'; onSave:(record:Measurement)=>void; onHistory:()=>void; historyPanel:ReactNode
  restored?: Measurement
  initialPoint: ScienceSelection['initialPoint']; onSelection: ScienceSelection['onSelection']; onWorkspace:(id:WorkspaceId)=>void
}) {
  const siteId = site.site_id
  const savedPoint = restored?.kind === 'Terrain sample' ? restored : undefined
  const savedProfile = restored?.kind === 'Elevation profile' ? restored : undefined
  const [restoringPoint, setRestoringPoint] = useState(Boolean(savedPoint))
  const [restoringProfile, setRestoringProfile] = useState(Boolean(savedProfile))
  const [mode, setMode] = useState<Mode>('Elevation')
  const [layer, setLayer] = useState<LayerName>('elevation')
  const [left, setLeft] = useState(true)
  const [right, setRight] = useState(Boolean(savedPoint || initialPoint))
  const [pinned,setPinned]=useState(false)
  const [layerPreset,setLayerPreset]=useState<LayerPreset>()
  const [terrainCamera,setTerrainCamera]=useState<'oblique'|'overhead'>(initialView==='overhead'||restored?'overhead':'oblique')
  const [resolution, setResolution] = useState(256)
  const [nativeCentre, setNativeCentre] = useState<MapPoint | undefined>(()=>initialGrid?.sampling.window&&site.available?{easting:site.easting,northing:site.northing}:undefined)
  const originalWindow=useRef(nativeCentre)
  const [exaggeration, setExaggeration] = useState(1)
  const [threshold, setThreshold] = useState(15)
  const [roughnessThreshold, setRoughnessThreshold] = useState(2)
  const [slopeMax, setSlopeMax] = useState(45)
  const [elevationRamp, setElevationRamp] = useState<'default'|'ice'>('default')
  const [contours, setContours] = useState(false)
  const [reset, setReset] = useState(0)
  const [retry, setRetry] = useState(0)
  const [heading, setHeading] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [expandedViewport, setExpandedViewport] = useState(false)
  const [gridState, setGridState] = useState<Result<TerrainGrid>>({ data: initialGrid })
  const [hover, setHover] = useState<Hit | null>(null)
  const [selected, setSelected] = useState<Selected | null>(() => savedPoint ? { ...savedPoint.projected, elevation: savedPoint.values.elevation_m } : initialPoint ? { ...initialPoint, elevation:null } : null)
  const [point, setPoint] = useState<Result<TerrainPoint>>({data: savedPoint?.values})
  const selectedMarker = useMemo(() => selected && point.data?.is_valid
    ? { ...selected, elevation: point.data.elevation_m }
    : selected, [selected, point.data])
  const [horizon, setHorizon] = useState<Result<Horizon>>({})
  const [measure, setMeasure] = useState(Boolean(savedProfile))
  const [path, setPath] = useState<Coordinates[]>(savedProfile?.coordinates ?? [])
  const [profile, setProfile] = useState<Result<Profile>>({data: savedProfile?.values})
  const [profileCursor, setProfileCursor] = useState<number>()
  const [extendPath, setExtendPath] = useState(false)
  const [palette, setPalette] = useState(false)
  const [renderFailed, setRenderFailed] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (path.length < 2 || restoringProfile) return
    const controller = new AbortController()
    loadCrossSection(siteId, path, controller.signal).then(data => {if (!controller.signal.aborted) setProfile({ data })}).catch(error => {
      if (!controller.signal.aborted) setProfile({ error: error.message })
    })
    return () => controller.abort()
  }, [path, siteId, restoringProfile])
  useEffect(() => {
    if (initialGrid && resolution === 256 && retry === 0 && originalWindow.current === nativeCentre) {
      setGridState({ data: initialGrid })
      return
    }
    const controller = new AbortController()
    getGrid(siteId, nativeCentre ? 256 : resolution, controller.signal, nativeCentre).then(data => setGridState({ data })).catch(error => {
      if (!controller.signal.aborted) setGridState({ error: error.message })
    })
    return () => controller.abort()
  }, [resolution, retry, initialGrid, nativeCentre, siteId])
  useEffect(() => {
    if (!selected || restoringPoint) return
    const controller = new AbortController()
    getPoint(siteId, selected, controller.signal).then(data => {
      if (!controller.signal.aborted) setPoint({ data })
    }).catch(error => {
      if (!controller.signal.aborted) setPoint({ error: error.message })
    })
    return () => controller.abort()
  }, [selected, siteId, restoringPoint])
  useEffect(() => {
    if (!selected || layer !== 'horizon') return
    const controller = new AbortController()
    getHorizon(siteId, selected, controller.signal).then(data => setHorizon({ data })).catch(error => {
      if (!controller.signal.aborted) setHorizon({ error: error.message })
    })
    return () => controller.abort()
  }, [selected, layer, siteId])
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
      setRestoringProfile(false)
      setProfile({})
      setProfileCursor(undefined)
      const coordinates = polarCoordinates(hit.easting, hit.northing)
      setPath(previous => previous.length >= 2 && !extendPath ? [coordinates] : previous.length >= 32 ? previous : [...previous, coordinates])
    }
    if(pinned && !measure)return
    setRestoringPoint(false)
    setPoint({})
    setHorizon({})
    setSelected({ easting: hit.easting, northing: hit.northing, elevation: hit.elevation })
    onSelection(siteId, {easting:hit.easting,northing:hit.northing})
    setRight(true)
  }, [measure,pinned,extendPath,onSelection,siteId])
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
  const profileEndpoints = profile.data ? [path[0], path.at(-1)].flatMap((coordinate, index) => coordinate ? [{
    ...polarPosition(coordinate), elevation: (index ? profile.data!.elevation_m.at(-1) : profile.data!.elevation_m[0]) ?? null,
  }] : []) : undefined
  const renderLayer = layer === 'horizon' ? 'elevation' : layer
  const range = useMemo<[number,number] | undefined>(() => renderLayer === 'slope' || renderLayer === 'nasa_slope' ? [0,slopeMax] : undefined,[renderLayer,slopeMax])
  const cursorPosition = profileCursor === undefined ? undefined : profile.data?.projected?.[profileCursor]
  const cursorElevation = profileCursor === undefined ? null : profile.data?.elevation_m[profileCursor] ?? null
  const profilePath = useMemo(() => profile.data?.projected?.map((position,index)=>({...position,elevation:profile.data!.elevation_m[index]})),[profile.data])
  const reportLayer = ['slope','roughness','coverage','uncertainty','elevation_uncertainty'].includes(layer) ? layer : layer === 'suitability' ? 'slope' : layer === 'roughness_screen' ? 'roughness' : 'elevation'
  const presetLayers=layerPreset&&grid?supportedLayers(layerPreset,l=>Boolean(layerBand(grid,l))):undefined
  const activeLayers = presetLayers?.available ?? (mode === 'Elevation' ? ['elevation'] as const : mode === 'Terrain Metrics' ? analysisLayers : landingLayers)
  function applyLayers(name:LayerPreset){
    if(!grid)return
    setLayerPreset(name);setMode(name==='Landing Assessment'?'Landing Assessment':'Terrain Metrics')
    const {available}=supportedLayers(name,l=>Boolean(layerBand(grid,l)))
    changeLayer(available[0]??layerPresets.find(p=>p.name===name)!.layers[0])
  }
  function selectHazard(layer: LayerName) {
    setLayerPreset(undefined)
    changeLayer(layer)
  }
  function savePoint(){
    if(!selected||!point.data||!grid)return
    if (restoringPoint && savedPoint) { onSave({...savedPoint, id:crypto.randomUUID(), timestamp:new Date().toISOString()}); return }
    onSave({id:crypto.randomUUID(),name:`${siteName(siteId)} terrain sample`,siteId,siteName:site.name,timestamp:new Date().toISOString(),source:grid.elevation_source_url,coordinates:[polarCoordinates(selected.easting,selected.northing)],projected:{easting:selected.easting,northing:selected.northing},kind:'Terrain sample',values:point.data,provenance: gridProvenance()})
  }
  function gridProvenance(sampling = 'Native raster cell') {
    return grid && {productUrl:grid.elevation_source_url,sourceFile:grid.source_file,crs:grid.crs,resolution:grid.source_resolution,sampling}
  }
  function saveProfile(){
    if(path.length<2||!profile.data)return
    if (restoringProfile && savedProfile) { onSave({...savedProfile, id:crypto.randomUUID(), timestamp:new Date().toISOString()}); return }
    onSave({id:crypto.randomUUID(),name:`${siteName(siteId)} elevation profile`,siteId,siteName:site.name,timestamp:new Date().toISOString(),source:profile.data.source,coordinates:path,kind:'Elevation profile',values:profile.data,provenance:gridProvenance(profile.data.sampling)})
  }
  const status = renderFailed ? 'Terrain rendering unavailable' : grid ? Object.keys(grid.unavailable).length ? 'Terrain loaded; some layers unavailable' : `${siteName(siteId)} terrain loaded` : gridState.error ? 'Terrain request failed' : `Loading ${siteName(siteId)} terrain…`

  const commands = [
    { label: 'Return to South Polar Region', group: 'Navigation', run: onExit },
    ...sites.map(item => ({ label: `${item.name} — ${siteCode(item.site_id)}`, group: 'Site', keywords: item.site_id, run: () => onSiteChange(item) })),
    ...modes.map(item => ({ label: `${item.name} Mode`, group: 'Analysis', run: () => {
      setLayerPreset(undefined);setMode(item.name); setLeft(true); changeLayer(item.layer)
    } })),
    ...[...new Set([...analysisLayers, ...landingLayers])].filter(item => item === 'horizon' || (grid && layerBand(grid, item)))
      .map(item => ({ label: layerNames[item], group: 'Layer', run: () => {
        setLayerPreset(undefined);setMode(analysisLayers.includes(item) ? 'Terrain Metrics' : 'Landing Assessment')
        setLeft(true)
        changeLayer(item)
      } })),
    { label: 'Reset camera', group: 'Navigation', run: () => setReset(value => value + 1) },
  ]

  return <div className="app-shell science-workspace analysis-shell terrain-workspace">
    <a href="#terrain-viewport" className="skip">Skip to terrain viewport</a>
    <header className="topbar observatory-bar">
      <div className="identity"><span className="brand-icon"><Aperture size={22} strokeWidth={1.6} /></span><strong>LUNA-SCOPE</strong></div>
      <div className="top-divider" />
      <h1>Site Analysis</h1>
      <div className="top-actions">
        <select className="workspace-site-picker" aria-label="Landing site" value={siteId} onChange={event => {
          const next = sites.find(item => item.site_id === event.target.value)
          if (next) onSiteChange(next)
        }}>{sites.map(item => <option value={item.site_id} key={item.site_id}>{item.name} — {siteCode(item.site_id)}</option>)}</select>
        <LiquidGlassButton className="lunar-return" label="South Polar Region" aria-label="Return to South Polar Region" icon={<ArrowLeft />} onClick={onExit} />
        <LiquidGlassButton className="terrain-history-trigger" icon={<Ruler />} iconOnly label="Measurement History" onClick={onHistory}/>
        <span className={`data-status ${gridState.error || renderFailed ? 'bad' : ''}`} role="status"><i />{status}</span>
        <LiquidGlassButton className="science-search" onClick={() => setPalette(true)} label="Find Location or Analysis Tool" iconOnly><kbd>Ctrl K</kbd></LiquidGlassButton>
        <button className="icon-button" aria-label="Full screen" title="Full screen" onClick={toggleFullscreen}><Maximize size={17} /></button>
      </div>
    </header>
    <WorkspaceNavigation active="terrain" onSelect={onWorkspace}/>
    <main className={`workspace ${left ? '' : 'left-closed'} ${right ? '' : 'right-closed'}`}>
      {left && <GlassSurface as="aside" className="side controls" aria-label="Terrain controls">
        <div className="panel-heading"><span>Terrain controls</span><button className="icon-button" aria-label="Collapse controls" title="Collapse controls" onClick={() => setLeft(false)}><PanelLeftClose size={17} /></button></div>
        <div className="panel-body">
          <div className="eyebrow">Analysis mode</div>
          <div className="mode-list">
            {modes.map(({ name, icon: Icon, layer: initial }) => <button key={name} className="mode"
              aria-pressed={mode === name} onClick={() => { setLayerPreset(undefined);setMode(name); changeLayer(initial) }}>
              <Icon size={17} /><span>{name}</span>
            </button>)}
          </div>
          <div className="control-group">
            <div className="eyebrow"><Layers3 size={14} /> Terrain layers</div>
            <label htmlFor="layer-preset">Scientific Layer Preset</label>
            <select id="layer-preset" value={layerPreset??''} disabled={!grid} onChange={e=>{if(e.target.value)applyLayers(e.target.value as LayerPreset);else setLayerPreset(undefined)}}>
              <option value="">Manual layers</option>{layerPresets.map(p=><option key={p.name}>{p.name}</option>)}
            </select>
            {Boolean(presetLayers?.missing.length)&&<p className="muted">Unavailable: {presetLayers!.missing.map(l=>layerNames[l]).join(', ')}.</p>}
            <div className="layer-list">
              {activeLayers.map(item => <button key={item} className="layer" aria-pressed={layer === item} onClick={() => changeLayer(item)}>
                <span>{layerNames[item]}{item === 'roughness' ? ' · 15 m' : ''}</span>
                {grid && item !== 'horizon' && !layerBand(grid, item) ? <small>Unavailable</small> : <Eye size={15} />}
              </button>)}
            </div>
            {grid && layer !== 'horizon' && !layerBand(grid, layer) && <p role="status" className="error">{grid.unavailable[layer === 'suitability' ? 'slope' : layer] ?? 'Layer unavailable.'} No values displayed.</p>}
          </div>
          {mode === 'Landing Assessment' && <LandingPanel siteId={siteId} threshold={threshold} onChange={value => { setThreshold(value); selectHazard('suitability') }} roughness={roughnessThreshold} onRoughness={value => { setRoughnessThreshold(value); selectHazard('roughness_screen') }} />}
          <div className="control-group display-controls">
            <div className="eyebrow"><SlidersHorizontal size={14} /> Display</div>
            {renderLayer === 'elevation' && <label>Elevation colors <select value={elevationRamp} onChange={e=>setElevationRamp(e.target.value as 'default'|'ice')}><option value="default">Lunar relief</option><option value="ice">Blue relief</option></select></label>}
            {range && <label>Slope display maximum <input type="number" min={1} max={90} value={slopeMax} onChange={e=>setSlopeMax(Math.max(1,Math.min(90,Number(e.target.value))))}/></label>}
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
            {mode === 'Elevation' && <label className="checkbox"><input type="checkbox" checked={contours} onChange={event => setContours(event.target.checked)} /> 200 m contours</label>}
            <LiquidMetalButton className="native-window" shader={false} icon={null} disabled={!selected && !nativeCentre} onClick={() => {
              setGridState({}); setHover(null)
              setNativeCentre(nativeCentre ? undefined : selected ?? undefined)
            }} label={nativeCentre ? 'Show Full Site' : 'Open Native Terrain Window'} />
            {!selected && !nativeCentre && <p className="muted">Select a terrain point to open a 256 × 256 window at 5 m/px.</p>}
          </div>
          <div className="control-group">
            <ReportActions title={`${site.name} · ${reportLayer.includes('uncertainty') || reportLayer === 'coverage' ? 'Data quality and uncertainty' : 'Individual site analysis'}`} sites={[site]} layer={reportLayer} assumptions={mode === 'Landing Assessment' ? `Slope ≤ ${threshold}°, 15 m roughness ≤ ${roughnessThreshold} m` : undefined}/>
            <button className="layer" aria-pressed={measure} onClick={() => { setRestoringProfile(false); setMeasure(value => !value); setPath([]); setProfile({}) }}>
              <Ruler size={15} /> Measure a path
            </button>
            {measure && <><label><input type="checkbox" checked={extendPath} onChange={e=>setExtendPath(e.target.checked)}/> Add intermediate vertices</label>
              <LiquidGlassButton label="Redraw Profile" disabled={!path.length} onClick={()=>{setRestoringProfile(false);setPath([]);setProfile({});setProfileCursor(undefined)}}/>
              {profile.data ? <><ProfilePlot profile={profile.data} activeSample={profileCursor} onSample={setProfileCursor} /><p className="muted">Shift-click near the profile to inspect its closest sample.</p>{restoringProfile && savedProfile?.provenance?.sourceFile && <p className="muted">{savedProfile.provenance.sourceFile}</p>}<LiquidGlassButton label="Save Profile" onClick={saveProfile}/><ReportActions title={`${site.name} · Terrain profile`} sites={[site]} layer="elevation" profile={profile.data}/></> :
              <p className={profile.error ? 'error' : 'muted'}>{profile.error ?? (path.length >= 2 ? `Sampling native ${siteId} elevations…` : path.length ? 'Select the end point.' : 'Select two points on the terrain.')}</p>}</>}
          </div>
        </div>
      </GlassSurface>}
      <div className={`viewport ${expandedViewport ? 'viewport-expanded' : ''}`} id="terrain-viewport" ref={viewport} tabIndex={-1}>
        <div className="viewport-heading">
          {!left && <button className="icon-button" aria-label="Expand controls" title="Expand controls" onClick={() => setLeft(true)}><PanelLeftOpen size={18} /></button>}
          <div><div className="eyebrow"><Mountain size={15} /> South Polar Region · {siteCode(siteId)}</div><h2>{site.name}</h2></div>
        </div>
        <div className="viewport-actions">
          <LiquidGlassButton label="Overhead Inspection" icon={<Crosshair/>} iconOnly aria-pressed={terrainCamera==='overhead'} onClick={()=>setTerrainCamera(v=>v==='overhead'?'oblique':'overhead')}/>
          <button className="icon-button" aria-label="Reset camera" title="Reset camera" onClick={() => { setReset(value => value + 1); setHover(null) }}><RotateCcw size={17} /></button>
          <button className="icon-button" aria-label={fullscreen || expandedViewport ? 'Exit full screen' : 'Full screen viewport'} title={fullscreen || expandedViewport ? 'Exit full screen' : 'Full screen viewport'} onClick={toggleFullscreen}>{fullscreen || expandedViewport ? <Minimize size={17} /> : <Maximize size={17} />}</button>
          {!right && <button className="icon-button" aria-label="Expand inspector" title="Expand inspector" onClick={() => setRight(true)}><PanelRightOpen size={18} /></button>}
        </div>
        {grid ? <ViewportBoundary onError={() => setRenderFailed(true)}><Suspense fallback={<p className="viewport-message" role="status">Preparing the 3D viewport…</p>}><TerrainScene grid={grid} layer={renderLayer} threshold={threshold}
          exaggeration={exaggeration} contours={contours} reset={reset} selected={selectedMarker} profileEndpoints={profileEndpoints} overhead={terrainCamera==='overhead'} colorRange={range} elevationRamp={elevationRamp} roughnessThreshold={roughnessThreshold}
          profilePath={profilePath} profileMarker={cursorPosition && {...cursorPosition,elevation:cursorElevation}}
          onProfilePick={profilePath ? hit => {
            let closest = -1, best = Infinity
            profilePath.forEach((sample, index) => {
              const distance = Math.hypot(sample.easting-hit.easting, sample.northing-hit.northing)
              if (distance < best) { best = distance; closest = index }
            })
            if (closest >= 0 && best <= Math.max(...grid.resolution)) setProfileCursor(closest)
          } : undefined}
          onHover={setHover} onSelect={selectPoint} onHeading={setHeading} fromGlobe={Boolean(initialGrid)} /></Suspense></ViewportBoundary> :
          <div className="viewport-message" role="status">
            {gridState.error ? <><p>{gridState.error}</p><LiquidGlassButton label="Retry Data Retrieval" onClick={() => { setGridState({}); setRetry(value => value + 1) }} /></> : `Loading ${siteName(siteId)} terrain data…`}
          </div>}
        {grid && <>
          <div className="north-compass" title="Grid north"><span>N</span><ArrowUp size={23} strokeWidth={1.5} style={{ transform: `rotate(${heading}deg)` }} /></div>
          {layerBand(grid,renderLayer)&&<Legend grid={grid} layer={renderLayer} threshold={threshold} range={range} ramp={elevationRamp} roughness={roughnessThreshold}/>}
          <LunarLocator sites={sites} siteId={siteId} onSite={next=>{if(next.site_id!==siteId)onSiteChange(next)}} grid={grid}/>
          <div className="gestures"><Crosshair size={13} /> Drag to orbit · Right-drag to pan · Scroll to zoom</div>
          {hover && <div className="hover-tooltip" style={{ left: `clamp(8px, ${hover.x + 14}px, 100% - 204px)`, top: `clamp(76px, ${hover.y + 12}px, 100% - 85px)` }}>
            <strong>{format(hover.elevation, 1)} m <small>mesh elevation</small></strong>
            <span>E {format(hover.easting, 1)} · N {format(hover.northing, 1)}</span>
            {renderLayer !== 'elevation' && <span>{sampleLabel(renderLayer, layerBand(grid, renderLayer)?.values[hover.index], threshold, roughnessThreshold)}</span>}
          </div>}
        </>}
      </div>
      {right && <Inspector grid={grid} selected={selected} point={point} horizon={horizon} showHorizon={layer === 'horizon'}
        landing={mode === 'Landing Assessment'} threshold={threshold} layer={layer} pinned={pinned} onPin={()=>setPinned(v=>!v)} onSave={savePoint} saved={restoringPoint ? savedPoint : undefined} close={() => setRight(false)} />}
    </main>
    <Metadata grid={grid} />
    {historyPanel}
    <CommandPalette commands={commands} open={palette} onOpen={setPalette} />
  </div>
}
