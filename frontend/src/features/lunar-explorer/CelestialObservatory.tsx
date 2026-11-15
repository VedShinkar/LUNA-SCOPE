import { useEffect, useState, type FormEvent } from 'react'
import type { ScienceSelection } from './WorkspaceNavigation'
import { ChevronLeft, ChevronRight, Crosshair } from 'lucide-react'
import { LiquidGlassButton } from '../../components/ui/liquid-glass'
import { getCelestialGeometry, getCelestialMetadata, type CelestialEpoch, type CelestialMetadata,
  type CelestialResult, type TimeQuery } from '../../services/celestial'
import type { LunarSite } from '../../services/lunar'
import { getGrid, type MapPoint, type TerrainGrid } from '../../services/terrain'
import TerrainScene, { type Hit } from '../../visualization/TerrainScene'
import { inputUtc, skyPosition, stepUtc } from '../../visualization/celestial-display'

const bodies = [
  { key: 'sun', name: 'Sun', color: '#ffd383' },
  { key: 'earth', name: 'Earth', color: '#75def4' },
] as const
const increments = [[60, '1 min'], [600, '10 min'], [3600, '1 hour'], [21600, '6 hours'], [86400, '1 day'], [604800, '7 days']] as const
const noop = () => {}
const angle = (value: number | null) => value === null ? 'Undefined' : `${value.toFixed(4)}°`
const showUtc = (value: string) => value.replace('T', ' ').replace(/(?:\.0+)?Z$/, ' UTC')
const now = () => new Date().toISOString().slice(0, 19)

function HorizonPlot({ sample }: { sample?: CelestialEpoch }) {
  const limit = sample ? Math.max(10, Math.ceil(Math.max(...bodies.map(({key}) => Math.abs(sample[key].elevation_deg))) / 10) * 10) : 10
  const ticks = [-limit, -limit / 2, 0, limit / 2, limit]
  return <svg className="horizon-plot" role="img" aria-label="Local horizontal chart. Azimuth measured clockwise from true north. Elevation relative to the radial horizontal plane." viewBox="0 0 535 232">
    <rect x={46} y={28} width={468} height={81} fill="#102136"/>
    <rect x={46} y={109} width={468} height={81} fill="#0b131f"/>
    {ticks.map(el => {
      const {y} = skyPosition(0, el, limit)
      return <g key={el}><path d={`M46 ${y}H514`} className={el === 0 ? 'sky-horizon' : 'sky-grid'} />
        <text x={39} y={y + 4} textAnchor="end">{el > 0 ? '+' : ''}{el}°</text></g>
    })}
    {['N', 'E', 'S', 'W', 'N'].map((name, i) => {
      const {x} = skyPosition(i * 90, 0, limit)
      return <g key={i}><path d={`M${x} 28V190`} className="sky-grid"/>
        <text x={x} y={206} textAnchor="middle">{name} {i * 90}°</text></g>
    })}
    <text x={47} y={17}>ELEVATION</text>
    <text x={280} y={226} textAnchor="middle">AZIMUTH · TRUE NORTH</text>
    {sample && bodies.map(({key, name, color}) => {
      const direction = sample[key]
      if (direction.azimuth_deg === null) return null
      const {x, y} = skyPosition(direction.azimuth_deg, direction.elevation_deg, limit)
      const right = x < 470
      return <g key={key} data-body={key} transform={`translate(${x} ${y})`}>
        <path d={`M0 0V${109 - y}`} stroke={color} strokeDasharray="3 4" opacity=".65"/>
        <circle r={9} stroke={color} fill={direction.above_local_horizontal ? color : '#0b131f'} fillOpacity={direction.above_local_horizontal ? '.22' : '1'} strokeWidth={1.5} strokeDasharray={direction.above_local_horizontal ? undefined : '3 2'}/>
        <circle r={2.5} fill={color}/>
        <text x={right ? 13 : -13} y={-8} textAnchor={right ? 'start' : 'end'} style={{fill: color}}>{name}</text>
      </g>
    })}
  </svg>
}

export default function CelestialObservatory({ sites, initialSite, initialPoint, onSelection, onEpoch }: { sites: LunarSite[] } & ScienceSelection) {
  const [siteId, setSiteId] = useState(initialSite)
  const [point, setPoint] = useState<MapPoint | null>(initialPoint ?? null)
  const [draft, setDraft] = useState(now)
  const [end, setEnd] = useState(() => stepUtc(inputUtc(now()), 86400))
  const [increment, setIncrement] = useState(3600)
  const [series, setSeries] = useState(false)
  const [query, setQuery] = useState<TimeQuery>(() => ({utc: inputUtc(draft)}))
  const [cursor, setCursor] = useState(0)
  const [grid, setGrid] = useState<TerrainGrid>()
  const [gridError, setGridError] = useState('')
  const [metadata, setMetadata] = useState<CelestialMetadata>()
  const [metadataError, setMetadataError] = useState('')
  const [outcome, setOutcome] = useState<{ key: string; data?: CelestialResult; error?: string }>()
  const observerSite = sites.find(site => site.site_id === siteId)
  const key = JSON.stringify([siteId, point, query])
  const result = outcome?.key === key ? outcome.data : undefined
  const error = outcome?.key === key ? outcome.error : undefined
  const sample = result?.samples[cursor]
  useEffect(()=>{if(sample?.utc) onEpoch?.(sample.utc)},[sample?.utc,onEpoch])
  const observer = result?.observer ?? (!point ? metadata?.sites.find(site => site.site_id === siteId)?.observer : undefined)

  useEffect(() => {
    const controller = new AbortController()
    getCelestialMetadata(controller.signal).then(setMetadata).catch(err => {
      if (!controller.signal.aborted) setMetadataError(err.message)
    })
    return () => controller.abort()
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    setGridError('')
    getGrid(siteId, 160, controller.signal).then(next => {
      if (!controller.signal.aborted) setGrid(next)
    }).catch(err => { if (!controller.signal.aborted) setGridError(err.message) })
    return () => controller.abort()
  }, [siteId])
  useEffect(() => {
    const controller = new AbortController()
    getCelestialGeometry(siteId, point, query, controller.signal).then(data => {
      if (!controller.signal.aborted) setOutcome({key, data})
    }).catch(err => { if (!controller.signal.aborted) setOutcome({key, error: err.message}) })
    return () => controller.abort()
  }, [siteId, point, query, key])

  function selectPoint(hit: Hit) {
    const next = {easting: hit.easting, northing: hit.northing}
    setPoint(next)
    onSelection(siteId,next)
    setCursor(0)
  }
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const start = String(fields.get('utc'))
    const finish = series ? String(fields.get('end_utc')) : ''
    setDraft(start)
    if (series) setEnd(finish)
    setCursor(0)
    setOutcome(undefined)
    setQuery(series ? {start_utc: inputUtc(start), end_utc: inputUtc(finish), step_seconds: increment} : {utc: inputUtc(start)})
  }
  function step(direction: number) {
    if ('start_utc' in query) {
      setCursor(index => Math.min((result?.samples.length ?? 1) - 1, Math.max(0, index + direction)))
    } else {
      const next = stepUtc(query.utc, increment * direction)
      setDraft(next)
      setQuery({utc: inputUtc(next)})
    }
  }
  const terrain = grid?.site_id === siteId ? grid : undefined
  return <section className="celestial-observatory" aria-label="Celestial Geometry Observatory">
    <form className="mission-inputs celestial-inputs" onSubmit={apply}>
      <label>Landing site<select value={siteId} onChange={event => {setSiteId(event.target.value); setPoint(null); setCursor(0); onSelection(event.target.value,null)}}>
        {sites.map(site => <option key={site.site_id} value={site.site_id}>{site.name} · {site.site_id}</option>)}
      </select></label>
      <label>{series ? 'Start (UTC)' : 'Observation time (UTC)'}<input name="utc" type="datetime-local" step={1} min="0001-01-01T00:00:00" max="9999-12-31T23:59:59" value={draft} onChange={event => setDraft(event.target.value)} required /></label>
      {series && <label>End (UTC)<input name="end_utc" type="datetime-local" step={1} min="0001-01-01T00:00:00" max="9999-12-31T23:59:59" value={end} onChange={event => setEnd(event.target.value)} required /></label>}
      <label>Time increment<select value={increment} onChange={event => setIncrement(Number(event.target.value))}>
        {increments.map(([seconds, label]) => <option key={seconds} value={seconds}>{label}</option>)}
      </select></label>
      <label className="celestial-series"><input type="checkbox" checked={series} onChange={event => setSeries(event.target.checked)} /> Time series</label>
      <button className="obs-button obs-primary" type="submit">Calculate geometry</button>
      <LiquidGlassButton label="Use current UTC" onClick={() => {const utc = now(); setDraft(utc); setSeries(false); setCursor(0); setQuery({utc: inputUtc(utc)})}} />
    </form>
    <div className="celestial-layout">
      <section className="celestial-terrain" aria-label="Lunar observer terrain">
        <div className="celestial-view-bar"><h2>{observerSite?.name ?? 'Lunar terrain'}</h2><span>{siteId} · LOLA</span></div>
        <div className="celestial-terrain-viewport">
          {terrain ? <TerrainScene grid={terrain} layer="elevation" exaggeration={1} contours={false} threshold={15} reset={0}
            selected={observer ? {easting: observer.easting_m, northing: observer.northing_m, elevation: observer.elevation_m} : null}
            celestial={observer ? {longitude: observer.longitude_deg_east, directions: sample ? bodies.map(({key, color}) => ({
              vector: sample[key].enu_unit_vector, above: sample[key].above_local_horizontal, color,
            })) : []} : undefined}
            onHover={noop} onHeading={noop} onSelect={selectPoint} /> : <p role="status">{gridError || 'Loading site terrain…'}</p>}
        </div>
        <div className="celestial-view-bar celestial-terrain-actions">
          <p>{observer ? `${observer.latitude_deg.toFixed(5)}°, ${observer.longitude_deg_east.toFixed(5)}° E · ${observer.elevation_m.toFixed(2)} m` : 'Observer position unavailable'}</p>
          <LiquidGlassButton icon={<Crosshair />} label="Use raster centre" disabled={!point} onClick={() => {setPoint(null); setCursor(0); onSelection(siteId,null)}} />
        </div>
        <p className="muted">Select terrain to move the observer. The ring marks the local horizontal. Dashed rays indicate body centres below it.</p>
      </section>
      <section className="celestial-sky" aria-label="Sun and Earth directions">
        <div className="celestial-view-bar"><h2>Local horizon</h2><span>{result?.ephemeris ?? 'SPICE'}</span></div>
        <HorizonPlot sample={sample} />
        <table className="celestial-readouts"><thead><tr><th scope="col">Body</th><th scope="col">Azimuth</th><th scope="col">Elevation</th><th scope="col">Diameter</th></tr></thead>
          <tbody>{bodies.map(({key, name, color}) => {
            const direction = sample?.[key]
            return <tr key={key}><th scope="row"><span style={{color}}>{name}</span>{direction && <small>{direction.elevation_deg === 0 ? 'On horizontal' : direction.above_local_horizontal ? 'Above horizontal' : 'Below horizontal'}</small>}</th>
              <td>{direction ? angle(direction.azimuth_deg) : '—'}</td><td>{direction ? angle(direction.elevation_deg) : '—'}</td>
              <td>{direction ? angle(direction.angular_diameter_deg) : '—'}</td></tr>
          })}</tbody>
        </table>
        {error ? <p role="alert" className="celestial-error">{error}</p> : <p className="celestial-epoch" role="status">{sample ? showUtc(sample.utc) : 'Calculating Sun and Earth geometry…'}</p>}
        <div className="celestial-time-controls">
          <LiquidGlassButton icon={<ChevronLeft />} label="Previous time" onClick={() => step(-1)} disabled={'start_utc' in query && cursor === 0} />
          {result && result.samples.length > 1 && <label>Sample {cursor + 1} of {result.samples.length}<input aria-label="Observation sample" type="range" min={0} max={result.samples.length - 1} value={cursor} onChange={event => setCursor(Number(event.target.value))} /></label>}
          <LiquidGlassButton icon={<ChevronRight />} label="Next time" onClick={() => step(1)} disabled={'start_utc' in query && cursor >= (result?.samples.length ?? 1) - 1} />
        </div>
      </section>
    </div>
    <details className="celestial-provenance"><summary>Frames, data sources and coverage</summary>
      <p>Airless apparent body-centre directions. SPICE applies converged reception light-time and stellar aberration (CN+S). Azimuth is clockwise from true north. Elevation is relative to the observer’s radial horizontal plane. Terrain obstruction and gravitational light bending are outside this model.</p>
      <p>{result?.conventions.inertial_frame ?? 'J2000 (ICRF)'} → {result?.conventions.body_fixed_frame ?? 'MOON_ME_DE440_ME421'} → local east, north, up. UTC is converted to SPICE ephemeris time.</p>
      {observer && <p>{observer.datum} · <a href={observer.source_url}>{observer.source_file}</a> · {observer.placement}</p>}
      <p>{metadata?.coverage ? `${showUtc(metadata.coverage.start_utc)} to ${showUtc(metadata.coverage.end_utc)} under the loaded leap-second table.` : metadata?.error ?? metadataError ?? 'Reading kernel coverage…'}</p>
      <p>{metadata?.limits.max_samples ?? 241} samples per series. The reference comparison measures regression agreement at selected epochs. Individual results carry no statistical uncertainty estimate.</p>
      {result?.quality_flags.includes('pre_1972_time_uses_spice_utc_convention') && <p>Before 1972, time uses SPICE’s extrapolated UTC convention.</p>}
      {result?.quality_flags.includes('future_civil_leap_seconds_not_predicted') && <p>Future civil leap seconds are unavailable in the loaded kernel.</p>}
      <ul>{(result?.kernels ?? metadata?.kernels)?.map(kernel => <li key={kernel.file}><a href={kernel.url} title={kernel.sha256}>{kernel.file}</a></li>)}</ul>
    </details>
  </section>
}
