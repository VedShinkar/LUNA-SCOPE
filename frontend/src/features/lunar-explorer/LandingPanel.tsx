import { CircleAlert, MapPinned } from 'lucide-react'
import { siteName } from './copy'

export function LandingPanel({ threshold, onChange, roughness, onRoughness, siteId }: { threshold: number; onChange: (value: number) => void; roughness: number; onRoughness: (value:number)=>void; siteId: string }) {
  return <>
    <div className="caution"><CircleAlert size={16} /><div><strong>Preliminary terrain screening</strong><p>Terrain screening does not establish landing safety.</p></div></div>
    <div className="control-group">
      <label htmlFor="slope-limit">Maximum slope <output>{threshold}°</output></label>
      <input id="slope-limit" type="range" min="0" max="90" step="1" value={threshold}
        onChange={event => onChange(Number(event.target.value))} />
      <label htmlFor="roughness-limit">Maximum roughness (15 m) <output>{roughness} m</output></label>
      <input id="roughness-limit" type="range" min="0" max="10" step="0.1" value={roughness} onChange={event => onRoughness(Number(event.target.value))}/>
      <p className="muted">User thresholds are mission assumptions. NoData is excluded from the screening.</p>
    </div>
    <div className="candidate">
      <h2>Candidate regions</h2>
      <div className="candidate-empty"><MapPinned size={18} /><p>Candidate boundaries and statistics are unavailable for {siteName(siteId)}.</p></div>
    </div>
  </>
}
