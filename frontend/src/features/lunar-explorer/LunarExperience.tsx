import { Aperture, ArrowDownRight, ArrowUpRight, Compass, Globe2, Layers3, MapPin, Maximize, Minimize, Mountain, RotateCcw, Ruler, Search } from 'lucide-react'
import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { loadContext, loadMoon, loadPolar, loadProfile, type Context, type Coordinates, type PolarGrid, type Profile } from '../../services/lunar'
import type { Destination } from '../../visualization/MoonScene'
import { getGrid, type TerrainGrid } from '../../services/terrain'
import Explorer from './Explorer'
import { ProfilePlot } from './ProfilePlot'
import './lunar-experience.css'

const MoonScene = lazy(() => import('../../visualization/MoonScene'))
const initial: Destination = { point: { latitude: -15, longitude: 5 }, distance: 3650 }
const south: Destination = { point: { latitude: -89, longitude: 160 }, distance: 420 }
// IAU Gazetteer of Planetary Nomenclature, feature 5450.
const crater: Destination = { point: { latitude: -89.67, longitude: 129.78 }, distance: 80 }
const formatLocation = ({ latitude, longitude }: Coordinates) =>
  `${Math.abs(latitude).toFixed(2)}° ${latitude < 0 ? 'S' : 'N'} · ${Math.abs(longitude).toFixed(2)}° ${longitude < 0 ? 'W' : 'E'}`

class GlobeBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed ? <p className="viewport-message" role="alert">The globe requires a browser with WebGL 2.</p> : this.props.children
  }
}

export default function LunarExperience() {
  const [context, setContext] = useState<Context>()
  const [heights, setHeights] = useState<Float32Array>()
  const [overview, setOverview] = useState<PolarGrid>()
  const [approach, setApproach] = useState<PolarGrid>()
  const [siteGrid, setSiteGrid] = useState<TerrainGrid>()
  const [siteError, setSiteError] = useState('')
  const [error, setError] = useState('')
  const [regionalError, setRegionalError] = useState('')
  const [retry, setRetry] = useState(0)
  const [destination, setDestination] = useState(initial)
  const [viewPoint, setViewPoint] = useState(initial.point)
  const [range, setRange] = useState(3650)
  const [regional, setRegional] = useState(false)
  const [nearPole, setNearPole] = useState(false)
  const [local, setLocal] = useState(false)
  const [imagery, setImagery] = useState(true)
  const [relief, setRelief] = useState(true)
  const [regionalRelief, setRegionalRelief] = useState(true)
  const [graticule, setGraticule] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [query, setQuery] = useState('')
  const [searchError, setSearchError] = useState('')
  const [measuring, setMeasuring] = useState(false)
  const [measurement, setMeasurement] = useState<Coordinates[]>([])
  const [profile, setProfile] = useState<Profile>()
  const [profileError, setProfileError] = useState('')
  const openSitePending = useRef(false)
  const [sitePending, setSitePending] = useState(false)
  const regionalSource = (regional || nearPole) && regionalRelief && overview
  const closeRegion = range < 120 && Boolean(approach)

  useEffect(() => {
    const abort = new AbortController()
    loadContext(abort.signal).then(async value => {
      const elevation = await loadMoon(value, abort.signal)
      setContext(value)
      setHeights(elevation)
    }).catch(err => { if (!abort.signal.aborted) setError(err.message) })
    return () => abort.abort()
  }, [retry])

  useEffect(() => {
    if ((!regional && !nearPole) || overview && approach) return
    const abort = new AbortController()
    const detail = overview ? 'approach' : 'overview'
    loadPolar(detail, abort.signal).then(detail === 'overview' ? setOverview : setApproach)
      .catch(err => { if (!abort.signal.aborted) setRegionalError(err.message) })
    return () => abort.abort()
  }, [regional, nearPole, overview, approach, retry])

  useEffect(() => {
    if (!sitePending || siteGrid) return
    const abort = new AbortController()
    getGrid(256, abort.signal).then(setSiteGrid).catch(err => {
      if (!abort.signal.aborted) {
        setSiteError(err.message)
        setSitePending(false)
        openSitePending.current = false
      }
    })
    return () => abort.abort()
  }, [sitePending, siteGrid])

  useEffect(() => {
    if (!sitePending || !context?.site04 || !siteGrid || !approach && !regionalError) return
    setDestination({ point: context.site04, distance: 25, enterSite: true })
    setSitePending(false)
  }, [sitePending, context, approach, regionalError, siteGrid])

  useEffect(() => {
    if (measurement.length !== 2) return
    const abort = new AbortController()
    loadProfile(measurement[0], measurement[1], regionalSource ? 'polar' : 'moon', abort.signal)
      .then(setProfile).catch(err => { if (!abort.signal.aborted) setProfileError(err.message) })
    return () => abort.abort()
  }, [measurement, regionalSource])

  useEffect(() => {
    if (!fullscreen) return
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setFullscreen(false) }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [fullscreen])

  function navigate(next: Destination, polar: boolean) {
    openSitePending.current = false
    setSitePending(false)
    setRegional(polar)
    setDestination({ ...next })
    setMeasurement([])
    setProfile(undefined)
    setProfileError('')
  }
  function flyToSite() {
    if (!context?.site04) return
    navigate({ point: context.site04, distance: 95 }, true)
  }
  function enterSite() {
    if (!context?.site04) return
    setSiteError('')
    openSitePending.current = true
    setRegional(true)
    setSitePending(true)
  }
  const onArrival = useCallback(() => {
    if (!openSitePending.current) return
    openSitePending.current = false
    setLocal(true)
  }, [])
  const addPoint = useCallback((point: Coordinates) => {
    setProfile(undefined)
    setProfileError('')
    setMeasurement(previous => previous.length === 2 ? [point] : [...previous, point])
  }, [])
  const onRange = useCallback((altitude: number) => setRange(altitude), [])
  const onView = useCallback((point: Coordinates, altitude: number) => {
    setViewPoint(point)
    setNearPole(point.latitude < -82 && altitude < 850)
  }, [])

  function search(event: React.FormEvent) {
    event.preventDefault()
    setSearchError('')
    const term = query.trim().toLowerCase()
    if (/^(site\s*04|shackleton( rim)?)$/.test(term) && context?.site04) {
      flyToSite()
      return
    }
    if (/^(lunar )?south pole$/.test(term)) {
      navigate(south, true)
      return
    }
    if (term === 'shackleton crater') {
      navigate(crater, true)
      return
    }
    const pair = term.match(/^([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)$/)
    if (pair) {
      const [latitude, longitude] = pair.slice(1).map(Number)
      if (Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180) {
        navigate({ point: { latitude, longitude }, distance: latitude <= -85 ? 210 : 1100 }, latitude <= -85)
        return
      }
    }
    setSearchError('Enter South Pole, Shackleton Rim, Shackleton Crater, or latitude, longitude in degrees.')
  }

  if (local) return <Explorer initialGrid={siteGrid} onExit={() => {
    setLocal(false)
    if (context?.site04) setDestination({ point: context.site04, distance: 95 })
  }} />

  return <div className="app-shell lunar-shell">
    <a href="#moon-viewport" className="skip">Skip to lunar viewport</a>
    <header className="topbar">
      <div className="identity"><span className="brand-icon"><Aperture size={22} strokeWidth={1.6} /></span><strong>LUNA-SCOPE</strong></div>
      <div className="top-divider" /><h1>Lunar Explorer</h1>
      <div className="top-actions"><span className="site-chip">{regional ? 'South pole' : 'Global view'}</span>
        <span className={`data-status ${error ? 'bad' : ''}`} role="status"><i />{error ? 'Data unavailable' : heights ? 'LOLA loaded' : 'Loading lunar data'}</span>
        <button className="icon-button" title="Expand viewport" aria-label="Expand viewport" onClick={() => setFullscreen(value => !value)}><Maximize size={17} /></button>
      </div>
    </header>
    <main className="workspace lunar-workspace">
      <aside className="side controls" aria-label="Lunar navigation">
        <div className="panel-heading">Navigation</div>
        <div className="panel-body">
          <form className="location-search" onSubmit={search}>
            <label className="eyebrow" htmlFor="lunar-search">Find a location</label>
            <div><input id="lunar-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Name or lat, lon" />
              <button className="icon-button" aria-label="Search locations"><Search size={15} /></button></div>
            {searchError && <p className="error" role="status">{searchError}</p>}
          </form>
          <div className="control-group">
            <div className="eyebrow"><Compass size={14} /> Destinations</div>
            <div className="mode-list lunar-destinations">
              <button className="mode" aria-pressed={!regional} onClick={() => navigate(initial, false)}><Globe2 size={16} /> Full Moon</button>
              <button className="mode" aria-pressed={regional} onClick={() => navigate(south, true)}><Compass size={16} /> Lunar south pole</button>
              <button className="mode" disabled={!context?.site04} onClick={flyToSite}><MapPin size={16} /> Shackleton Rim</button>
              <button className="mode" onClick={() => navigate(crater, true)}><Mountain size={16} /> Shackleton Crater</button>
            </div>
          </div>
          <div className="control-group lunar-layers">
            <div className="eyebrow"><Layers3 size={14} /> Surface layers</div>
            <label><input type="checkbox" checked={imagery} disabled={!context?.imagery} onChange={event => setImagery(event.target.checked)} /> LROC appearance</label>
            <label><input type="checkbox" checked={relief} onChange={event => setRelief(event.target.checked)} /> Global LOLA relief</label>
            <label><input type="checkbox" checked={regionalRelief} onChange={event => setRegionalRelief(event.target.checked)} /> Polar detail</label>
            <label><input type="checkbox" checked={graticule} onChange={event => setGraticule(event.target.checked)} /> Latitude / longitude grid</label>
          </div>
          <div className="control-group">
            <button className="layer" aria-pressed={measuring} onClick={() => {
              setMeasuring(value => !value); setMeasurement([]); setProfile(undefined); setProfileError('')
            }}><Ruler size={15} /> Measure a path</button>
            {measuring && <p className="muted">{measurement.length === 1 ? 'Select the end point.' : measurement.length === 2 ? 'Select a point to start a new path.' : 'Select the start point on the Moon.'}</p>}
          </div>
        </div>
      </aside>
      <div id="moon-viewport" className={`viewport moon-viewport ${fullscreen ? 'viewport-expanded' : ''}`} tabIndex={-1}>
        <div className="viewport-heading"><div>
          <div className="eyebrow"><Globe2 size={15} /> Lunar reference sphere</div>
          <h2>{regional ? 'Lunar south pole' : 'The Moon'}</h2>
        </div></div>
        <div className="viewport-actions">
          <button className="icon-button" aria-label="Reset globe camera" title="Reset globe camera" onClick={() => navigate(initial, false)}><RotateCcw size={17} /></button>
          <button className="icon-button" aria-label={fullscreen ? 'Exit expanded viewport' : 'Expand lunar viewport'} onClick={() => setFullscreen(value => !value)}>{fullscreen ? <Minimize size={17} /> : <Maximize size={17} />}</button>
        </div>
        {context && heights ? <GlobeBoundary><Suspense fallback={<p className="viewport-message">Preparing the lunar globe…</p>}>
          <MoonScene context={context} heights={heights} overview={overview}
            approach={approach} siteGrid={destination.enterSite ? siteGrid : undefined} destination={destination}
            imagery={imagery} relief={relief} graticule={graticule} regionalRelief={regionalRelief}
            measuring={measuring} measurement={measurement} onPoint={addPoint} onRange={onRange} onView={onView} onArrival={onArrival} onSite={flyToSite} />
        </Suspense></GlobeBoundary> : <div className="viewport-message" role="status">{error ? <>
          <p>{error}</p><button onClick={() => { setError(''); setRetry(value => value + 1) }}>Retry lunar data</button>
        </> : 'Loading global LOLA elevation…'}</div>}
        {heights && <div className="lunar-viewport-footer">
          <span title="Sub-camera coordinates"><Compass size={14} /> {formatLocation(viewPoint)}</span>
          <span>Drag to rotate · Scroll to zoom</span>
        </div>}
      </div>
      <aside className="side inspector lunar-inspector" aria-label="Lunar location and measurements">
        <div className="panel-heading">Location</div>
        <div className="panel-body lunar-site">
          <span className="lunar-site-icon"><Mountain size={22} /></span>
          <div className="eyebrow">Site04</div>
          <h2>Shackleton Rim</h2>
          {context?.site04 ? <p className="lunar-location">{formatLocation(context.site04)}</p> : <p className="muted">{context ? 'Site04 terrain unavailable.' : 'Loading site coordinates…'}</p>}
          <button className="lunar-primary" disabled={!context?.site04} onClick={flyToSite}>Fly to Shackleton <ArrowDownRight size={16} /></button>
          <button className="lunar-secondary" disabled={!context?.site04 || sitePending} onClick={enterSite}>
            {sitePending ? 'Loading polar approach…' : 'Inspect Site04'} <ArrowUpRight size={15} />
          </button>
          {siteError && <p className="error" role="alert">{siteError}</p>}
          {regional && <p className={regionalError ? 'error' : 'muted'} role="status">
            {regionalError || (regionalSource ? `Polar LOLA · ${closeRegion ? approach!.resolution[0] : overview!.resolution[0]} m display spacing` : regionalRelief ? 'Loading polar relief…' : 'Polar detail is off.')}
          </p>}
        </div>
        {measuring && <div className="panel-body lunar-measurement">
          <h2>Elevation profile</h2>
          {profile ? <ProfilePlot profile={profile} /> :
            <p className={profileError ? 'error' : 'muted'} role="status">{profileError || (measurement.length === 2 ? 'Sampling the path…' : 'Select two points on the surface.')}</p>}
        </div>}
      </aside>
    </main>
    <footer className="lunar-metadata">
      <div><span>Global relief</span><a href={context?.global_source_url ?? 'https://svs.gsfc.nasa.gov/4720/'}>NASA SVS · LOLA</a></div>
      <div><span>Appearance</span><strong>LROC WAC + polar LOLA reflectance</strong></div>
      <div><span>Coordinates</span><strong>Planetocentric · east-positive</strong></div>
      <div><span>Reference radius</span><strong>{context ? `${(context.radius_m / 1000).toLocaleString()} km` : '—'}</strong></div>
      <div><span>Lighting</span><strong>Illustrative Sun direction</strong></div>
    </footer>
  </div>
}
