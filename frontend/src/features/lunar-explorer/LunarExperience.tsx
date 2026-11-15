import { Aperture, ArrowDownRight, Camera, Compass, Crosshair, Globe2, Grid2X2, History, Layers3, MapPin, Maximize, Minimize, Mountain, RotateCcw, Ruler, Search, Settings2, X } from 'lucide-react'
import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { loadContext, loadMoon, loadPolar, loadProfile, loadSurface, type LunarSite, type SurfaceSample, type Context, type Coordinates, type PolarGrid, type Profile } from '../../services/lunar'
import type { Destination, SurfaceHit } from '../../visualization/MoonScene'
import { getGrid, type MapPoint, type TerrainGrid } from '../../services/terrain'
import { LunarLocator } from './LunarLocator'
import { MeasurementHistory } from './MeasurementHistory'
import { useMeasurementHistory } from './use-measurement-history'
import { cameraPresets, type CameraPreset, type Measurement } from './survey-tools'
import { CommandPalette, type Command } from '../../components/CommandPalette'
import { ProfilePlot } from './ProfilePlot'
import { LiquidMetalButton } from '../../components/ui/liquid-metal-button'
import { LiquidGlassButton, LiquidGlassDock } from '../../components/ui/liquid-glass'
import { siteCode, siteName } from './copy'
import { usePanelMotion } from '../../components/ui/use-panel-motion'
import type { WorkspaceId } from './WorkspaceNavigation'
import type { ManualEvent } from './MissionWorkspaces'
import type { DecisionContext } from '../../services/mission-intelligence'
import { pointForSite, type WorkspaceObserver } from './workspace-observer'
import './lunar-experience.css'

const MoonScene = lazy(() => import('../../visualization/MoonScene'))
const Explorer = lazy(() => import('./Explorer'))
const MissionWorkspaces = lazy(() => import('./MissionWorkspaces'))
const missionOptions = [ ['comparison', 'Site comparison'], ['celestial', 'Celestial geometry'], ['illumination', 'Solar illumination'], ['communication', 'Earth communication'], ['operations', 'Operations timeline'] ] as const
const initial: Destination = { point: { latitude: -15, longitude: 5 }, distance: 3820 }
const south: Destination = { point: { latitude: -89, longitude: 160 }, distance: 420 }
// IAU Gazetteer of Planetary Nomenclature, feature 5450.
const crater: Destination = { point: { latitude: -89.67, longitude: 129.78 }, distance: 80 }
const formatLocation = ({ latitude, longitude }: Coordinates) =>
  `${Math.abs(latitude).toFixed(2)}° ${latitude < 0 ? 'S' : 'N'} · ${Math.abs(longitude).toFixed(2)}° ${longitude < 0 ? 'W' : 'E'}`

class GlobeBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onError() }
  render() {
    return this.state.failed ? <p className="viewport-message" role="alert">Lunar rendering requires WebGL 2.</p> : this.props.children
  }
}

export default function LunarExperience() {
  const [context, setContext] = useState<Context>()
  const [heights, setHeights] = useState<Float32Array>()
  const [overview, setOverview] = useState<PolarGrid>()
  const [approachResult, setApproach] = useState<{id: string; grid: PolarGrid}>()
  const [siteId, setSiteId] = useState('Site04')
  const [siteGrid, setSiteGrid] = useState<TerrainGrid>()
  const [siteError, setSiteError] = useState('')
  const [error, setError] = useState('')
  const [renderFailed, setRenderFailed] = useState(false)
  const [regionalError, setRegionalError] = useState('')
  const [retry, setRetry] = useState(0)
  const [destination, setDestination] = useState(initial)
  const [viewPoint, setViewPoint] = useState(initial.point)
  const [range, setRange] = useState(3650)
  const [regional, setRegional] = useState(false)
  const [nearPole, setNearPole] = useState(false)
  const [local, setLocal] = useState(false)
  const [localView, setLocalView] = useState<'close' | 'overhead'>()
  const [historyOpen, setHistoryOpen] = useState(false)
  const { history, update: updateHistory } = useMeasurementHistory()
  const [restored, setRestored] = useState<Measurement>()
  const [preset, setPreset] = useState<CameraPreset>('Global Moon')
  const [mission, setMission] = useState<WorkspaceId>()
  const [manualEvents, setManualEvents] = useState<ManualEvent[]>([])
  const [decisionContext, setDecisionContext] = useState<DecisionContext|null>(null)
  const rememberAnalysisEpoch = useCallback((utc:string) => {
    setDecisionContext(previous=>({utc,profile:previous?.profile,equipment:previous?.equipment}))
  }, [])
  const [analysisPoint, setAnalysisPoint] = useState<WorkspaceObserver>(null)
  const analysisSelection = useCallback((nextSite:string, point:MapPoint|null) => {
    setSiteId(nextSite)
    setAnalysisPoint(point ? {siteId:nextSite,point} : null)
  }, [])
  const [imagery, setImagery] = useState(true)
  const [relief, setRelief] = useState(true)
  const [regionalRelief, setRegionalRelief] = useState(true)
  const [graticule, setGraticule] = useState(false)
  const [nebula, setNebula] = useState(true)
  const [metalEffects, setMetalEffects] = useState(true)
  const [fullscreen, setFullscreen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const shell = useRef<HTMLDivElement>(null)
  const [palette, setPalette] = useState(false)
  const [panel, setPanel] = useState<'locations' | 'layers' | 'settings' | 'workspaces' | 'camera' | null>(null)
  usePanelMotion(shell, panel)
  const [hover, setHover] = useState<SurfaceHit | null>(null)
  const [selected, setSelected] = useState<SurfaceHit | null>(null)
  const [hoverSample, setHoverSample] = useState<SurfaceSample>()
  const [hoverError, setHoverError] = useState(false)
  const [selectedSample, setSelectedSample] = useState<SurfaceSample>()
  const [sampleError, setSampleError] = useState(false)
  const [measuring, setMeasuring] = useState(false)
  const [measurement, setMeasurement] = useState<Coordinates[]>([])
  const [profile, setProfile] = useState<Profile>()
  const [revisited,setRevisited]=useState(false)
  const [savedSample,setSavedSample]=useState<Extract<Measurement,{kind:'Terrain sample'}>>()
  const [profileError, setProfileError] = useState('')
  const openSitePending = useRef(false)
  const [sitePending, setSitePending] = useState(false)
  const site = context?.sites.find(item => item.site_id === siteId)
  const approach = approachResult?.id === siteId ? approachResult.grid : undefined
  const regionalSource = (regional || nearPole) && regionalRelief && overview
  const closeRegion = range < 120 && Boolean(approach)

  useEffect(() => {
    const abort = new AbortController()
    loadContext(abort.signal).then(async value => {
      setContext(value)
      const elevation = await loadMoon(value, abort.signal)
      setHeights(elevation)
    }).catch(err => { if (!abort.signal.aborted) setError(err.message) })
    return () => abort.abort()
  }, [retry])

  useEffect(() => {
    if ((!regional && !nearPole) || overview) return
    const abort = new AbortController()
    loadPolar('overview', abort.signal).then(setOverview)
      .catch(err => { if (!abort.signal.aborted) setRegionalError(err.message) })
    return () => abort.abort()
  }, [regional, nearPole, overview, retry])

  useEffect(() => {
    if (!overview || (!regional && !nearPole) || approach) return
    const abort = new AbortController()
    loadPolar('approach', abort.signal, siteId).then(grid => { if (!abort.signal.aborted) setApproach({id: siteId, grid}) })
      .catch(err => { if (!abort.signal.aborted) setRegionalError(err.message) })
    return () => abort.abort()
  }, [regional, nearPole, overview, approach, retry, siteId])

  useEffect(() => {
    if (!sitePending || siteGrid?.site_id === siteId) return
    const abort = new AbortController()
    const centre: MapPoint | undefined = localView && site?.available ? {easting:site.easting,northing:site.northing} : undefined
    getGrid(siteId, 256, abort.signal, centre).then(grid => { if (!abort.signal.aborted) setSiteGrid(grid) }).catch(err => {
      if (!abort.signal.aborted) {
        setSiteError(err.message)
        setSitePending(false)
        openSitePending.current = false
      }
    })
    return () => abort.abort()
  }, [sitePending, siteGrid, siteId, site, localView])

  useEffect(() => {
    if (!sitePending || !site?.available || siteGrid?.site_id !== siteId) return
    if (heights && !renderFailed) setDestination({ point: site, distance: 25, enterSite: true })
    else { openSitePending.current = false; setLocal(true) }
    setSitePending(false)
  }, [sitePending, site, siteId, siteGrid, heights, renderFailed])

  useEffect(() => {
    if (measurement.length !== 2 || revisited) return
    const abort = new AbortController()
    loadProfile(measurement[0], measurement[1], regionalSource ? 'polar' : 'moon', abort.signal)
      .then(data=>{if(!abort.signal.aborted)setProfile(data)}).catch(err => { if (!abort.signal.aborted) setProfileError(err.message) })
    return () => abort.abort()
  }, [measurement, regionalSource,revisited])

  useEffect(() => {
    const changed = () => setFullscreen(document.fullscreenElement === shell.current)
    document.addEventListener('fullscreenchange', changed)
    return () => document.removeEventListener('fullscreenchange', changed)
  }, [])

  useEffect(() => {
    if (!expanded) return
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !palette) setExpanded(false) }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [expanded, palette])

  async function toggleFullscreen() {
    if (expanded) { setExpanded(false); return }
    if (fullscreen) { await document.exitFullscreen(); return }
    try {
      if (!shell.current?.requestFullscreen) { setExpanded(true); return }
      await shell.current.requestFullscreen()
    } catch { setExpanded(true) }
  }

  function navigate(next: Destination, polar: boolean) {
    setRestored(undefined)
    openSitePending.current = false
    setSitePending(false)
    setRegional(polar)
    setHover(null)
    setSelected(null)
    setSavedSample(undefined)
    setPanel(null)
    setDestination({ ...next })
    setMeasurement([])
    setRevisited(false)
    setProfile(undefined)
    setProfileError('')
  }
  function chooseSite(next: LunarSite, inspect = false, view?: 'close' | 'overhead') {
    const point = next.available ? next : next.reference
    if (next.site_id !== siteId) setAnalysisPoint(null)
    setSiteId(next.site_id)
    setLocalView(view)
    if (inspect) setSiteGrid(undefined)
    setSiteError('')
    setRegionalError('')
    if (point) navigate({ point, distance: 95 }, true)
    if (!inspect) return
    if (!next.available) { setSiteError(`${siteName(next.site_id)} terrain dataset is unavailable.`); return }
    openSitePending.current = true
    setSitePending(true)
  }
  function switchWorkspaceSite(next: LunarSite) {
    setRestored(undefined)
    analysisSelection(next.site_id, null)
    setSiteError('')
  }
  function applyCamera(next:CameraPreset) {
    setPreset(next)
    if(next==='Global Moon') navigate(initial,false)
    else if(next==='South Polar Overview') navigate(south,true)
    else if(site) chooseSite(site,next!=='Selected Landing Site',next==='Overhead Inspection'?'overhead':next==='Terrain Close-up'?'close':undefined)
  }
  function revisit(record:Measurement) {
    const recordedSite=context?.sites.find(s=>s.site_id===record.siteId)
    const point=record.coordinates[0]
    setLocal(false);setHistoryOpen(false);setMission(undefined)
    navigate({point,distance:point.latitude<=-85?95:550},point.latitude<=-85)
    setSiteError('')
    if (recordedSite?.available) {
      analysisSelection(recordedSite.site_id, record.kind==='Terrain sample' ? record.projected : null)
      if (siteGrid?.site_id !== recordedSite.site_id || siteGrid.sampling.window) setSiteGrid(undefined)
      setLocalView(undefined)
      setRestored(record)
      setLocal(true)
      return
    }
    if (recordedSite) setSiteId(recordedSite.site_id)
    if (record.siteId) setSiteError(`${siteName(record.siteId)} terrain is unavailable. Showing the saved measurement.`)
    if(record.kind==='Terrain sample'){setMeasuring(false);setSelected(point);setSavedSample(record)}
    else {setRevisited(true);setMeasuring(true);setMeasurement(record.coordinates);setProfile(record.values)}
  }
  function saveSurveyProfile() {
    if(!profile||measurement.length!==2)return
    updateHistory({ type: 'save', record: {id:crypto.randomUUID(),name:'Survey elevation profile',siteId:null,timestamp:new Date().toISOString(),source:profile.source,coordinates:measurement,kind:'Elevation profile',values:profile,
      provenance: {sampling: profile.sampling, productUrl: profile.source.includes('Polar') ? context?.polar_source_url : context?.global_source_url} } });setHistoryOpen(true)
  }
  const onArrival = useCallback(() => {
    if (!openSitePending.current) return
    openSitePending.current = false
    setLocal(true)
  }, [])
  const addPoint = useCallback((point: Coordinates) => {
    setRevisited(false)
    setProfile(undefined)
    setProfileError('')
    setMeasurement(previous => previous.length === 2 ? [point] : [...previous, point])
  }, [])
  const onRange = useCallback((altitude: number) => setRange(altitude), [])
  const onView = useCallback((point: Coordinates, altitude: number) => {
    setViewPoint(point)
    setNearPole(point.latitude < -82 && altitude < 850)
  }, [])

  const onHover = useCallback((point: SurfaceHit | null) => {
    setHoverSample(undefined)
    setHoverError(false)
    setHover(point)
  }, [])
  const onSelect = useCallback((point: SurfaceHit) => {
    setSavedSample(undefined)
    setSelectedSample(undefined)
    setSampleError(false)
    setSelected(point)
    setPanel(null)
  }, [])
  useEffect(() => {
    if (!hover || local) return
    const abort = new AbortController()
    loadSurface(hover, overview && hover.latitude <= -85 ? 'polar' : 'moon', abort.signal)
      .then(value => { if (!abort.signal.aborted) setHoverSample(value) })
      .catch(() => { if (!abort.signal.aborted) setHoverError(true) })
    return () => abort.abort()
  }, [hover, overview, local])
  useEffect(() => {
    if (!selected || local || savedSample) return
    const abort = new AbortController()
    loadSurface(selected, overview && selected.latitude <= -85 ? 'polar' : 'moon', abort.signal)
      .then(value => { if (!abort.signal.aborted) setSelectedSample(value) })
      .catch(() => { if (!abort.signal.aborted) setSampleError(true) })
    return () => abort.abort()
  }, [selected, overview, local,savedSample])

  function search(query: string) {
    const pair = query.trim().match(/^([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)$/)
    if (!pair) return false
    const [latitude, longitude] = pair.slice(1).map(Number)
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return false
    navigate({ point: { latitude, longitude }, distance: latitude <= -85 ? 210 : 1100 }, latitude <= -85)
    return true
  }
  function toggleMeasure() {
    setRevisited(false)
    setMeasuring(value => !value)
    setMeasurement([])
    setProfile(undefined)
    setProfileError('')
    setSelected(null)
    setPanel(null)
  }
  const layerOptions = [
    { label: 'LROC Imagery', enabled: imagery, toggle: () => setImagery(value => !value), available: Boolean(context?.imagery) },
    { label: 'Global LOLA Elevation', enabled: relief, toggle: () => setRelief(value => !value), available: Boolean(heights) },
    { label: 'Polar LOLA Elevation', enabled: regionalRelief, toggle: () => setRegionalRelief(value => !value), available: true },
    { label: 'Coordinate Grid', enabled: graticule, toggle: () => setGraticule(value => !value), available: true },
  ]
  const commands: Command[] = [
    { label: 'Global Survey', group: 'Navigation', run: () => navigate(initial, false) },
    { label: 'South Polar Region', group: 'Location', run: () => navigate(south, true) },
    { label: 'Shackleton Crater', group: 'Landmark', run: () => navigate(crater, true) },
    ...(context?.sites ?? []).flatMap(item => [
      { label: `${item.name} — ${siteCode(item.site_id)}`, group: 'Site', keywords: `${item.site_id} fly`, run: () => chooseSite(item) },
      { label: `Open Site Analysis — ${siteCode(item.site_id)}`, group: 'Analysis', keywords: `${item.site_id} ${item.name} terrain inspect`, run: () => chooseSite(item, true) },
    ]),
    ...layerOptions.filter(option => option.available).map(option => ({ label: option.label, group: 'Layer', run: option.toggle })),
    ...missionOptions.map(([id, label]) => ({ label, group: 'Mission', run: () => setMission(id) })),
    ...cameraPresets.filter((_,i)=>i<2||site?.available).map(label=>({label,group:'Camera',run:()=>applyCamera(label)})),
    { label: 'Measure a path', group: 'Tool', keywords: 'distance elevation profile', run: toggleMeasure },
  ]

  const historyPanel=historyOpen&&<MeasurementHistory history={history} update={updateHistory} revisit={revisit} ready={Boolean(context || error)} close={()=>setHistoryOpen(false)}/>
  const carriedPoint = pointForSite(analysisPoint,siteId)
  function openWorkspace(id:WorkspaceId) {
    if (id === 'terrain') {
      setMission(undefined)
      setLocal(true)
    } else {
      setRestored(undefined)
      setMission(id)
    }
  }
  if (mission) return <Suspense fallback={<p className="viewport-message" role="status">Opening mission workspace…</p>}><MissionWorkspaces id={mission} onChange={openWorkspace}
    siteId={siteId} point={carriedPoint} onSelection={analysisSelection} sites={context?.sites ?? []}
    events={manualEvents} setEvents={setManualEvents} decisionContext={decisionContext} onApply={setDecisionContext} onEpoch={rememberAnalysisEpoch}
    onHistory={()=>setHistoryOpen(v=>!v)} historyPanel={historyPanel} onExit={() => { setPanel(null); setMission(undefined); setLocal(false) }} /></Suspense>
  if (local && site) return <Suspense fallback={<div className="app-shell observatory" role="status"><p className="viewport-message">Opening {siteId} terrain…</p></div>}><Explorer key={`${siteId}:${restored?.id ?? ''}`} site={site} sites={context?.sites ?? []} onSiteChange={switchWorkspaceSite} initialGrid={!restored && siteGrid?.site_id === siteId ? siteGrid : undefined} initialView={localView} restored={restored}
    initialPoint={carriedPoint} onSelection={analysisSelection} onWorkspace={openWorkspace} onSave={record=>{updateHistory({type:'save',record});setHistoryOpen(true)}} onHistory={()=>setHistoryOpen(v=>!v)} historyPanel={historyPanel} onExit={() => {
    setLocal(false)
    const point = site.available ? site : site.reference
    if (point) navigate({ point, distance: 95 }, true)
  }} /></Suspense>

  const mode = regional || nearPole ? 'Regional Survey' : 'Global Survey'
  const datasetStatus = renderFailed ? 'Lunar rendering unavailable' : error ? 'Global elevation unavailable' : !heights ? 'Loading global elevation…' : !context?.imagery || regionalError || siteError || site?.available === false ? 'Some datasets unavailable' : 'Global elevation loaded'
  const elevationText = (sample?: SurfaceSample) => sample?.elevation_m == null
    ? 'Elevation unavailable' : `${Math.round(sample.elevation_m).toLocaleString()} m`
  return <div ref={shell} className="app-shell observatory">
    <a href="#moon-viewport" className="skip">Skip to lunar viewport</a>
    <header className="topbar observatory-bar">
      <div className="identity"><span className="brand-icon"><Aperture size={22} strokeWidth={1.5} /></span><span><strong>LUNA-SCOPE</strong><small>Deep Space Observatory</small></span></div>
      <span className="observatory-mode"><Globe2 size={14} /> {mode}</span>
      <div className="top-actions">
        <LiquidGlassButton className="site-launch" label={siteCode(siteId)} aria-label="Select landing site" icon={<MapPin />} aria-expanded={panel === 'locations'} onClick={() => setPanel(value => value === 'locations' ? null : 'locations')} />
        <LiquidGlassButton className="workspace-launch" label="Analysis" icon={<Mountain />} aria-expanded={panel === 'workspaces'} onClick={() => setPanel(value => value === 'workspaces' ? null : 'workspaces')} />
        <span className={`data-status ${error || siteError || renderFailed ? 'bad' : ''}`} role="status"><i />{datasetStatus}</span>
        <LiquidGlassButton className="command-launch" label="Find Location" icon={<Search />} onClick={() => setPalette(true)}><kbd>Ctrl K</kbd></LiquidGlassButton>
        <LiquidGlassButton label="Display Settings" iconOnly icon={<Settings2 />} aria-expanded={panel === 'settings'} onClick={() => setPanel(value => value === 'settings' ? null : 'settings')} />
      </div>
    </header>
    <main id="moon-viewport" className={`viewport observatory-view ${expanded ? 'viewport-expanded' : ''}`} tabIndex={-1}>
      <div className="observatory-title">
        <h1>{regional || nearPole ? 'South Polar Region' : 'Lunar Surface Survey'}</h1>
        <dl className="survey-reference"><div><dt>Reference frame</dt><dd>Moon-fixed · east positive</dd></div><div><dt>Surface layers</dt><dd>{imagery && context?.imagery ? 'LROC imagery' : 'Neutral shading'}{relief ? ' + LOLA relief' : ''}</dd></div></dl>
      </div>
      {context && heights ? <GlobeBoundary onError={() => setRenderFailed(true)}><Suspense fallback={<p className="viewport-message">Initializing lunar view…</p>}>
        <MoonScene context={context} heights={heights} overview={overview}
          approach={approach} activeSite={site} destination={destination}
          imagery={imagery} relief={relief} graticule={graticule} nebula={nebula} regionalRelief={regionalRelief}
          measuring={measuring} measurement={measurement} selected={selected} onHover={onHover} onSelect={onSelect}
          onPoint={addPoint} onRange={onRange} onView={onView} onArrival={onArrival} />
      </Suspense></GlobeBoundary> : <div className="viewport-message" role="status">{error ? <>
        <p>{error}</p><button className="obs-button" onClick={() => { setError(''); setRetry(value => value + 1) }}>Retry lunar data</button>
      </> : 'Loading global LOLA elevation…'}</div>}

      <LiquidGlassDock className="observatory-tools" aria-label="Survey controls">
        <LiquidGlassButton label="Camera Presets" icon={<Camera />} iconOnly aria-expanded={panel==='camera'} onClick={()=>setPanel(p=>p==='camera'?null:'camera')}/>
        <LiquidGlassButton label="Measurement History" icon={<History />} iconOnly aria-expanded={historyOpen} onClick={()=>setHistoryOpen(v=>!v)}/>
        <LiquidGlassButton label="Landing Sites" icon={<Compass />} aria-expanded={panel === 'locations'} onClick={() => setPanel(value => value === 'locations' ? null : 'locations')} />
        <LiquidGlassButton label="Data Layers" icon={<Layers3 />} aria-expanded={panel === 'layers'} onClick={() => setPanel(value => value === 'layers' ? null : 'layers')} />
        <LiquidGlassButton label="Measure" icon={<Ruler />} aria-pressed={measuring} onClick={toggleMeasure} />
        <LiquidGlassButton label="Coordinate Grid" icon={<Grid2X2 />} iconOnly aria-pressed={graticule} onClick={() => setGraticule(value => !value)} />
        <LiquidGlassButton label="Reset View" icon={<RotateCcw />} iconOnly onClick={() => navigate(initial, false)} />
        <LiquidGlassButton label={fullscreen || expanded ? 'Exit Fullscreen' : 'Fullscreen'} icon={fullscreen || expanded ? <Minimize /> : <Maximize />} iconOnly onClick={toggleFullscreen} />
      </LiquidGlassDock>

      {panel && <aside id="observatory-tools-panel" data-enter-panel data-panel={panel} className="observatory-panel floating-tools" aria-labelledby="observatory-panel-title">
        <div className="obs-panel-heading"><h2 id="observatory-panel-title">{panel === 'locations' ? 'Landing Sites' : panel === 'settings' ? 'Display Settings' : panel === 'workspaces' ? 'Analysis' : panel==='camera'?'Camera Presets':'Data Layers'}</h2>
          <LiquidGlassButton label="Close Panel" iconOnly icon={<X />} onClick={() => setPanel(null)} /></div>
        {panel === 'locations' ? <div className="obs-panel-body">
          <LiquidGlassButton className="panel-row" label="Find Location" icon={<Search />} onClick={() => { setPanel(null); setPalette(true) }}><kbd>Ctrl K</kbd></LiquidGlassButton>
          <div className="destination-list">{context?.sites.map(item => <article key={item.site_id} data-selected={siteId === item.site_id}>
            <h3><MapPin size={14} />{item.name}<small>{siteCode(item.site_id)}</small></h3>
            {item.reference && <a href={item.reference.url} title={item.reference.basis}>{formatLocation(item.reference)} · NASA reference</a>}
            <p>{item.available ? `Elevation available · ${item.source_resolution_m.join(' × ')} m/px` : 'Terrain dataset unavailable'}</p>
            <div><LiquidGlassButton label="Center on Site" disabled={!item.available && !item.reference} onClick={() => chooseSite(item)} />
              <LiquidMetalButton shader={false} disabled={sitePending && item.site_id === siteId} aria-label={`Open Site Analysis — ${siteCode(item.site_id)}`} onClick={() => chooseSite(item, true)} label="Open Site Analysis" /></div>
          </article>)}</div>
          <div className="quick-locations">{commands.filter(command => ['Navigation', 'Location', 'Landmark'].includes(command.group)).map(command => <button className="obs-button panel-row" key={command.label} onClick={command.run}>{command.label}</button>)}</div>
        </div> : panel==='camera' ? <div className="obs-panel-body">{cameraPresets.map((name,i)=><LiquidGlassButton className="panel-row" key={name} label={name} aria-pressed={preset===name} disabled={i>=2&&!site?.available} onClick={()=>applyCamera(name)}/>)}</div> : panel === 'workspaces' ? <div className="obs-panel-body">
          <LiquidGlassButton className="panel-row" label="Terrain Analysis" onClick={() => setPanel('locations')} />
          <LiquidMetalButton className="panel-row" shader={false} label="Site Comparison" onClick={() => setMission('comparison')} />
          {missionOptions.filter(([id]) => id !== 'comparison').map(([id, name]) => <LiquidGlassButton key={id} className="panel-row" label={name} onClick={() => setMission(id)} />)}
        </div> : <div className="obs-panel-body">
          {layerOptions.map(option => <label className="layer-option" key={option.label}><span>{option.label}</span>
            <input type="checkbox" disabled={!option.available} checked={option.enabled} onChange={option.toggle} /></label>)}
          {panel === 'settings' && <label className="layer-option">Illustrative nebula<input type="checkbox" checked={nebula} onChange={event => setNebula(event.target.checked)} /></label>}
          {panel === 'settings' && <label className="layer-option">Metal reflections<input type="checkbox" checked={metalEffects} onChange={event => setMetalEffects(event.target.checked)} /></label>}
        </div>}
      </aside>}

      {(selected || measuring) && <aside className="observatory-panel context-inspector" aria-label="Lunar inspector">
        <div className="obs-panel-heading"><h2>{measuring ? 'Elevation Profile' : selected?.landmark ?? 'Terrain Sample'}</h2>
          <LiquidGlassButton label="Close Inspector" iconOnly icon={<X />} onClick={() => { setSelected(null); if (measuring) toggleMeasure() }} /></div>
        <div className="obs-panel-body">
          {measuring ? (profile ? <><ProfilePlot profile={profile} /><LiquidGlassButton label="Save Profile" onClick={saveSurveyProfile}/></> :
            <p className={profileError ? 'error' : 'muted'} role="status">{profileError || (measurement.length === 2 ? 'Sampling the path…' : measurement.length ? 'Select the end point.' : 'Select the start point on the Moon.')}</p>) : selected && <>
            <p className="obs-coordinates">{formatLocation(selected)}</p>
            <div className="obs-elevation">{savedSample ? savedSample.values.elevation_m==null?'Elevation unavailable':`${savedSample.values.elevation_m.toLocaleString()} m` : sampleError ? 'Elevation unavailable' : selectedSample ? elevationText(selectedSample) : 'Sampling elevation…'}</div>
            {savedSample ? <p className="muted">{siteCode(savedSample.siteId ?? '')} · saved native measurement</p> : selectedSample && <p className="muted">{selectedSample.source} · nearest native cell</p>}
            <button className="obs-button obs-primary panel-row" onClick={() => {
              const polar = selected.latitude <= -85
              navigate({ point: selected, distance: polar ? 95 : 550 }, polar)
            }}>Fly to location <ArrowDownRight size={16} /></button>
            {selected.landmark && site && <LiquidMetalButton className="panel-row" shader={false} disabled={sitePending} onClick={() => chooseSite(site, true)}
              label={sitePending ? `Loading ${siteName(siteId)} terrain…` : 'Open Site Analysis'} />}
          </>}
        </div>
      </aside>}

      <div className="observatory-readout" data-hover={Boolean(hover)}>
        {hover ? <><Crosshair size={17} /><div><span>{hover.landmark ?? 'Terrain Sample'}</span><strong>{formatLocation(hover)} <b>{hoverError ? 'Elevation unavailable' : hoverSample ? elevationText(hoverSample) : 'Sampling elevation…'}</b></strong>
          {hoverSample && <small>{hoverSample.source} · native cell</small>}</div></> :
          <><Crosshair size={17} /><div><span>Sub-camera coordinates</span><strong>{formatLocation(viewPoint)}</strong>
            {regionalSource && <small>Polar LOLA · {closeRegion ? approach!.resolution[0] : overview!.resolution[0]} m display</small>}</div></>}
      </div>
      {(siteError || regionalError) && <p className="obs-error" role="alert">{siteError || regionalError}</p>}
      {context && <LunarLocator sites={context.sites} siteId={siteId} onSite={chooseSite}/>}
      {historyPanel}
      <div className="observatory-site">
        <div><span><small>{siteCode(siteId)}</small><strong>{site?.name ?? 'Landing Sites'}</strong>{site && <small>{site.available ? `LOLA · ${site.source_resolution_m[0]} m/px` : 'Terrain dataset unavailable'}</small>}</span></div>
        <LiquidMetalButton shader={metalEffects} disabled={!site || sitePending} onClick={() => site && chooseSite(site, regional)}
          label={sitePending ? `Loading ${siteName(siteId)} terrain…` : regional ? 'Open Site Analysis' : 'Center on Selected Site'} />
      </div>
    </main>
    <footer className="observatory-footer">
      <a href={context?.global_source_url ?? 'https://svs.gsfc.nasa.gov/4720/'}>NASA SVS · LROC / LOLA</a>
      <span>Planetocentric · east-positive</span>
      {site && <span>{siteCode(site.site_id)} · {site.available ? `${site.source_resolution_m[0]} m/px · South polar stereographic` : 'Terrain dataset unavailable'}</span>}
      <span>Illustrative sky &amp; lighting</span>
      <span>Drag to orbit · Scroll to zoom</span>
    </footer>
    <CommandPalette commands={commands} open={palette} onOpen={setPalette} onSearch={search} />
  </div>
}
