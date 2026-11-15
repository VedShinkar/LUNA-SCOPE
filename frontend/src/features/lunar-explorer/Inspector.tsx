import { Crosshair, PanelRightClose } from 'lucide-react'
import type { Horizon, LayerName, TerrainGrid, TerrainPoint } from '../../services/terrain'
import type { Selected } from '../../visualization/TerrainScene'
import { polarCoordinates } from '../../visualization/lunar-coordinates'
import { GlassSurface, LiquidGlassButton } from '../../components/ui/liquid-glass'
import { siteCode } from './copy'
import { nativeCell, type Measurement } from './survey-tools'
import { layerNames } from './layers'

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

export function Inspector({ grid, selected, point, horizon, showHorizon, landing, threshold, close, layer, pinned,onPin,onSave,saved }: {
  grid: TerrainGrid | undefined
  selected: Selected | null
  point: Result<TerrainPoint>
  horizon: Result<Horizon>
  showHorizon: boolean
  landing: boolean
  threshold: number
  close: () => void
  layer:LayerName; pinned:boolean;onPin:()=>void;onSave:()=>void
  saved?: Extract<Measurement,{kind:'Terrain sample'}>
}) {
  const p = point.data
  const geographic = selected && polarCoordinates(selected.easting, selected.northing)
  const cell=grid&&selected?nativeCell(grid.source_transform,selected):undefined
  return <GlassSurface as="aside" className="side inspector refined-inspector" aria-label="Point inspector">
    <div className="panel-heading"><span>Terrain Sample</span><LiquidGlassButton label="Close Inspector" iconOnly icon={<PanelRightClose />} onClick={close} /></div>
    {!selected ? <div className="empty-inspector">
      <span className="empty-icon"><Crosshair size={25} strokeWidth={1.4} /></span>
      <h2>Select a terrain point</h2>
      <p>Point values come from the corresponding native raster cell.</p>
    </div> : <div className="panel-body">
      <div className="inspector-selection"><Crosshair size={15} /> {layerNames[layer]}</div>
      <div className="history-actions"><LiquidGlassButton label={pinned?'Unpin Sample':'Pin Sample'} aria-pressed={pinned} onClick={onPin}/><LiquidGlassButton label="Save Sample" disabled={!p} onClick={onSave}/></div>
      <h3>Location</h3>
      <dl className="readings">
        <div><dt>Site</dt><dd>{grid?siteCode(grid.site_id):'Unavailable'}</dd></div>
        <div><dt>Raster row / column</dt><dd>{cell?`${cell.row} / ${cell.col}`:'Unavailable'}</dd></div>
        <div><dt>Easting / Northing</dt><dd>{format(selected.easting,1)} / {format(selected.northing,1)} m</dd></div>
        {geographic && <><div><dt>Latitude</dt><dd>{geographic.latitude.toFixed(5)}°</dd></div><div><dt>Longitude (east-positive)</dt><dd>{geographic.longitude.toFixed(5)}°</dd></div></>}
      </dl>
        {p && <><h3>Terrain Properties</h3><dl className="readings">
          <div><dt>LOLA elevation</dt><dd>{metric(p.elevation_m, 'm')}</dd></div>
          <div><dt>Calculated Slope</dt><dd>{metric(saved || grid?.layers.slope ? p.slope_deg : null, '°')}</dd></div>
          <div><dt>Calculated Aspect</dt><dd>{!saved && !grid?.layers.aspect ? 'Unavailable' : p.aspect_deg === -1 ? 'Flat' : metric(p.aspect_deg, '°')}</dd></div>
          <div><dt>Roughness · 15 m</dt><dd>{metric(p.roughness.roughness_15m_m, 'm')}</dd></div>
          <div><dt>Roughness · 35 m</dt><dd>{metric(p.roughness.roughness_35m_m, 'm')}</dd></div>
          <div><dt>Roughness · 75 m</dt><dd>{metric(p.roughness.roughness_75m_m, 'm')}</dd></div>
          </dl><h3>Data Quality</h3><dl className="readings">
          <div><dt>Observation Count</dt><dd>{p.uncertainty_and_observation.lola_observation_count ?? 'Unavailable'}</dd></div>
          <div><dt>Elevation Uncertainty</dt><dd>{metric(p.uncertainty_and_observation.elevation_uncertainty_m_rms, 'm RMS')}</dd></div>
          <div><dt>Slope Uncertainty</dt><dd>{metric(p.uncertainty_and_observation.slope_uncertainty_deg_rms, '° RMS')}</dd></div>
          <div><dt>{grid?.sampling.window?'Window valid coverage':'Raster valid coverage'}</dt><dd>{grid?`${format(100-grid.nodata_percent,2)}%`:'Unavailable'}</dd></div>
          <div><dt>Physical hazard</dt><dd>{p.hazard_classification.physical_hazard_class}</dd></div>
          <div><dt>Combined screen</dt><dd className={`severity ${p.hazard_classification.combined_screening_class.toLowerCase()}`}>{grid?.layers.hazards ? p.hazard_classification.combined_screening_class : 'Unavailable'}</dd></div>
          {landing && <div><dt>Slope suitability</dt><dd>{!grid?.layers.slope || p.slope_deg == null ? 'Unknown' : p.slope_deg <= threshold ? 'Within limit' : 'Exceeds limit'}</dd></div>}
        </dl></>}
      {!p && <p role="status" className={point.error ? 'error' : 'muted'}>{point.error ?? 'Loading native measurements…'}</p>}
      {saved ? <><h3>Saved Provenance</h3><p className="muted">{saved.source}<br/>{saved.provenance?.sourceFile}{saved.provenance?.resolution && ` · ${saved.provenance.resolution.join(' × ')} m/px`}</p></> : grid&&<><h3>Provenance</h3><p className="muted"><a href={grid.elevation_source_url}>{siteCode(grid.site_id)} · NASA LOLA elevation</a><br/>{grid.source_resolution.join(' × ')} m/px · {grid.source_file}<br/>Aspect is measured clockwise from grid north.</p></>}
    </div>}
    {showHorizon && <div className="panel-body horizon">
      <h2>Local horizon</h2>
      <p className="muted">2 m observer · 5 km range · lunar curvature</p>
      {horizon.data ? <HorizonPlot profile={horizon.data} /> :
        <p role="status" className={horizon.error ? 'error' : 'muted'}>{horizon.error ?? (selected ? 'Tracing horizon rays…' : 'Select an observer point.')}</p>}
    </div>}
  </GlassSurface>
}
