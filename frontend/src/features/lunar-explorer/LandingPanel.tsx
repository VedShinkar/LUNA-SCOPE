import { CircleAlert, MapPinned } from 'lucide-react'

export function LandingPanel({ threshold, onChange }: { threshold: number; onChange: (value: number) => void }) {
  return <>
    <div className="caution"><CircleAlert size={16} /><div><strong>Preliminary terrain suitability</strong><p>Terrain alone cannot establish landing safety.</p></div></div>
    <div className="control-group">
      <label htmlFor="slope-limit">Maximum slope <output>{threshold}°</output></label>
      <input id="slope-limit" type="range" min="0" max="90" step="1" value={threshold}
        onChange={event => onChange(Number(event.target.value))} />
      <p className="muted">Mission assumption for the slope suitability layer.</p>
    </div>
    <div className="candidate">
      <h2>Candidate regions</h2>
      <div className="candidate-empty"><MapPinned size={18} /><p>Candidate regions are unavailable. Site04 has no generated candidate boundaries or statistics.</p></div>
    </div>
  </>
}
