import { Aperture, ArrowLeft, ArrowUpRight, MapPin, Mountain } from 'lucide-react'
import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react'
import type { LunarSite } from '../../services/lunar'
import { getComparison, type Comparison, type MapPoint } from '../../services/terrain'
import { usePanelMotion } from '../../components/ui/use-panel-motion'
import { GlassSurface, LiquidGlassButton } from '../../components/ui/liquid-glass'
import { siteCode } from './copy'
import { ReportActions } from './ScientificReport'
import { WorkspaceNavigation, type ScienceSelection, type WorkspaceId } from './WorkspaceNavigation'
import type { DecisionContext } from '../../services/mission-intelligence'
import './analysis-workspace.css'
const ComparativeTerrain = lazy(() => import('./ComparativeTerrain').then(module => ({default:module.ComparativeTerrain})))
const CelestialObservatory = lazy(() => import('./CelestialObservatory'))
const SolarObservatory = lazy(() => import('./SolarObservatory'))
const EarthObservatory = lazy(() => import('./EarthObservatory'))
const MissionTimeline = lazy(() => import('./MissionTimeline'))
const DecisionWorkspace = lazy(() => import('./DecisionWorkspace'))

const titles: Record<WorkspaceId, string> = {
  overview:'Site overview', terrain:'Terrain analysis', comparison:'Comparative Terrain Analysis',
  celestial:'Celestial Geometry Observatory', illumination:'Solar Illumination Observatory',
  communication:'Earth Visibility Observatory', operations:'Operations timeline',
  intelligence:'Mission Intelligence', scenarios:'Scenario comparison', copilot:'Mission Copilot', reports:'Reports and history',
}
export type ManualEvent = { id: number; name: string; hours: number; phase: string }
const phases = ['Landing', 'Deployment', 'Power', 'Communication', 'Surface operations', 'Contingency']
const number = (value?: number | null, unit = '') => value == null ? 'Unavailable' : `${value.toLocaleString(undefined, {maximumFractionDigits: 2})}${unit}`

export default function MissionWorkspaces({ id, onChange, onExit, sites, siteId, point, onSelection, onHistory, historyPanel, events, setEvents, decisionContext, onApply, onEpoch }: {
  id: WorkspaceId; onChange: (id: WorkspaceId) => void; onExit: () => void; sites: LunarSite[]; siteId: string
  point:MapPoint|null; onSelection:ScienceSelection['onSelection']; onHistory:()=>void; historyPanel:ReactNode
  events:ManualEvent[]; setEvents:(update:(items:ManualEvent[])=>ManualEvent[])=>void
  decisionContext:DecisionContext|null; onApply:(request:DecisionContext)=>void; onEpoch:(utc:string)=>void
}) {
  const [comparison, setComparison] = useState<Comparison>()
  const [failure, setFailure] = useState('')
  const [cursor, setCursor] = useState(0)
  const scope = useRef<HTMLElement>(null)
  usePanelMotion(scope, id)
  useEffect(() => {
    if (id !== 'comparison' || comparison) return
    const abort = new AbortController()
    setFailure('')
    getComparison(abort.signal).then(setComparison).catch(err => { if (!abort.signal.aborted) setFailure(err.message) })
    return () => abort.abort()
  }, [id, comparison])
  const site = sites.find(item=>item.site_id===siteId)
  const observer = {sites, initialSite:siteId, initialPoint:point, onSelection, onEpoch}
  const latest = Math.max(1, ...events.map(item => item.hours))
  const rows = [
    {label: 'Terrain Resolution', read: (s: LunarSite) => s.available ? `${s.source_resolution_m.join(' × ')} m/px` : 'Unavailable'},
    {label: 'Elevation span', read: (s: LunarSite) => {
      const range = comparison?.sites.find(e => e.site_id === s.site_id)?.metrics?.elevation
      return range ? `${number(range.minimum_m)} to ${number(range.maximum_m, ' m')}` : 'Unavailable'
    }},
    {label: 'Direct observation support', read: (s: LunarSite) => number(comparison?.sites.find(e => e.site_id === s.site_id)?.metrics?.observations?.direct_observation_percentage, '%')},
    {label: 'Median roughness · 15 m', read: (s: LunarSite) => number(comparison?.sites.find(e => e.site_id === s.site_id)?.metrics?.roughness?.small?.statistics?.median_m, ' m')},
    {label: 'High combined hazard', read: (s: LunarSite) => number(comparison?.sites.find(e => e.site_id === s.site_id)?.metrics?.hazards?.HIGH, '%')},
    {label: 'Median NASA slope', read: (s: LunarSite) => number(comparison?.sites.find(e => e.site_id === s.site_id)?.metrics?.nasa_slope_median_deg, '°')},
    {label: 'Median slope uncertainty', read: (s: LunarSite) => number(comparison?.sites.find(e => e.site_id === s.site_id)?.metrics?.slope_uncertainty_median_deg, '° RMS')},
    {label: 'Median elevation uncertainty', read: (s: LunarSite) => number(comparison?.sites.find(e => e.site_id === s.site_id)?.metrics?.elevation_uncertainty_median_m, ' m RMS')},
  ]
  return <div className="app-shell science-workspace mission-workspace analysis-shell">
    <a href="#mission-view" className="skip">Skip to workspace</a>
    <header className="topbar observatory-bar">
      <div className="identity"><span className="brand-icon"><Aperture size={22} /></span><strong>LUNA-SCOPE</strong></div>
      <div className="top-divider"/>
      <span className="analysis-top-label">Site Analysis</span>
      <div className="top-actions"><LiquidGlassButton icon={<ArrowLeft />} label="Return to Survey" onClick={onExit} /></div>
    </header>
    <WorkspaceNavigation active={id} onSelect={onChange}/>
    <main id="mission-view" tabIndex={-1} ref={scope}>
      <section className="observatory-panel mission-sheet" data-enter-panel>
        <div className="analysis-page-heading">
          <div><p className="analysis-kicker">South polar region</p><h1>{titles[id]}</h1></div>
          {site&&<div className="analysis-context"><MapPin size={16} aria-hidden="true"/><div>
            <strong>{site.name} · {siteCode(siteId)}</strong>
            <span>{point ? `E ${point.easting.toFixed(1)} · N ${point.northing.toFixed(1)} m` : 'Raster centre'}</span>
          </div></div>}
        </div>
        {id === 'overview' ? <GlassSurface className="analysis-overview">
          <div><h2>{site?.name ?? 'Landing sites'}</h2>
            <p>{site?.available ? `LOLA terrain · ${site.source_resolution_m.join(' × ')} m/px` : 'Native terrain is currently unavailable.'}</p>
            {site&&<a href={site.source_url}>Source dataset <ArrowUpRight size={13} aria-hidden="true"/></a>}
          </div>
          <label>Landing site<select value={siteId} onChange={event=>onSelection(event.target.value,null)}>
            {sites.map(item=><option key={item.site_id} value={item.site_id}>{item.name} · {siteCode(item.site_id)}</option>)}
          </select></label>
          <LiquidGlassButton label="Open terrain analysis" icon={<Mountain/>} onClick={()=>onChange('terrain')} disabled={!site?.available}/>
        </GlassSurface> : id === 'reports' ? <div className="analysis-report-list">
          <section><h2>Terrain reports</h2><p>Open site statistics, data quality and uncertainty reports.</p>
            {site?.available ? <div className="analysis-actions">
              <ReportActions key={siteId+'-site'} triggerLabel="Site statistics report" title={`${site.name} · Individual site analysis`} sites={[site]} layer="elevation"/>
              <ReportActions key={siteId+'-quality'} triggerLabel="Data quality report" title={`${site.name} · Data quality and uncertainty`} sites={[site]} layer="uncertainty"/>
            </div> : <p role="status">Site data unavailable.</p>}
          </section>
          <section><h2>Reports from a workspace</h2><p>Open a comparison or timeline to export its results. Path profiles can be exported from Terrain analysis.</p>
            <div className="analysis-actions">
              <LiquidGlassButton label="Terrain comparison" onClick={()=>onChange('comparison')}/>
              <LiquidGlassButton label="Operations timeline" onClick={()=>onChange('operations')}/>
              <LiquidGlassButton label="Terrain analysis" onClick={()=>onChange('terrain')}/>
            </div>
          </section>
          <section><h2>Measurement history</h2><p>Reopen, rename or export measurements saved in this browser.</p><LiquidGlassButton label="Open measurement history" onClick={onHistory}/></section>
        </div> : id === 'intelligence' || id === 'scenarios' || id === 'copilot' ?
          <Suspense fallback={<p role="status">Loading mission analysis…</p>}>
            <DecisionWorkspace key={`${id}:${siteId}`} view={id} sites={sites} siteId={siteId} point={point}
              context={decisionContext} onSiteChange={next=>onSelection(next,null)} onPointChange={next=>onSelection(siteId,next)} onContext={onApply}/>
          </Suspense> : id === 'comparison' ? <><Suspense fallback={<p>Loading comparison workspace…</p>}><ComparativeTerrain sites={sites}/></Suspense><details><summary>Archived comparison reports</summary>
          <p className="muted">{comparison ? `${comparison.source}. Values apply to the full raster.` : failure || 'Loading archived terrain statistics…'}</p>
          <div className="mission-table" tabIndex={0}><table><thead><tr><th scope="col">Metric</th>{sites.map(s => <th scope="col" key={s.site_id}>{s.name}<small>{siteCode(s.site_id)}</small></th>)}</tr></thead>
            <tbody>{rows.map(row => <tr key={row.label}><th scope="row">{row.label}</th>{sites.map(s => <td key={s.site_id}>{row.read(s)}</td>)}</tr>)}</tbody></table></div>
        </details></> : id === 'celestial' ? <Suspense fallback={<p role="status">Loading celestial observatory…</p>}>
          <CelestialObservatory {...observer}/>
        </Suspense> : id === 'illumination' ? <Suspense fallback={<p role="status">Loading solar observatory…</p>}>
          <SolarObservatory {...observer}/>
        </Suspense> : id === 'communication' ? <Suspense fallback={<p role="status">Loading Earth observatory…</p>}>
          <EarthObservatory {...observer}/>
        </Suspense> : id === 'operations' && <>
          <Suspense fallback={<p role="status">Loading mission timeline…</p>}>
            <MissionTimeline {...observer} onApply={onApply}/>
          </Suspense>
          <details><summary>Manual mission events</summary>
          <p className="muted">Plan events in hours after landing. These are your entries; no visibility or power windows are calculated.</p>
          <form className="mission-inputs" onSubmit={event => {
            event.preventDefault()
            const form = event.currentTarget
            const data = new FormData(form)
            const name = String(data.get('event')).trim()
            const hours = Number(data.get('hours'))
            if (!name || !Number.isFinite(hours) || hours < 0) return
            setEvents(items => [...items, {id: (items.at(-1)?.id ?? 0) + 1, name, hours, phase: String(data.get('phase'))}])
            setCursor(hours)
            form.reset()
          }}>
            <label>Event<input name="event" required maxLength={80} /></label>
            <label>Phase<select name="phase">{phases.map(phase => <option key={phase}>{phase}</option>)}</select></label>
            <label>Hours after landing<input name="hours" type="number" min="0" step="0.1" required /></label>
            <button className="obs-button obs-primary">Add event</button>
          </form>
          {events.length ? <><label className="mission-scrub">Time after landing <output>{cursor.toFixed(1)} h</output><input type="range" min="0" max={latest} step="0.1" value={Math.min(cursor, latest)} onChange={event => setCursor(Number(event.target.value))} /></label>
            <ol className="mission-events">{[...events].sort((a, b) => a.hours - b.hours).map(item => <li key={item.id} data-reached={item.hours <= cursor}><span>{item.hours.toFixed(1)} h</span><b>{item.name}</b><small>{item.phase}</small><button className="obs-button" onClick={() => setEvents(items => items.filter(e => e.id !== item.id))} aria-label={`Remove ${item.name}`}>Remove</button></li>)}</ol></> : <p className="muted">No events added.</p>}
          </details>
        </>}
      </section>
    </main>
    {historyPanel}
  </div>
}
