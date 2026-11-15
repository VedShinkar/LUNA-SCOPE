import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import type { ScienceSelection } from './WorkspaceNavigation'
import { ChevronLeft, ChevronRight, Crosshair } from 'lucide-react'
import { LiquidGlassButton } from '../../components/ui/liquid-glass'
import { getSolarObserver, getSolarRegion, type ObserverAnalysis, type RegionAnalysis, type RegionFrame, type SolarQuery } from '../../services/illumination'
import type { LunarSite } from '../../services/lunar'
import { getGrid, type MapPoint, type TerrainGrid } from '../../services/terrain'
import TerrainScene from '../../visualization/TerrainScene'
import { inputUtc, stepUtc } from '../../visualization/celestial-display'
import { displayState, solarColors, solarTexture } from '../../visualization/solar-display'

const labels = { illuminated:'Confirmed sun centre', shadowed:'Shadowed centre', unknown:'Unresolved', invalid:'NoData', clear:'Clear within raster' }
const reasons: Record<string,string> = {
  below_horizontal:'Below the radial horizontal in the native cell model.',
  native_terrain_obstruction:'Native terrain intersects the centre ray.',
  grazing:'The centre ray lies within the grazing tolerance.',
  nodata_along_ray:'The ray crosses missing terrain without a known obstruction.',
  terrain_extent:'The ray leaves mapped terrain before clearance can be established.',
  clears_model_ceiling:'The centre ray clears native terrain and reaches the adopted lunar elevation ceiling.',
  zenith_ray:'The centre ray points radially up.',
}
const now = () => new Date().toISOString().slice(0, 19)
const utc = (time: string) => time.replace('T',' ').replace(/(?:\.0+)?Z$/, ' UTC')
const angle = (value?: number | null) => value == null ? '—' : `${value.toFixed(3)}°`
const hours = (seconds: number) => `${(seconds/3600).toLocaleString(undefined,{maximumFractionDigits:3})} h`
const noop = () => {}
type Outcome<T> = {key: string; data?: T; error?: string}

function RegionMap({ analysis, frame }: { analysis: RegionAnalysis; frame: RegionFrame }) {
  const {width,height} = analysis.region
  return <svg viewBox={`0 0 ${width} ${height}`} className="solar-cell-map" role="img" aria-label="Native LOLA cell classification map, northing increases upwards">
    <g aria-hidden="true">{frame.states.map((state, index) => {
      const kind = displayState(state, frame.native_states[index])
      return <rect key={index} x={index%width} y={Math.floor(index/width)} width={1} height={1} fill={solarColors[kind]}>
        <title>{labels[kind]}</title>
      </rect>
    })}</g>
  </svg>
}

function TemporalMetrics({ analysis }: { analysis: ObserverAnalysis }) {
  const {summary, native_summary:native} = analysis
  const scopes = [['Confirmed', summary], ['Native footprint', native]] as const
  return <section className="solar-temporal" aria-label="Observer illumination intervals">
    <h2>Observer intervals</h2>
    <p className="muted">Sampled estimates. Adjacent samples must agree to assign time. Changed or unresolved samples leave an unresolved bracket.</p>
    <dl className="solar-metrics">
      <div><dt>Confirmed centre illumination</dt><dd>{hours(summary.duration_s.illuminated)}</dd></div>
      <div><dt>Longest confirmed illumination</dt><dd>{hours(summary.longest_clear_s)}</dd></div>
      <div><dt>Shadow duration</dt><dd>{hours(summary.duration_s.shadowed)}</dd></div>
      <div><dt>Longest shadow</dt><dd>{hours(summary.longest_shadow_s)}</dd></div>
      <div><dt>Unresolved time</dt><dd>{hours(summary.duration_s.unknown)}</dd></div>
      <div><dt>Lit share of classifiable time</dt><dd>{summary.fraction_known_time_clear == null ? '—' : `${(100*summary.fraction_known_time_clear).toFixed(1)}%`}</dd></div>
      <div><dt>Confirmed transitions / gaps</dt><dd>{summary.transitions.length} / {summary.gap_count}</dd></div>
      <div><dt>Native-clear time / longest</dt><dd>{hours(native.duration_s.clear)} / {hours(native.longest_clear_s)}</dd></div>
    </dl>
    <details><summary>Intervals and transition brackets</summary>
      <div className="mission-table"><table><thead><tr><th>Scope</th><th>State</th><th>Start</th><th>End</th><th>Duration</th></tr></thead><tbody>
        {scopes.flatMap(([scope,value]) =>
          value.intervals.map(interval => <tr key={`${scope}:${interval.start_utc}`}><td>{scope}</td><td>{labels[interval.state as keyof typeof labels]}</td><td>{utc(interval.start_utc)}</td><td>{utc(interval.end_utc)}</td><td>{hours(interval.duration_s)}</td></tr>))}
      </tbody></table></div>
      {scopes.map(([scope,result]) =>
        <div key={scope}><h3>{scope} transitions and gaps</h3>
          {result.transitions.length === 0 && <p className="muted">No transitions bracketed by classified samples.</p>}
          {result.transitions.map(change => <p key={change.start_utc}>{labels[change.from as keyof typeof labels]} → {labels[change.to as keyof typeof labels]} · {utc(change.start_utc)} to {utc(change.end_utc)}</p>)}
          {result.gaps.map(gap => <p key={gap.first_shadow_utc}>Gap · {utc(gap.first_shadow_utc)} to {utc(gap.last_shadow_utc)} · {hours(gap.duration_s)} between shadow samples, {hours(gap.bracket_s)} enclosing bracket</p>)}
        </div>
      )}
    </details>
  </section>
}

export default function SolarObservatory({ sites, initialSite, initialPoint, onSelection, onEpoch }: {sites:LunarSite[]} & ScienceSelection) {
  const [site, setSite] = useState(initialSite)
  const [point, setPoint] = useState<MapPoint | null>(initialPoint ?? null)
  const [start, setStart] = useState(now)
  const [end, setEnd] = useState(() => stepUtc(inputUtc(start), 86400))
  const [step, setStep] = useState(3600)
  const [series, setSeries] = useState(false)
  const [side, setSide] = useState(12)
  const [query, setQuery] = useState<SolarQuery>(() => ({utc:inputUtc(start)}))
  const [cursor, setCursor] = useState(0)
  const [retry, setRetry] = useState(0)
  const [observerLoad, setObserverLoad] = useState<Outcome<ObserverAnalysis>>()
  const [mapLoad, setMapLoad] = useState<Outcome<RegionAnalysis>>()
  const [gridLoad, setGridLoad] = useState<Outcome<TerrainGrid>>()
  const [comparison, setComparison] = useState<{key:string; rows:Outcome<RegionAnalysis>[]; pending:boolean}>()
  const comparisonRequest = useRef<AbortController | null>(null)
  const siteInfo = sites.find(item => item.site_id === site)
  const easting = point?.easting ?? (siteInfo?.available ? siteInfo.easting : null)
  const northing = point?.northing ?? (siteInfo?.available ? siteInfo.northing : null)
  const gridKey = JSON.stringify([site,easting,northing,retry])
  const observerKey = JSON.stringify([site,point,query,retry])
  const current = observerLoad?.key === observerKey ? observerLoad : undefined
  const result = current?.data
  const sample = result?.samples[cursor]
  const epoch = sample?.utc
  useEffect(()=>{if(epoch) onEpoch?.(epoch)},[epoch,onEpoch])
  const mapKey = JSON.stringify([site,point,epoch,side,retry])
  const map = mapLoad?.key === mapKey ? mapLoad : undefined
  const compareKey = JSON.stringify([epoch,side])
  const compare = comparison?.key === compareKey ? comparison : undefined
  const frame = map?.data?.frames[0]
  const grid = gridLoad?.key === gridKey ? gridLoad.data : undefined
  const texture = useMemo(() => grid && map?.data && frame ? solarTexture(grid,map.data,frame) : undefined, [grid,map,frame])

  useEffect(() => {
    const abort = new AbortController()
    if (easting !== null && northing !== null) getGrid(site,48,abort.signal,{easting,northing}).then(data => {
      if (!abort.signal.aborted) setGridLoad({key:gridKey,data})
    }).catch(error => { if (!abort.signal.aborted) setGridLoad({key:gridKey,error:error.message}) })
    return () => abort.abort()
  }, [site, easting, northing, gridKey])
  useEffect(() => {
    const abort = new AbortController()
    getSolarObserver(site,point,query,abort.signal).then(data => {
      if (!abort.signal.aborted) setObserverLoad({key:observerKey,data})
    }).catch(error => { if (!abort.signal.aborted) setObserverLoad({key:observerKey,error:error.message}) })
    return () => abort.abort()
  }, [site,point,query,observerKey])
  useEffect(() => {
    if (!epoch) return
    const abort = new AbortController()
    getSolarRegion(site,point,[epoch],side,abort.signal).then(data => {
      if (!abort.signal.aborted) setMapLoad({key:mapKey,data})
    }).catch(error => { if (!abort.signal.aborted) setMapLoad({key:mapKey,error:error.message}) })
    return () => abort.abort()
  }, [site,point,epoch,side,mapKey])
  useEffect(() => () => comparisonRequest.current?.abort(), [compareKey])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const first = String(form.get('start'))
    const last = String(form.get('end') ?? '')
    setStart(first)
    if (series) setEnd(last)
    setCursor(0)
    setRetry(value => value + 1)
    setQuery(series ? {start_utc:inputUtc(first),end_utc:inputUtc(last),step_seconds:step} : {utc:inputUtc(first)})
  }
  function move(direction: number) {
    if ('start_utc' in query) {
      setCursor(index => Math.min((result?.samples.length ?? 1)-1,Math.max(0,index+direction)))
      return
    }
    const next = stepUtc(query.utc,step*direction)
    setStart(next)
    setQuery({utc:inputUtc(next)})
  }
  async function compareSites() {
    if (!epoch) return
    comparisonRequest.current?.abort()
    const abort = new AbortController()
    comparisonRequest.current = abort
    setComparison({key:compareKey,rows:[],pending:true})
    const rows: Outcome<RegionAnalysis>[] = []
    for (const item of sites) {
      try {
        const data = await getSolarRegion(item.site_id,null,[epoch],side,abort.signal)
        rows.push({key:item.site_id,data})
      } catch (error) {
        if (abort.signal.aborted) return
        rows.push({key:item.site_id,error:(error as Error).message})
      }
      if (abort.signal.aborted) return
      setComparison({key:compareKey,rows:[...rows],pending:rows.length < sites.length})
    }
  }

  return <section className="celestial-observatory solar-observatory" aria-label="Solar Illumination Observatory">
    <form className="mission-inputs celestial-inputs" onSubmit={submit}>
      <label>Landing site<select value={site} onChange={event=>{setSite(event.target.value);setPoint(null);setCursor(0);onSelection(event.target.value,null)}}>
        {sites.map(item => <option key={item.site_id} value={item.site_id}>{item.name} · {item.site_id}</option>)}
      </select></label>
      <label>{series ? 'Start (UTC)' : 'Observation time (UTC)'}<input name="start" type="datetime-local" min="0001-01-01T00:00" max="9999-12-31T23:59" step={1} value={start} onChange={event=>setStart(event.target.value)} required /></label>
      {series && <label>End (UTC)<input name="end" type="datetime-local" min="0001-01-01T00:00" max="9999-12-31T23:59" step={1} value={end} onChange={event=>setEnd(event.target.value)} required /></label>}
      <label>Time increment<select value={step} onChange={event=>setStep(Number(event.target.value))}>
        <option value={60}>1 min</option><option value={600}>10 min</option><option value={3600}>1 hour</option><option value={21600}>6 hours</option><option value={86400}>1 day</option>
      </select></label>
      <label className="celestial-series"><input type="checkbox" checked={series} onChange={event=>setSeries(event.target.checked)}/> Time series</label>
      <button type="submit" className="obs-button obs-primary">Calculate illumination</button>
      <LiquidGlassButton label="Use current UTC" onClick={()=>{const time=now();setStart(time);setSeries(false);setCursor(0);setQuery({utc:inputUtc(time)})}}/>
    </form>
    <div className="celestial-layout">
      <section aria-label="Solar terrain view">
        <div className="celestial-view-bar"><h2>{siteInfo?.name ?? site}</h2><span>{site} · Native LOLA</span></div>
        <div className="celestial-terrain-viewport">
          {grid ? <TerrainScene grid={grid} layer="elevation" exaggeration={1} contours={false} threshold={15} reset={0}
            selected={result ? {easting:result.observer.easting_m,northing:result.observer.northing_m,elevation:result.observer.elevation_m} : null}
            celestial={sample && result ? {longitude:result.observer.longitude_deg_east,directions:[{vector:sample.sun_enu_unit_vector,above:sample.centre_above_horizontal,color:solarColors.illuminated}]} : undefined}
            surfaceColors={texture} onHeading={noop} onHover={noop}
            onSelect={hit=>{const next={easting:hit.easting,northing:hit.northing};setPoint(next);setCursor(0);onSelection(site,next)}}/> :
            <p role="status">{gridLoad?.key === gridKey && gridLoad.error ? gridLoad.error : 'Loading native terrain…'}</p>}
        </div>
        <div className="celestial-view-bar celestial-terrain-actions">
          <p>{result ? `${result.observer.latitude_deg.toFixed(5)}°, ${result.observer.longitude_deg_east.toFixed(5)}° east · ${result.observer.elevation_m.toFixed(2)} m` : 'Observer coordinates pending'}</p>
          <LiquidGlassButton icon={<Crosshair />} label="Recenter on site" disabled={!point} onClick={()=>{setPoint(null);setCursor(0);onSelection(site,null)}}/>
        </div>
        <p className="muted">Select terrain to place the observer at the nearest containing pixel centre. The arrow points to the Sun centre.</p>
      </section>
      <section className="solar-analysis" aria-label="Solar obstruction and native-cell map">
        <div className="celestial-view-bar"><h2>Direct solar centre</h2><span>JPL DE440s</span></div>
        {current?.error ? <p role="alert" className="celestial-error">{current.error}</p> : sample ?
          <><p className="solar-state" aria-live="polite"><strong data-state={sample.state} style={{color:solarColors[displayState(sample.state,sample.native_state)]}}>{labels[displayState(sample.state,sample.native_state)]}</strong><span>{reasons[sample.reason]}</span></p>
            <dl className="solar-metrics">
              <div><dt>Sun elevation</dt><dd>{angle(sample.solar_elevation_deg)}</dd></div>
              <div><dt>Sun azimuth</dt><dd>{angle(sample.solar_azimuth_deg)}</dd></div>
              <div><dt>Terrain horizon</dt><dd>{angle(sample.native_horizon_deg)}</dd></div>
              <div><dt>Sun angular radius</dt><dd>{angle(sample.solar_angular_radius_deg)}</dd></div>
            </dl>
            <p className="muted">{sample.rms_horizon_deg ? `LOLA RMS scenario · ${angle(sample.rms_horizon_deg[0])} to ${angle(sample.rms_horizon_deg[1])}${sample.rms_sensitive ? ' · outcome sensitive to height uncertainty' : ''}` : 'No terrain RMS horizon scenario for this ray.'}</p>
            <p className="celestial-epoch">{utc(sample.utc)}</p></> : <p role="status">Tracing the solar centre ray…</p>}
        <div className="celestial-time-controls">
          <LiquidGlassButton icon={<ChevronLeft />} label="Previous time" onClick={()=>move(-1)} disabled={'start_utc' in query && cursor===0}/>
          {result && result.samples.length > 1 && <label>Sample {cursor+1} of {result.samples.length}<input type="range" aria-label="Illumination epoch" min={0} max={result.samples.length-1} value={cursor} onChange={event=>setCursor(Number(event.target.value))}/></label>}
          <LiquidGlassButton icon={<ChevronRight />} label="Next time" onClick={()=>move(1)} disabled={'start_utc' in query && cursor>=(result?.samples.length??1)-1}/>
        </div>
        <div className="solar-map-block">
          <div className="celestial-view-bar"><h3>Native cell map</h3><label>Window <select aria-label="Map window" value={side} onChange={event=>setSide(Number(event.target.value))}>
            <option value={8}>8 × 8</option><option value={12}>12 × 12</option><option value={16}>16 × 16</option>
          </select></label></div>
          {frame && map?.data ? <div className="solar-map-layout"><RegionMap analysis={map.data} frame={frame}/>
            <dl className="solar-metrics">
              <div><dt>Confirmed lit / valid</dt><dd>{frame.lit_percent_of_valid_cells?.toFixed(1) ?? '—'}{frame.lit_percent_of_valid_cells == null ? '' : '%'}</dd></div>
              <div><dt>Shadowed / valid</dt><dd>{frame.counts.valid_cells ? `${(100 * frame.counts.shadowed / frame.counts.valid_cells).toFixed(1)}%` : '—'}</dd></div>
              <div><dt>Confirmed lit / shadowed cells</dt><dd>{frame.counts.illuminated} / {frame.counts.shadowed}</dd></div>
              <div><dt>Unresolved / NoData</dt><dd>{frame.counts.unknown} / {frame.counts.invalid}</dd></div>
              <div><dt>Clear within raster</dt><dd>{frame.native_clear}</dd></div>
            </dl></div> : map?.error ? <p role="alert">{map.error}</p> : epoch ? <p role="status">Tracing native cells…</p> : null}
          <ul className="solar-legend">{Object.entries(solarColors).map(([state,color])=><li key={state}><i style={{background:color}}/>{labels[state as keyof typeof labels]}</li>)}</ul>
        </div>
      </section>
    </div>
    {result && result.samples.length > 1 && <TemporalMetrics analysis={result}/>}
    <section className="solar-temporal" aria-label="Matched-epoch regional comparison">
      <div className="celestial-view-bar"><h2>Matched-epoch comparison</h2><LiquidGlassButton label="Compare three sites" onClick={compareSites} disabled={!epoch || compare?.pending}/></div>
      <p className="muted">Separate {side} × {side} native windows at the three raster centres. The obstruction search uses each site’s own terrain footprint.</p>
      {compare?.pending && <p role="status">Tracing site {compare.rows.length+1} of {sites.length}…</p>}
      {compare && compare.rows.length > 0 && <div className="mission-table"><table><thead><tr><th>Site</th><th>Native spacing</th><th>Ray footprint</th><th>Lit / valid</th><th>Shadowed</th><th>Unresolved</th><th>Clear within raster</th><th>NoData</th></tr></thead><tbody>
        {compare.rows.map(row=>{
          const data = row.data
          const stats = data?.frames[0]
          return <tr key={row.key}><th scope="row">{sites.find(item=>item.site_id===row.key)?.name ?? row.key}</th>{data && stats ?
            <><td>{data.terrain.resolution_m.join(' × ')} m</td>
              <td title={`West, south, east, north (m) · ${data.terrain.bounds_m.join(', ')}`}>{(data.terrain.bounds_m[2]-data.terrain.bounds_m[0])/1000} × {(data.terrain.bounds_m[3]-data.terrain.bounds_m[1])/1000} km</td>
              <td>{stats.counts.illuminated} / {stats.counts.valid_cells}</td><td>{stats.counts.shadowed}</td><td>{stats.counts.unknown}</td><td>{stats.native_clear}</td><td>{stats.counts.invalid}</td></> :
            <td colSpan={7}>{row.error}</td>}</tr>
        })}
      </tbody></table></div>}
    </section>
    <details className="celestial-provenance"><summary>Method and terrain provenance</summary>
      <p>Apparent Sun direction from Phase 3.1. The solver traces the solar centre through native spherical LOLA cells. It reports the angular radius separately. Disc visibility, eclipses, and power output are outside this model.</p>
      <p>Terrain outside the raster remains unresolved unless the ray has already cleared the adopted lunar elevation ceiling. The RMS scenarios describe sensitivity to height changes.</p>
      {result && <p><a href={result.terrain.source_url}>{result.terrain.file}</a> · {result.terrain.resolution_m.join(' × ')} m/px · Bounds {result.terrain.bounds_m.join(', ')} m{result.terrain.rms_source_url && <> · <a href={result.terrain.rms_source_url}>LOLA elevation RMS</a></>}</p>}
    </details>
  </section>
}
