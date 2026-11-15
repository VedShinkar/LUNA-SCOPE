import { useState } from 'react'
import { LiquidGlassButton } from '../../components/ui/liquid-glass'
import { measurementCsv, type Measurement } from './survey-tools'
import type { HistoryEdit, HistorySnapshot } from './measurement-storage'
import { ProfilePlot } from './ProfilePlot'
import { siteCode } from './copy'

export function MeasurementHistory({history, update, revisit, close, ready}: {history:HistorySnapshot;update:(change?:HistoryEdit)=>void;revisit:(r:Measurement)=>void;close:()=>void;ready:boolean}) {
  const { records, warning, unsaved } = history
  const [confirm,setConfirm]=useState(false)
  function download(){
    // Excel 2013 needs a UTF-8 signature to recognize characters such as the middle dot.
    const url=URL.createObjectURL(new Blob(['\uFEFF', measurementCsv(records)],{type:'text/csv;charset=utf-8'}))
    const link=document.createElement('a');link.href=url;link.download='luna-scope-measurements.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
  }
  return <aside className="glass-surface measurement-history" aria-label="Measurement History">
    <div className="obs-panel-heading"><h2>Measurement History</h2><LiquidGlassButton label="Close History" onClick={close}/></div>
    <div className="obs-panel-body">
    {warning && <p className="error" role="alert">{warning}</p>}
    {unsaved && <div className="history-actions"><span role="status">Unsaved changes</span><LiquidGlassButton label="Retry Saving" onClick={()=>update()}/></div>}
    <div className="history-actions"><LiquidGlassButton label="Export CSV" disabled={!records.length} onClick={download}/><LiquidGlassButton label="Clear History" disabled={!records.length&&!warning} onClick={()=>setConfirm(true)}/></div>
    {confirm&&<div role="alert"><p>Clear all measurements saved in this browser?</p><LiquidGlassButton label="Clear All Measurements" onClick={()=>{update({type:'clear'});setConfirm(false)}}/><LiquidGlassButton label="Cancel" onClick={()=>setConfirm(false)}/></div>}
    {!records.length&&<p className="muted">No saved measurements.</p>}
    {records.map(r=><details key={r.id}><summary>{r.name || r.kind} · {r.siteId ? siteCode(r.siteId) : 'Global / polar survey'}</summary>
      <div className="muted">{r.kind} · {r.source}<br/>{new Date(r.timestamp).toLocaleString()}</div>
      {r.siteName && <p>{r.siteName}</p>}
      {r.provenance?.sourceFile && <p className="muted">{r.provenance.sourceFile}{r.provenance.resolution && ` · ${r.provenance.resolution.join(' × ')} m/px`}</p>}
      {r.coordinates.map((p,i)=><p className="obs-coordinates" key={i}>{p.latitude.toFixed(5)}°, {p.longitude.toFixed(5)}°</p>)}
      {r.kind==='Elevation profile'?<ProfilePlot profile={r.values}/>:<p>Elevation: {r.values.elevation_m==null?'Unavailable':`${r.values.elevation_m} m`} · Slope: {r.values.slope_deg==null?'Unavailable':`${r.values.slope_deg}°`}</p>}
      <label>Measurement name<input value={r.name} maxLength={100} onChange={e=>update({type:'rename',id:r.id,name:e.target.value})}/></label>
      <div className="history-actions"><LiquidGlassButton label="Revisit Measurement" disabled={r.siteId!==null&&!ready} onClick={()=>revisit(r)}/><LiquidGlassButton label="Delete Measurement" onClick={()=>update({type:'delete',id:r.id})}/></div>
    </details>)}
    </div>
  </aside>
}
