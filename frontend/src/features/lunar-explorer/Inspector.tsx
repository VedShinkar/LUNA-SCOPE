import { Crosshair, PanelRightClose } from 'lucide-react'
import type { Horizon, TerrainGrid, TerrainPoint } from '../../services/terrain'
import type { Selected } from '../../visualization/TerrainScene'

export type Result<T> = { data?: T; error?: string }
export const format = (n: number | null | undefined, digits = 2) => n == null ? 'Unavailable' :
  n.toLocaleString('en', { maximumFractionDigits: digits, minimumFractionDigits: digits })
const metric = (value: number | null | undefined, unit: string) => value == null ? 'Unavailable' : `${format(value)} ${unit}`

function HorizonPlot({ profile }: { profile: Horizon }) {
  const points = profile.horizon_angles_deg
  const finite = points.filter(value => value != null)
  if (!finite.length) return <p className="muted">No valid horizon rays at this point.</p>
  const lo = Math.min(0, ...finite)
  const hi = Math.max(lo + 1, ...finite)
  const x = (i: number) => 5 + 230 * profile.azimuths_deg[i] / 360
  const y = (v: number) => 64 - 59 * (v - lo) / (hi - lo)
  const line = points.map((value, i) => value == null ? '' :
    `${i && points[i - 1] != null ? 'L' : 'M'}${x(i)},${y(value)}`).join(' ')
  return <div className="horizon-plot">
    <svg viewBox="0 0 240 70" role="img" aria-label={`Horizon obstruction angles from ${format(lo)} to ${format(hi)} degrees`}>
      <path d={`M5 ${y(0)} H235`} stroke="#526172" />
      <path d={line} fill="none" stroke="#75d6df" strokeWidth="1.5" />
    </svg>
    <div className="horizon-labels"><span>N</span><span>E</span><span>S</span><span>W</span><span>N</span></div>
  </div>
}

export function Inspector({ grid, selected, point, horizon, showHorizon, landing, threshold, close }: {
  grid: TerrainGrid | undefined
  selected: Selected | null
  point: Result<TerrainPoint>
  horizon: Result<Horizon>
  showHorizon: boolean
  landing: boolean
  threshold: number
  close: () => void
}) {
  const p = point.data
  return <aside className="side inspector" aria-label="Point inspector">
    <div className="panel-heading"><span>Point inspector</span><button className="icon-button" title="Collapse inspector" aria-label="Collapse inspector" onClick={close}><PanelRightClose size={17} /></button></div>
    {!selected ? <div className="empty-inspector">
      <span className="empty-icon"><Crosshair size={25} strokeWidth={1.4} /></span>
      <h2>Select a point</h2>
      <p>Click the terrain to inspect measurements from the native grid.</p>
    </div> : <div className="panel-body">
      <div className="inspector-selection"><Crosshair size={15} /> Selected point</div>
      <dl className="readings">
        <div><dt>Easting</dt><dd>{metric(selected.easting, 'm')}</dd></div>
        <div><dt>Northing</dt><dd>{metric(selected.northing, 'm')}</dd></div>
        {p && <>
          <div><dt>Elevation</dt><dd>{metric(p.elevation_m, 'm')}</dd></div>
          <div><dt>Slope</dt><dd>{metric(grid?.layers.slope ? p.slope_deg : null, '°')}</dd></div>
          <div><dt>Aspect</dt><dd>{!grid?.layers.aspect ? 'Unavailable' : p.aspect_deg === -1 ? 'Flat' : metric(p.aspect_deg, '°')}</dd></div>
          <div><dt>Roughness · 15 m</dt><dd>{metric(p.roughness.roughness_15m_m, 'm')}</dd></div>
          <div><dt>Roughness · 35 m</dt><dd>{metric(p.roughness.roughness_35m_m, 'm')}</dd></div>
          <div><dt>Roughness · 75 m</dt><dd>{metric(p.roughness.roughness_75m_m, 'm')}</dd></div>
          <div><dt>LOLA returns</dt><dd>{p.uncertainty_and_observation.lola_observation_count ?? 'Unavailable'}</dd></div>
          <div><dt>Elevation RMS</dt><dd>{metric(p.uncertainty_and_observation.elevation_uncertainty_m_rms, 'm')}</dd></div>
          <div><dt>Slope RMS</dt><dd>{metric(p.uncertainty_and_observation.slope_uncertainty_deg_rms, '°')}</dd></div>
          <div><dt>Physical hazard</dt><dd>{p.hazard_classification.physical_hazard_class}</dd></div>
          <div><dt>Combined screen</dt><dd className={`severity ${p.hazard_classification.combined_screening_class.toLowerCase()}`}>{grid?.layers.hazards ? p.hazard_classification.combined_screening_class : 'Unavailable'}</dd></div>
          {landing && <div><dt>Slope suitability</dt><dd>{!grid?.layers.slope || p.slope_deg == null ? 'Unknown' : p.slope_deg <= threshold ? 'Within limit' : 'Exceeds limit'}</dd></div>}
        </>}
      </dl>
      {!p && <p role="status" className={point.error ? 'error' : 'muted'}>{point.error ?? 'Loading native measurements…'}</p>}
      {p && <p className="muted">Aspect is clockwise from grid north. Uncertainties are RMS.</p>}
    </div>}
    {showHorizon && <div className="panel-body horizon">
      <h2>Local horizon</h2>
      <p className="muted">2 m observer · 5 km range · lunar curvature</p>
      {horizon.data ? <HorizonPlot profile={horizon.data} /> :
        <p role="status" className={horizon.error ? 'error' : 'muted'}>{horizon.error ?? (selected ? 'Tracing horizon rays…' : 'Select an observer point.')}</p>}
    </div>}
  </aside>
}
