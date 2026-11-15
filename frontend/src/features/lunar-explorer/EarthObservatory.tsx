import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import type { ScienceSelection } from './WorkspaceNavigation'
import { ChevronLeft, ChevronRight, Crosshair } from 'lucide-react'
import { LiquidGlassButton } from '../../components/ui/liquid-glass'
import { getEarthPoint, getEarthRegion, type Criterion, type EarthPoint, type EarthRegion, type EarthSample, type EpochQuery } from '../../services/communication'
import type { LunarSite } from '../../services/lunar'
import { getGrid, type MapPoint, type TerrainGrid } from '../../services/terrain'
import TerrainScene from '../../visualization/TerrainScene'
import { inputUtc, stepUtc } from '../../visualization/celestial-display'
import { discPlot, earthLabels, earthPalette, mapClass, type MapMode } from '../../visualization/earth-display'
import { nativeWindowColors } from '../../visualization/solar-display'

const now = () => new Date().toISOString().slice(0,19)
const utc = (value: string) => value.replace('T',' ').replace(/(?:\.0+)?Z$/, ' UTC')
const angle = (value?: number | null) => value == null ? '—' : `${value.toFixed(3)}°`
const hours = (seconds: number) => `${(seconds/3600).toLocaleString(undefined,{maximumFractionDigits:3})} h`
const percent = (value?: number | null) => value == null ? '—' : `${value.toFixed(1)}%`
const noop = () => {}
const criteria: Record<Criterion,string> = {
  centre:'Earth centre', any_disc:'Any visible disc', full_disc:'Entire disc', centre_with_mask:'Earth centre and elevation mask',
}
const reasons: Record<string,string> = {
  terrain_extent:'The ray clears native terrain before leaving the mapped footprint.',
  native_terrain_obstruction:'A native terrain cell blocks the centre ray.',
  below_horizontal:'Earth’s centre is below the observer’s radial horizontal.',
  grazing:'The centre ray falls within the grazing tolerance.',
  nodata_along_ray:'The centre ray crosses missing terrain.',
  clears_model_ceiling:'The centre ray clears native terrain and reaches the adopted radial ceiling.',
  zenith_ray:'The centre ray points radially up.',
}
const mapKeys = {
  centre:['visible','obstructed','unresolved','invalid'],
  disc:['fully_visible','partially_visible','fully_obscured','unresolved','invalid'],
  mask:['eligible','ineligible','invalid'],
} as const
type Outcome<T> = {key:string; data?:T; error?:string}

function DiscPlot({ sample }: {sample:EarthSample}) {
  const plot = discPlot(sample)
  return <svg viewBox="0 0 440 194" role="img" className="earth-disc-plot" aria-label="Earth centre and apparent limbs compared with radial horizontal and native horizon at the centre bearing">
    <rect x="2" y="2" width="436" height="190" rx="6" fill="#0b1524"/>
    <path d={`M12 ${plot.horizontal}H428`} stroke="#48647b" strokeDasharray="4 4"/>
    <text x="18" y={Math.min(plot.horizontal+13,184)}>RADIAL HORIZONTAL</text>
    {plot.horizon !== null && <>
      <path d={`M12 ${plot.horizon}H428`} stroke="#d2ab76"/>
      <text x="18" y={Math.max(14,plot.horizon-5)} className="earth-horizon-label">NATIVE HORIZON · CENTRE BEARING</text>
    </>}
    <circle cx="267" cy={plot.centre} r={plot.radius} fill="#3b819937" stroke="#79d6e7"/>
    <path d={`M267 ${plot.upper}V${plot.lower}`} stroke="#6db1c8" strokeDasharray="2 3"/>
    <circle cx="267" cy={plot.upper} r="2" fill="#c6edf5"/>
    <circle cx="267" cy={plot.centre} r="2.4" fill="#79d6e7"/>
    <circle cx="267" cy={plot.lower} r="2" fill="#c6edf5"/>
    <text x="280" y={Math.max(14,plot.upper-7)}>UPPER LIMB</text>
    <text x="383" y={plot.centre+3}>CENTRE</text>
    <text x="280" y={Math.min(185,plot.lower+14)}>LOWER LIMB</text>
  </svg>
}

function Intervals({ data }: { data:EarthPoint }) {
  const summary = data.summary
  return <section className="solar-temporal" aria-label="Earth visibility intervals">
    <h2>{criteria[data.criterion]} intervals</h2>
    <p className="muted">{data.requested_sample_count} requested epochs · {data.refinement_sample_count} additional refinement samples. Changed or unresolved endpoints leave the bracket unresolved.</p>
    <dl className="solar-metrics">
      <div><dt>Confirmed visibility under criterion</dt><dd>{hours(summary.duration_s.visible)}</dd></div>
      <div><dt>{data.criterion === 'centre_with_mask' ? 'Obstructed or below mask' : 'Obstructed under criterion'}</dt><dd>{hours(summary.duration_s.obstructed)}</dd></div>
      <div><dt>Unresolved time</dt><dd>{hours(summary.duration_s.unresolved)}</dd></div>
      <div><dt>Longest visible / interruption</dt><dd>{hours(summary.longest_visible_s)} / {hours(summary.longest_interruption_s)}</dd></div>
      <div><dt>Observed transition brackets</dt><dd>{summary.transitions.length}</dd></div>
    </dl>
    <details><summary>Intervals and transition brackets</summary>
      <div className="mission-table"><table><thead><tr><th>State</th><th>Start</th><th>End</th><th>Duration</th></tr></thead><tbody>
        {summary.intervals.map(row=><tr key={row.start_utc}><td>{row.state === 'obstructed' && data.criterion==='centre_with_mask' ? 'Obstructed or below mask' : row.state}</td><td>{utc(row.start_utc)}</td><td>{utc(row.end_utc)}</td><td>{hours(row.duration_s)}</td></tr>)}
      </tbody></table></div>
      {summary.transitions.map(row=><p key={row.start_utc}>{row.from_state} → {row.to_state} · {utc(row.start_utc)} to {utc(row.end_utc)}</p>)}
    </details>
  </section>
}

export default function EarthObservatory({ sites, initialSite, initialPoint, onSelection, onEpoch }: {sites:LunarSite[]} & ScienceSelection) {
  const [site,setSite] = useState(initialSite)
  const [point,setPoint] = useState<MapPoint|null>(initialPoint ?? null)
  const [start,setStart] = useState(now)
  const [end,setEnd] = useState(()=>stepUtc(inputUtc(start),86400))
  const [series,setSeries] = useState(false)
  const [step,setStep] = useState(3600)
  const [maskDraft,setMaskDraft] = useState(0)
  const [criterionDraft,setCriterionDraft] = useState<Criterion>('centre')
  const [request,setRequest] = useState<{query:EpochQuery;mask:number;criterion:Criterion;revision:number}>(()=>({
    query:{utc:inputUtc(start)}, mask:0, criterion:'centre', revision:0,
  }))
  const {query,mask,criterion} = request
  const [cursor,setCursor] = useState(0)
  const [side,setSide] = useState(8)
  const [mode,setMode] = useState<MapMode>('disc')
  const [survey,setSurvey] = useState<Outcome<EarthPoint>>()
  const [regional,setRegional] = useState<Outcome<EarthRegion>>()
  const [terrain,setTerrain] = useState<Outcome<TerrainGrid>>()
  const [comparison,setComparison] = useState<{key:string; rows:Outcome<EarthRegion>[]; pending:boolean}>()
  const compareRequest = useRef<AbortController|null>(null)
  const active = sites.find(item=>item.site_id===site)
  const easting = point?.easting ?? (active?.available ? active.easting : null)
  const northing = point?.northing ?? (active?.available ? active.northing : null)
  const terrainKey = JSON.stringify([site,easting,northing])
  const observerKey = JSON.stringify([site,point,request])
  const earth = survey?.key === observerKey ? survey.data : undefined
  const sample = earth?.samples[cursor]
  const epoch = sample?.utc
  useEffect(()=>{if(epoch) onEpoch?.(epoch)},[epoch,onEpoch])
  const regionKey = JSON.stringify([site,point,epoch,side,mask,criterion,request.revision])
  const map = regional?.key === regionKey ? regional.data : undefined
  const grid = terrain?.key === terrainKey ? terrain.data : undefined
  const compareKey = JSON.stringify([epoch,side,mask,criterion])
  const matches = comparison?.key === compareKey ? comparison : undefined
  const values = useMemo(()=>map?.cells.map(cell=>earthPalette[mapClass(cell,mode)]),[map,mode])
  const texture = useMemo(()=>grid && map && values ? nativeWindowColors(grid,map.site_id,map.region,values) : undefined,[grid,map,values])
  const mapStatistics = map && (mode==='mask' ? [{name:earthLabels.eligible,key:'antenna_eligible'}]
    : mapKeys[mode].filter(key=>key!=='invalid').map(key=>({name:earthLabels[key], key:`${mode}_${key}`})))

  useEffect(()=>{
    const abort = new AbortController()
    if (easting !== null && northing !== null) getGrid(site,48,abort.signal,{easting,northing}).then(data=>{
      if (!abort.signal.aborted) setTerrain({key:terrainKey,data})
    }).catch(error=>{if (!abort.signal.aborted) setTerrain({key:terrainKey,error:error.message})})
    return ()=>abort.abort()
  },[site,easting,northing,terrainKey])
  useEffect(()=>{
    const abort = new AbortController()
    getEarthPoint(site,point,query,mask,criterion,abort.signal).then(data=>{
      if (!abort.signal.aborted) setSurvey({key:observerKey,data})
    }).catch(error=>{if (!abort.signal.aborted) setSurvey({key:observerKey,error:error.message})})
    return ()=>abort.abort()
  },[site,point,query,mask,criterion,observerKey])
  useEffect(()=>{
    if (!epoch) return
    const abort = new AbortController()
    getEarthRegion(site,point,epoch,side,mask,criterion,abort.signal).then(data=>{
      if (!abort.signal.aborted) setRegional({key:regionKey,data})
    }).catch(error=>{if (!abort.signal.aborted) setRegional({key:regionKey,error:error.message})})
    return ()=>abort.abort()
  },[site,point,epoch,side,mask,criterion,regionKey])
  useEffect(()=>()=>compareRequest.current?.abort(),[compareKey])

  function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const input = new FormData(event.currentTarget)
    const first = String(input.get('start'))
    const last = String(input.get('end') ?? '')
    setStart(first)
    if (series) setEnd(last)
    setCursor(0)
    setRequest(old=>({mask:maskDraft,criterion:criterionDraft,revision:old.revision+1,
      query:series ? {start_utc:inputUtc(first),end_utc:inputUtc(last),step_seconds:step} : {utc:inputUtc(first)}}))
  }
  function move(direction:number) {
    if ('start_utc' in query) {
      setCursor(index=>Math.min((earth?.samples.length??1)-1,Math.max(0,index+direction)))
    } else {
      const next = stepUtc(query.utc,direction*step)
      setStart(next)
      setRequest(old=>({...old,query:{utc:inputUtc(next)}}))
    }
  }
  async function compareSites() {
    if (!epoch) return
    compareRequest.current?.abort()
    const abort = new AbortController()
    compareRequest.current = abort
    setComparison({key:compareKey,rows:[],pending:true})
    const rows:Outcome<EarthRegion>[] = []
    for (const item of sites) {
      try {
        const data = await getEarthRegion(item.site_id,null,epoch,side,mask,criterion,abort.signal)
        rows.push({key:item.site_id,data})
      } catch(error) {
        if (abort.signal.aborted) return
        rows.push({key:item.site_id,error:(error as Error).message})
      }
      if (abort.signal.aborted) return
      setComparison({key:compareKey,rows:[...rows],pending:rows.length<sites.length})
    }
  }

  return <section className="celestial-observatory solar-observatory earth-observatory" aria-label="Earth Communication Observatory">
    <form className="mission-inputs celestial-inputs" onSubmit={submit}>
      <label>Landing site<select value={site} onChange={event=>{setSite(event.target.value);setPoint(null);setCursor(0);onSelection(event.target.value,null)}}>
        {sites.map(item=><option key={item.site_id} value={item.site_id}>{item.name} · {item.site_id}</option>)}
      </select></label>
      <label>{series ? 'Start (UTC)' : 'Observation time (UTC)'}<input name="start" type="datetime-local" min="0001-01-01T00:00" max="9999-12-31T23:59" step={1} value={start} onChange={event=>setStart(event.target.value)} required/></label>
      {series && <label>End (UTC)<input name="end" type="datetime-local" min="0001-01-01T00:00" max="9999-12-31T23:59" step={1} value={end} onChange={event=>setEnd(event.target.value)} required/></label>}
      <label>Time increment<select value={step} onChange={event=>setStep(Number(event.target.value))}>
        <option value={60}>1 min</option><option value={600}>10 min</option><option value={3600}>1 hour</option><option value={21600}>6 hours</option><option value={86400}>1 day</option>
      </select></label>
      <label>Antenna minimum elevation (°)<input type="number" min={0} max={90} step="any" value={maskDraft} onChange={event=>setMaskDraft(Number(event.target.value))} required/></label>
      <label>Visibility criterion<select value={criterionDraft} onChange={event=>setCriterionDraft(event.target.value as Criterion)}>{Object.entries(criteria).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      <label className="celestial-series"><input type="checkbox" checked={series} onChange={event=>setSeries(event.target.checked)}/> Time series</label>
      <button className="obs-button obs-primary" type="submit">Calculate visibility</button>
    </form>
    <div className="celestial-layout">
      <section aria-label="Earth direction over terrain">
        <div className="celestial-view-bar"><h2>{active?.name??site}</h2><span>{site} · Native LOLA</span></div>
        <div className="celestial-terrain-viewport">
          {grid ? <TerrainScene grid={grid} layer="elevation" threshold={15} exaggeration={1} contours={false} reset={0}
            selected={earth ? {easting:earth.observer.easting_m,northing:earth.observer.northing_m,elevation:earth.observer.elevation_m} : null}
            celestial={earth && sample ? {longitude:earth.observer.longitude_deg_east,directions:[{
              vector:sample.earth_enu_unit_vector,above:sample.centre_above_horizontal,color:earthPalette.visible,
            }]} : undefined} surfaceColors={texture} onHover={noop} onHeading={noop}
            onSelect={hit=>{const next={easting:hit.easting,northing:hit.northing};setPoint(next);setCursor(0);onSelection(site,next)}}/> :
            <p role="status">{terrain?.key===terrainKey && terrain.error ? terrain.error : active && !active.available ? 'Native terrain unavailable.' : 'Loading native terrain…'}</p>}
        </div>
        <div className="celestial-view-bar celestial-terrain-actions">
          <p>{earth ? `${earth.observer.latitude_deg.toFixed(5)}°, ${earth.observer.longitude_deg_east.toFixed(5)}° east · ${earth.observer.elevation_m.toFixed(2)} m` : 'Observer coordinates pending'}</p>
          <LiquidGlassButton icon={<Crosshair/>} label="Recenter on site" disabled={!point} onClick={()=>{setPoint(null);setCursor(0);onSelection(site,null)}}/>
        </div>
        <p className="muted">Select terrain to move the observer. The ring marks the radial horizontal and the arrow points towards Earth’s centre.</p>
      </section>
      <section aria-label="Earth geometry and clearance">
        <div className="celestial-view-bar"><h2>Earth disc and horizon</h2><span>JPL DE440s</span></div>
        {survey?.key===observerKey && survey.error ? <p role="alert">{survey.error}</p> : sample ?
          <><div className="earth-status">
            <strong>{earthLabels[sample.centre_state]}</strong>
            <strong>{sample.disc_state==='unresolved' ? 'Disc unresolved' : earthLabels[sample.disc_state]}</strong>
            <strong>{sample.antenna_eligible ? 'Elevation meets mask' : 'Elevation below mask'}</strong>
          </div>
          <DiscPlot sample={sample}/>
          <dl className="solar-metrics earth-angle-metrics">
            <div><dt>Earth azimuth</dt><dd>{angle(sample.earth_azimuth_deg)}</dd></div>
            <div><dt>Earth elevation</dt><dd>{angle(sample.earth_elevation_deg)}</dd></div>
            <div><dt>Native horizon</dt><dd>{angle(sample.native_horizon_deg)}</dd></div>
            <div><dt>Apparent radius</dt><dd>{angle(sample.earth_angular_radius_deg)}</dd></div>
            <div><dt>Centre clearance</dt><dd>{angle(sample.clearance_deg.centre)}</dd></div>
            <div><dt>Upper / lower limb clearance</dt><dd>{angle(sample.clearance_deg.upper_limb)} / {angle(sample.clearance_deg.lower_limb)}</dd></div>
          </dl>
          <p className="muted">{reasons[sample.centre_reason]} · Applied antenna assumption {angle(mask)}.</p>
          {sample.rms_horizon_deg && <p className="muted">Centre-bearing RMS scenario {sample.rms_horizon_deg.map(value=>angle(value)).join(' to ')}{sample.rms_sensitive && ' · classification sensitive to height changes'}</p>}
          <p className="celestial-epoch">{utc(sample.utc)}</p></> : <p role="status">Evaluating Earth visibility…</p>}
        <div className="celestial-time-controls">
          <LiquidGlassButton icon={<ChevronLeft/>} label="Previous time" onClick={()=>move(-1)} disabled={'start_utc' in query && cursor===0}/>
          {earth && earth.samples.length>1 && <label>Sample {cursor+1} of {earth.samples.length}<input type="range" aria-label="Earth visibility epoch" min={0} max={earth.samples.length-1} value={cursor} onChange={event=>setCursor(Number(event.target.value))}/></label>}
          <LiquidGlassButton icon={<ChevronRight/>} label="Next time" onClick={()=>move(1)} disabled={'start_utc' in query && cursor>=(earth?.samples.length??1)-1}/>
        </div>
      </section>
    </div>
    {earth && earth.samples.length>1 && <Intervals data={earth}/>}
    <section className="solar-temporal" aria-label="Native Earth visibility map">
      <div className="celestial-view-bar"><h2>Native visibility map</h2>
        <div className="earth-map-controls">
          <label>Map layer <select value={mode} onChange={event=>setMode(event.target.value as MapMode)}><option value="disc">Earth disc</option><option value="centre">Earth centre</option><option value="mask">Antenna elevation</option></select></label>
          <label>Window <select value={side} onChange={event=>setSide(Number(event.target.value))}><option value={6}>6 × 6</option><option value={8}>8 × 8</option><option value={12}>12 × 12</option></select></label>
        </div>
      </div>
      {map && values ? <div className="solar-map-layout"><svg className="solar-cell-map" viewBox={`0 0 ${side} ${side}`} role="img" aria-label="Native LOLA cell visibility classification map">
        <g aria-hidden="true">{values.map((color,index)=><rect key={index} x={index%side} y={Math.floor(index/side)} width={1} height={1} fill={color}><title>{earthLabels[mapClass(map.cells[index],mode)]}</title></rect>)}</g>
      </svg><dl className="solar-metrics">
        <div><dt>Centre visible / obstructed / unresolved</dt><dd>{map.counts.centre_visible} / {map.counts.centre_obstructed} / {map.counts.centre_unresolved}</dd></div>
        <div><dt>Disc full / partial / obscured / unresolved</dt><dd>{map.counts.disc_fully_visible} / {map.counts.disc_partially_visible} / {map.counts.disc_fully_obscured} / {map.counts.disc_unresolved}</dd></div>
        <div><dt>Antenna eligible / valid / NoData</dt><dd>{map.counts.antenna_eligible} / {map.counts.valid} / {map.counts.invalid}</dd></div>
        <div><dt>Native spacing</dt><dd>{map.terrain.resolution_m.join(' × ')} m</dd></div>
        {mapStatistics?.map(item=><div key={item.key}><dt>{item.name} / valid</dt><dd>{percent(map.percent_of_valid[item.key])}</dd></div>)}
        {mode==='mask' && <div><dt>Elevation below mask / valid</dt><dd>{percent(map.percent_of_valid.antenna_eligible == null ? null : 100-map.percent_of_valid.antenna_eligible)}</dd></div>}
      </dl></div> : regional?.key===regionKey && regional.error ? <p role="alert">{regional.error}</p> : epoch ? <p role="status">Tracing the native visibility window…</p> : null}
      <ul className="solar-legend">{mapKeys[mode].map(key=><li key={key}><i style={{background:earthPalette[key]}}/>{earthLabels[key]}</li>)}</ul>
    </section>
    <section className="solar-temporal" aria-label="Matched-epoch Earth visibility comparison">
      <div className="celestial-view-bar"><h2>Matched-epoch comparison</h2><LiquidGlassButton label="Compare three sites" onClick={compareSites} disabled={!epoch||matches?.pending}/></div>
      <p className="muted">{epoch && <>{utc(epoch)} · </>}Equal {side} × {side} native windows at each site centre. The ray footprints differ by site.</p>
      {matches?.pending && <p role="status">Tracing site {matches.rows.length+1} of {sites.length}…</p>}
      {matches && matches.rows.length>0 && <div className="mission-table"><table><thead><tr><th>Site</th><th>Ray footprint</th><th>Above horizontal</th><th>Centre visible / blocked / unresolved</th><th>Disc full / partial / obscured / unresolved</th><th>Meets mask</th><th>Valid / NoData</th></tr></thead><tbody>
        {matches.rows.map(row=>{
          const d = row.data
          return <tr key={row.key}><th scope="row">{sites.find(item=>item.site_id===row.key)?.name??row.key}</th>{d ?
            <><td>{(d.terrain.bounds_m[2]-d.terrain.bounds_m[0])/1000} × {(d.terrain.bounds_m[3]-d.terrain.bounds_m[1])/1000} km</td>
              <td>{d.counts.geometric_above_horizontal}</td><td>{d.counts.centre_visible} / {d.counts.centre_obstructed} / {d.counts.centre_unresolved}</td>
              <td>{d.counts.disc_fully_visible} / {d.counts.disc_partially_visible} / {d.counts.disc_fully_obscured} / {d.counts.disc_unresolved}</td>
              <td>{d.counts.antenna_eligible}</td><td>{d.counts.valid} / {d.counts.invalid}</td></> : <td colSpan={6}>{row.error}</td>}</tr>
        })}
      </tbody></table></div>}
    </section>
    <details className="celestial-provenance"><summary>Frames, terrain and visibility evidence</summary>
      <p>Airless apparent geometry from Phase 3.1, with native LOLA rays from Phase 3.2. The diagram and clearances use the native horizon at the centre bearing. The disc classification also uses evidence across other bearings.</p>
      <p>Antenna eligibility compares Earth-centre elevation with the configured assumption. Radio link performance requires separate equipment and propagation analysis.</p>
      {sample && <p>Disc evidence · {sample.disc_evidence.replaceAll('_',' ')}. Confirmed clear, obstructed, unresolved sampled directions · {sample.disc_probe_counts.visible} / {sample.disc_probe_counts.obstructed} / {sample.disc_probe_counts.unresolved}.</p>}
      {earth && <p><a href={earth.terrain.source_url}>{earth.terrain.file}</a> · {earth.terrain.resolution_m.join(' × ')} m/px{earth.terrain.rms_source_url && <> · <a href={earth.terrain.rms_source_url}>Elevation RMS</a></>}</p>}
    </details>
  </section>
}
