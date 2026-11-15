import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { LunarSite } from '../../services/lunar'
import { demonstration } from '../../services/mission'
import { askMissionCopilot, assessMission, compareScenarios, type CopilotResult, type DecisionAction, type DecisionContext, type DecisionRequest, type DecisionResult, type ScenarioComparison } from '../../services/mission-intelligence'
import type { MapPoint } from '../../services/terrain'

type View = 'intelligence' | 'scenarios' | 'copilot'
const actions:Record<DecisionAction,string> = {
  assessment:'Explain site assessment', terrain:'Explain terrain evidence', solar:'Explain solar illumination',
  earth:'Explain Earth visibility', timeline:'Explain operational windows', compare_sites:'Compare landing sites',
}
const display = (value:string) => value.replaceAll('_',' ').toLowerCase().replace(/^./,first=>first.toUpperCase())
const fmt = (value:number|null|undefined, digits=3) => value == null ? 'Unavailable' : value.toLocaleString(undefined,{maximumFractionDigits:digits})
const inputTime = (time:string) => time.slice(0,19)
const utc = (value:FormDataEntryValue|null) => new Date(`${String(value)}Z`).toISOString()

function Evidence({title,value}:{title:string;value:unknown}) {
  if (value == null) return null
  return <details className="decision-evidence"><summary>{title}</summary><pre>{JSON.stringify(value,null,2)}</pre></details>
}

function Assessment({value}:{value:DecisionResult}) {
  const {assessment, observer, effective_profile:profile, timeline} = value
  return <section aria-label="Preliminary assessment" className="decision-result">
    <h2>Preliminary assessment</h2>
    <dl className="mission-totals">
      <div><dt>Evidence status</dt><dd>{display(assessment.overall_data_status)}</dd></div>
      <div><dt>Preliminary score</dt><dd>{fmt(assessment.preliminary_score)} / 1</dd></div>
      <div><dt>Operational window requirement</dt><dd>{display(value.operational_screen)}</dd></div>
      <div><dt>Native observer</dt><dd>Row {observer.source_pixel_row}, column {observer.source_pixel_column} · {fmt(observer.elevation_m)} m</dd></div>
    </dl>
    <p>{profile.name} · Earth {display(profile.earth_requirement)} · antenna mask {profile.minimum_antenna_elevation_deg}° · minimum window {fmt(profile.minimum_window_s/3600)} h</p>
    <p>Projected observer E {fmt(observer.easting_m)}, N {fmt(observer.northing_m)} m · <a href={observer.source_url}>{observer.source_file}</a></p>
    <div className="mission-table" tabIndex={0}><table>
      <thead><tr><th scope="col">Criterion</th><th scope="col">Value</th><th scope="col">Weight</th><th scope="col">Contribution</th><th scope="col">Evidence</th></tr></thead>
      <tbody>{assessment.criteria.map(criterion=><tr key={criterion.criterion}>
        <th scope="row">{display(criterion.criterion)}</th><td>{fmt(criterion.value)} {criterion.value!=null&&criterion.units}</td>
        <td>{criterion.weight}</td><td>{fmt(value.contributions[criterion.criterion])}</td><td>{display(criterion.data_status)}</td>
      </tr>)}</tbody>
    </table></div>
    {assessment.missing_criteria.length>0&&<p>Unresolved or unavailable criteria · {assessment.missing_criteria.map(display).join(', ')}</p>}
    {timeline&&<><h3>Operational timeline evidence</h3><p>{timeline.start_utc} to {timeline.end_utc}</p>
      <dl className="mission-totals">{Object.entries(timeline.summary.duration_s).map(([key,seconds])=><div key={key}><dt>{display(key)}</dt><dd>{fmt(seconds/3600)} h</dd></div>)}</dl>
      <p>Longest favourable window {fmt(timeline.summary.longest_favourable_s/3600)} h · {timeline.summary.transition_count} mission transitions</p>
    </>}
    <h3>Assumptions and warnings</h3>
    <ul>{[...new Set([...value.limitations,...assessment.quality_notes,...assessment.criteria.flatMap(item=>item.notes)])].map(note=><li key={note}>{note}</li>)}</ul>
    <Evidence title="Configured weights and thresholds" value={value.request}/>
    <Evidence title="Terrain provenance and quality" value={assessment.terrain}/>
    <Evidence title="Solar duration and provenance" value={assessment.illumination}/>
    <Evidence title="Earth visibility duration and provenance" value={assessment.communication}/>
    <Evidence title="Timeline provenance and classification rules" value={timeline}/>
    <Evidence title="Observations at the evaluation instant" value={value.snapshot}/>
  </section>
}

function Comparison({value}:{value:ScenarioComparison}) {
  return <section aria-label="Scenario results" className="decision-result">
    <h2>Scenario results</h2>
    <ul>{value.explanations.map(note=><li key={note}>{note}</li>)}</ul>
    {value.ranked_groups.length>0&&<ol>{value.ranked_groups.map(group=><li key={group.join('|')}>{group.join(' · ')}</li>)}</ol>}
    <div className="mission-table" tabIndex={0}><table><thead><tr>
      <th scope="col">Scenario</th><th scope="col">Antenna mask</th><th scope="col">Slope</th><th scope="col">Solar fraction</th>
      <th scope="col">Earth fraction</th><th scope="col">Window requirement</th><th scope="col">Score / 1</th>
    </tr></thead><tbody>{value.scenarios.map(({name,result,unavailable})=>{
      const measured = (criterion:string) => result?.assessment.criteria.find(item=>item.criterion===criterion)?.value
      return <tr key={name}><th scope="row">{name}</th>{result ? <>
        <td>{result.effective_profile.minimum_antenna_elevation_deg}°</td><td>{fmt(measured('terrain_slope'))}</td>
        <td>{fmt(measured('illumination_fraction'))}</td><td>{fmt(measured('communication_visibility_fraction'))}</td>
        <td>{display(result.operational_screen)}</td><td>{fmt(result.assessment.preliminary_score)}</td>
      </> : <td colSpan={6}>{unavailable}</td>}</tr>
    })}</tbody></table></div>
    {value.scenarios.map(({name,result})=>result&&<details className="decision-evidence" key={name}><summary>{name} evidence</summary><Assessment value={result}/></details>)}
    {value.differences.map(item=><details className="decision-evidence" key={item.scenario}>
      <summary>{item.scenario} compared with {item.baseline}</summary>
      <p>{item.changes.length ? item.changes.join(' ') : 'Same submitted assumptions.'}</p>
      {item.score_delta!==null&&<p>Preliminary score change {fmt(item.score_delta)}</p>}
    </details>)}
  </section>
}

function CopilotEvidence({reply}:{reply:CopilotResult}) {
  const missing = [...new Set([...reply.missing_inputs,...(reply.response?.missing_inputs??[])])]
  return <div>
    {missing.length>0&&<p>Missing evidence · {missing.map(display).join(', ')}</p>}
    {reply.response?.limitations?.map(note=><p key={note}>{note}</p>)}
    {reply.assessment&&<Assessment value={reply.assessment}/>}
    {reply.comparison&&<Comparison value={reply.comparison}/>}
    {!reply.assessment&&!reply.comparison&&reply.response&&<Evidence title="Scientific evidence and provenance" value={reply.response.evidence??reply.response}/>}
    {reply.response?.copilot_note&&<p className="muted">{reply.response.copilot_note}</p>}
    <Evidence title="Request context" value={reply.context}/>
  </div>
}

export default function DecisionWorkspace({view,siteId,point,sites,context,onSiteChange,onContext,onPointChange}:{
  view:View;siteId:string;point:MapPoint|null;sites:LunarSite[];context:DecisionContext|null
  onSiteChange:(site:string)=>void;onContext:(context:DecisionContext)=>void
  onPointChange:(point:MapPoint|null)=>void
}) {
  const [mode,setMode] = useState(() => {
    if (context?.utc) return 'instant'
    return context && !context.start_utc ? 'none' : 'range'
  })
  const [pending,setPending] = useState(false)
  const [error,setError] = useState('')
  const [assessment,setAssessment] = useState<DecisionResult>()
  const [comparison,setComparison] = useState<ScenarioComparison>()
  const [replies,setReplies] = useState<CopilotResult[]>([])
  const active = useRef<AbortController|null>(null)
  const [now] = useState(()=>Math.floor(Date.now()/3600000)*3600000)
  const activeProfile = context?.profile ?? demonstration
  const start = context?.start_utc ?? new Date(now).toISOString()
  const end = context?.end_utc ?? new Date(now+86400000).toISOString()
  const onEdit = () => {
    active.current?.abort()
    setPending(false)
    setAssessment(undefined)
    setComparison(undefined)
    setError('')
  }
  useEffect(()=>()=>active.current?.abort(),[])

  async function run(event:FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onEdit()
    const data = new FormData(event.currentTarget)
    const controller = new AbortController()
    active.current = controller
    setPending(true)
    try {
      const profile = {...activeProfile,name:String(data.get('profile')),
        solar_required:data.has('solar_required'),prefer_full_disc:data.has('prefer_full_disc'),
        earth_requirement:String(data.get('earth_requirement')) as typeof activeProfile.earth_requirement,
        minimum_window_s:Math.round(Number(data.get('minimum_hours'))*3600)}
      const east = String(data.get('easting')).trim()
      const north = String(data.get('northing')).trim()
      if (Boolean(east)!==Boolean(north)) throw new Error('Enter both projected observer coordinates or leave both blank.')
      const request:DecisionRequest = {
        site_id:siteId,point:east && north ? {easting_m:Number(east),northing_m:Number(north)}:null,profile,
        equipment:{name:String(data.get('equipment')),minimum_antenna_elevation_deg:Number(data.get('mask'))},
        step_seconds:Number(data.get('step')),
      }
      if (mode==='range') {
        request.start_utc=utc(data.get('start_utc'))
        request.end_utc=utc(data.get('end_utc'))
      } else if (mode==='instant') request.utc=utc(data.get('utc'))
      if (view==='intelligence') {
        const result=await assessMission(request,controller.signal)
        if (!controller.signal.aborted) setAssessment(result)
      } else if (view==='scenarios') {
        const selected=sites.filter(site=>data.getAll('comparison_site').includes(site.site_id))
        const scenarios=selected.map(site=>({name:site.name,site_id:site.site_id,
          point:site.site_id===siteId ? request.point:null,profile,equipment:request.equipment}))
        if(data.has('alternate')) scenarios.push({name:'Alternate equipment · active site',site_id:siteId,point:request.point,
          profile,equipment:{name:'Alternate configuration',minimum_antenna_elevation_deg:Number(data.get('alternate_mask'))}})
        if (scenarios.length<2) throw new Error('Select at least two scenarios.')
        const result=await compareScenarios({step_seconds:request.step_seconds,utc:request.utc,start_utc:request.start_utc,end_utc:request.end_utc,scenarios},controller.signal)
        if (!controller.signal.aborted) setComparison(result)
      } else {
        const result=await askMissionCopilot({...request,action:data.get('action') as DecisionAction},controller.signal)
        if (!controller.signal.aborted) setReplies(items=>[...items.slice(-7),result])
      }
      if (!controller.signal.aborted) {
        onContext({utc:request.utc,start_utc:request.start_utc,end_utc:request.end_utc,
          step_seconds:request.step_seconds,profile,equipment:request.equipment})
        onPointChange(request.point ? {easting:request.point.easting_m,northing:request.point.northing_m}:null)
      }
    } catch (issue) {
      if (!controller.signal.aborted) setError(issue instanceof Error?issue.message:'Mission service unavailable.')
    } finally {
      if (active.current===controller && !controller.signal.aborted) setPending(false)
    }
  }

  return <div className="mission-timeline decision-workspace">
    <form onSubmit={run} onChange={onEdit}>
      <fieldset><legend>Native observer</legend><div className="mission-fields">
        <label>Landing site<select name="site_id" aria-label="Landing site" value={siteId} onChange={event=>onSiteChange(event.target.value)}>{sites.map(site=><option key={site.site_id} value={site.site_id}>{site.name}</option>)}</select></label>
        <label>Projected easting (m)<input name="easting" type="number" step="any" defaultValue={point?.easting}/></label>
        <label>Projected northing (m)<input name="northing" type="number" step="any" defaultValue={point?.northing}/></label>
      </div><p className="muted">Blank coordinates use the native raster centre. The backend resolves elevation from LOLA.</p></fieldset>
      <fieldset><legend>Evaluation time</legend><div className="mission-fields">
        <label>Time selection<select name="time_selection" aria-label="Time selection" value={mode} onChange={event=>setMode(event.target.value)}><option value="range">UTC range</option><option value="instant">UTC instant</option><option value="none">Terrain only</option></select></label>
        {mode==='instant'&&<label>Evaluation UTC<input name="utc" type="datetime-local" step="1" required defaultValue={inputTime(context?.utc ?? start)}/></label>}
        {mode==='range'&&<><label>Start UTC<input name="start_utc" type="datetime-local" step="1" required defaultValue={inputTime(start)}/></label>
          <label>End UTC<input name="end_utc" type="datetime-local" step="1" required defaultValue={inputTime(end)}/></label></>}
        <label>Sampling increment (s)<input name="step" type="number" min="60" max="604800" step="1" required defaultValue={context?.step_seconds ?? 3600}/></label>
      </div></fieldset>
      <fieldset><legend>Mission and equipment assumptions</legend><div className="mission-fields">
        <label>Profile name<input name="profile" required maxLength={64} defaultValue={activeProfile.name}/></label>
        <label>Earth criterion<select name="earth_requirement" defaultValue={activeProfile.earth_requirement}>
          <option value="centre">Earth centre</option><option value="any_disc">Any visible disc</option><option value="full_disc">Full visible disc</option>
        </select></label>
        <label>Minimum favourable hours<input name="minimum_hours" type="number" min="0" max="2160" step="any" required defaultValue={activeProfile.minimum_window_s/3600}/></label>
        <label>Equipment configuration<input name="equipment" required maxLength={64} defaultValue={context?.equipment?.name ?? 'Configured antenna'}/></label>
        <label>Antenna elevation mask (°)<input name="mask" type="number" min="0" max="90" step="any" required defaultValue={context?.equipment?.minimum_antenna_elevation_deg ?? activeProfile.minimum_antenna_elevation_deg}/></label>
        <label className="mission-check"><input type="checkbox" name="solar_required" defaultChecked={activeProfile.solar_required}/>Require direct sunlight</label>
        <label className="mission-check"><input type="checkbox" name="prefer_full_disc" defaultChecked={activeProfile.prefer_full_disc}/>Prefer full Earth disc</label>
      </div></fieldset>
      {view==='scenarios'&&<fieldset><legend>Scenarios</legend><div className="mission-fields">
        {sites.map(site=><label className="mission-check" key={site.site_id}><input type="checkbox" name="comparison_site" value={site.site_id} defaultChecked/>{site.name}</label>)}
        <label className="mission-check"><input type="checkbox" name="alternate"/>Include alternate equipment at the active site</label>
        <label>Alternate antenna mask (°)<input name="alternate_mask" type="number" min="0" max="90" step="any" defaultValue={10}/></label>
      </div></fieldset>}
      {view==='copilot'&&<fieldset><legend>Copilot question</legend><p>Choose a question to retrieve evidence for the current site and assumptions.</p>
        <div className="mission-fields"><label>Question<select name="action" aria-label="Question">{Object.entries(actions).map(([action,label])=><option key={action} value={action}>{label}</option>)}</select></label></div>
      </fieldset>}
      <div className="mission-actions"><button className="obs-button obs-primary" disabled={pending||!siteId}>
        {view==='intelligence'?'Run assessment':view==='scenarios'?'Compare scenarios':'Ask Copilot'}
      </button></div>
    </form>
    {pending&&<p role="status">Retrieving native terrain and mission evidence…</p>}
    {error&&<p role="alert" className="error">{error}</p>}
    {!pending&&!error&&!assessment&&!comparison&&replies.length===0&&<p className="muted">No result for this selection yet.</p>}
    {assessment&&<Assessment value={assessment}/>}
    {comparison&&<Comparison value={comparison}/>}
    {replies.map((reply,index)=><article className="decision-result" key={index}><h2>{actions[reply.action]}</h2><CopilotEvidence reply={reply}/></article>)}
  </div>
}
