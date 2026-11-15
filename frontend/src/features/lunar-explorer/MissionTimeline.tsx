import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { ScienceSelection } from './WorkspaceNavigation'
import type { LunarSite } from '../../services/lunar'
import { demonstration, getMissionComparison, getMissionTimeline, validateMissionProfile, type MissionRequest, type MissionTimeline as Timeline } from '../../services/mission'
import { conditionLabel, epoch, hours, intervalIndex, missionColors, shownUtc, trackNames, trackOrder } from '../../visualization/mission-display'
import MissionReport, { ProfileAssumptions } from './MissionReport'
import { MissionTimelineChart, type TimeBounds } from './MissionTimelineChart'

const storageKey = 'luna-scope.mission-profile.v1'
const states = Object.keys(missionColors) as (keyof typeof missionColors)[]
const utcInput = (time: string) => new Date(time).toISOString().slice(0, 19)
const steps = [[60,'1 minute'],[600,'10 minutes'],[1800,'30 minutes'],[3600,'1 hour'],[21600,'6 hours'],[43200,'12 hours'],[86400,'1 day'],[604800,'7 days']] as const
const timestamp = (value: string, label: string) => {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value) || !Number.isFinite(epoch(value+'Z'))) throw new Error(`Enter a valid ${label} in UTC.`)
  return new Date(value+'Z').toISOString()
}

export default function MissionTimeline({ sites, initialSite, initialPoint, onSelection, onApply }: {
  sites:LunarSite[]; onApply:(request:MissionRequest)=>void
} & ScienceSelection) {
  const [site,setSite] = useState(sites.some(item=>item.site_id===initialSite) ? initialSite : sites[0]?.site_id ?? '')
  const [defaults,setDefaults] = useState<MissionRequest>(()=>{
    const now = Math.floor(Date.now()/60000)*60000
    return {start_utc:new Date(now).toISOString(),end_utc:new Date(now+86400000).toISOString(),step_seconds:3600,profile:demonstration,refine_transitions:true}
  })
  const [formKey,setFormKey] = useState(0)
  const form = useRef<HTMLFormElement>(null)
  const active = useRef<AbortController|null>(null)
  const [pending,setPending] = useState('')
  const [message,setMessage] = useState('')
  const [error,setError] = useState('')
  const [dirty,setDirty] = useState(false)
  const [timelines,setTimelines] = useState<Timeline[]>([])
  const [selected,setSelected] = useState('')
  const [cursor,setCursor] = useState(0)
  const [zoom,setZoom] = useState<TimeBounds>()
  const names = Object.fromEntries(sites.map(item=>[item.site_id,item.name]))
  const result = timelines.find(item=>item.site_id===selected)??timelines[0]
  const index = result ? intervalIndex(result,cursor) : -1
  const row = result?.intervals[index]
  const brackets = row ? result?.transitions.filter(event=>epoch(event.start_utc)<epoch(row.end_utc)&&epoch(event.end_utc)>epoch(row.start_utc)) : []
  const first = result?.samples[index]
  const last = result?.samples[index+1]
  const bounds = result && (zoom??[epoch(result.start_utc),epoch(result.end_utc)])
  const matched = first && epoch(first.utc)===cursor ? first : last && epoch(last.utc)===cursor ? last : undefined

  useEffect(()=>()=>active.current?.abort(),[])

  function abort() {
    active.current?.abort()
    active.current = null
    setPending('')
  }
  function invalidate() {
    setTimelines([])
    setZoom(undefined)
    setMessage('')
    setError('')
    abort()
  }
  function readConfig(): MissionRequest {
    if (!form.current?.reportValidity()) throw new Error('Check the time range and mission assumptions.')
    const data = new FormData(form.current)
    const start = timestamp(String(data.get('start_utc')),'start time')
    const end = timestamp(String(data.get('end_utc')),'end time')
    if (epoch(end)<=epoch(start)) throw new Error('End UTC must be later than start UTC.')
    const name = String(data.get('name')).trim()
    if (!name) throw new Error('Enter a mission profile name.')
    return {start_utc:start,end_utc:end,step_seconds:Number(data.get('step')),refine_transitions:data.has('refine'),
      profile:{version:'1',name,solar_required:data.has('solar'),
        earth_requirement:data.get('earth') as MissionRequest['profile']['earth_requirement'],prefer_full_disc:data.has('prefer'),
        minimum_antenna_elevation_deg:Number(data.get('antenna')),minimum_window_s:Math.round(Number(data.get('duration'))*3600)}}
  }
  async function perform(action:'site'|'compare'|'save'|'load') {
    abort()
    setError('')
    setMessage('')
    const controller = new AbortController()
    active.current = controller
    try {
      if (action==='load') {
        const stored = localStorage.getItem(storageKey)
        if (!stored) throw new Error('This browser has no saved mission profile.')
        const saved = JSON.parse(stored) as MissionRequest
        if (!steps.some(([step])=>step===saved.step_seconds) || typeof saved.refine_transitions!=='boolean' ||
            !Number.isFinite(epoch(saved.start_utc)) || !(epoch(saved.end_utc)>epoch(saved.start_utc))) throw new Error('The saved analysis settings are invalid.')
        setPending('Validating saved mission profile…')
        const profile = await validateMissionProfile(saved.profile,controller.signal)
        if (controller.signal.aborted) return
        setDefaults({...saved,profile})
        setFormKey(key=>key+1)
        setDirty(true)
        setMessage('Saved profile loaded. Apply it by running an analysis.')
        return
      }
      const config = readConfig()
      if (action==='save') {
        setPending('Validating mission profile…')
        const profile = await validateMissionProfile(config.profile,controller.signal)
        if (controller.signal.aborted) return
        localStorage.setItem(storageKey,JSON.stringify({...config,profile}))
        setMessage('Mission profile and UTC settings saved in this browser.')
        return
      }
      const data = new FormData(form.current!)
      const selection = String(data.get('site'))
      const east = String(data.get('easting')).trim(), north = String(data.get('northing')).trim()
      if (Boolean(east)!==Boolean(north)) throw new Error('Enter both projected coordinates, or leave both blank to use the raster centre.')
      const point = east && north ? {easting:Number(east),northing:Number(north)} : null
      setTimelines([])
      setZoom(undefined)
      setPending(action==='compare'?'Calculating synchronized evidence for three native observers…':'Calculating solar and Earth evidence for the native observer…')
      const next = action==='compare'
        ? (await getMissionComparison(config,selection,point,controller.signal)).timelines
        : [await getMissionTimeline(config,selection,point,controller.signal)]
      if (controller.signal.aborted) return
      onSelection(selection, point)
      onApply(config)
      setTimelines(next)
      setSelected(next.find(item=>item.site_id===selection)?.site_id??next[0].site_id)
      setCursor(epoch(next[0].start_utc))
      setDirty(false)
    } catch (problem) {
      if (!controller.signal.aborted) setError(problem instanceof Error ? problem.message : 'Mission analysis could not be completed.')
    } finally {
      if (active.current===controller) {
        active.current = null
        setPending('')
      }
    }
  }
  function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement|null
    void perform(submitter?.value==='compare'?'compare':'site')
  }
  function inspect(time:number, target=result) {
    if (!target) return
    setSelected(target.site_id)
    setCursor(time)
    if (zoom && (time<zoom[0]||time>zoom[1])) setZoom(undefined)
  }
  function step(direction:number) {
    if (!result) return
    const target = direction<0 ? [...result.samples].reverse().find(sample=>epoch(sample.utc)<cursor) : result.samples.find(sample=>epoch(sample.utc)>cursor)
    if (target) inspect(epoch(target.utc))
  }
  const sourceTimes = (label:string, kind:'solar_source_utc'|'earth_source_utc') =>
    <p>{label}: {matched ? (matched[kind]?shownUtc(matched[kind]):'Unavailable') : [first,last].map(sample=>sample?.[kind]?shownUtc(sample[kind]):'Unavailable').join(' to ')}</p>

  return <div className="mission-timeline">
    <p className="muted">Find periods when sunlight and Earth visibility satisfy the mission assumptions at a selected native terrain pixel. The timeline shows geometric and terrain evidence for the sampled period.</p>
    <form key={formKey} ref={form} onSubmit={submit} onChange={()=>{
      if (active.current) abort()
      setDirty(true)
      setMessage('')
    }}>
      <fieldset><legend>Observer and UTC range</legend><div className="mission-fields">
        <label>Observer site<select name="site" value={site} onChange={event=>{setSite(event.target.value);invalidate();onSelection(event.target.value,null)}}>
          {sites.map(item=><option key={item.site_id} value={item.site_id}>{item.name}</option>)}
        </select></label>
        <label>Start (UTC)<input name="start_utc" type="datetime-local" step="1" required defaultValue={utcInput(defaults.start_utc)}/></label>
        <label>End (UTC)<input name="end_utc" type="datetime-local" step="1" required defaultValue={utcInput(defaults.end_utc)}/></label>
        <label>Sampling interval<select name="step" defaultValue={defaults.step_seconds}>{steps.map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label>
        <label>Projected easting (m)<input name="easting" type="number" step="any" key={site+'-e'} defaultValue={initialPoint?.easting} onChange={invalidate}/></label>
        <label>Projected northing (m)<input name="northing" type="number" step="any" key={site+'-n'} defaultValue={initialPoint?.northing} onChange={invalidate}/></label>
        <label className="mission-check"><input type="checkbox" name="refine" defaultChecked={defaults.refine_transitions}/> Refine detected transition brackets</label>
      </div><p className="muted">Leave coordinates blank to use the native raster centre. In comparison, coordinates apply only to the selected site. Maximum 241 nominal samples.</p></fieldset>
      <fieldset><legend>Mission profile</legend><div className="mission-fields">
        <label>Profile name<input name="name" maxLength={64} required defaultValue={defaults.profile.name}/></label>
        <label>Required Earth visibility<select name="earth" defaultValue={defaults.profile.earth_requirement}>
          <option value="centre">Earth centre</option><option value="any_disc">Any part of Earth disc</option><option value="full_disc">Entire Earth disc</option>
        </select></label>
        <label>Minimum antenna elevation (°)<input name="antenna" type="number" min="0" max="90" step="any" required defaultValue={defaults.profile.minimum_antenna_elevation_deg}/></label>
        <label>Minimum continuous window (h)<input name="duration" type="number" min="0" max="2160" step="any" required defaultValue={defaults.profile.minimum_window_s/3600}/></label>
        <label className="mission-check"><input type="checkbox" name="solar" defaultChecked={defaults.profile.solar_required}/> Require direct sunlight at solar centre</label>
        <label className="mission-check"><input type="checkbox" name="prefer" defaultChecked={defaults.profile.prefer_full_disc}/> Flag intervals without confirmed full Earth disc</label>
      </div><p className="muted">The default profile is a demonstration. Minimum duration qualifies continuous favourable windows after classification.</p></fieldset>
      <div className="mission-actions">
        <button className="obs-button obs-primary" value="site" disabled={!!pending||!site}>Analyse site</button>
        <button className="obs-button" value="compare" disabled={!!pending||!site}>Compare three sites</button>
        <button className="obs-button" type="button" disabled={!!pending} onClick={()=>void perform('save')}>Save profile</button>
        <button className="obs-button" type="button" disabled={!!pending} onClick={()=>void perform('load')}>Load profile</button>
        {pending&&<button className="obs-button" type="button" onClick={()=>{abort();setMessage('Stopped waiting for the current request.')}}>Stop waiting</button>}
      </div>
    </form>
    {pending&&<p role="status">{pending}</p>}
    {error&&<p role="alert">{error}</p>}
    {message&&<p role="status">{message}</p>}
    {result&&bounds&&row&&<>
      <section className="mission-results" aria-label="Mission results">
        <div className="mission-heading"><h2>{timelines.length>1?'Matched site comparison':names[result.site_id]??result.site_id}</h2><MissionReport timelines={timelines} names={names}/></div>
        <ProfileAssumptions profile={result.profile} step={result.step_seconds}/>
        {dirty&&<p role="status">These results use the applied settings shown above. Run a new analysis to apply your edits.</p>}
        <ul className="mission-legend">{states.map(state=><li key={state}><i data-tone={state} style={{backgroundColor:missionColors[state]}}/>{conditionLabel(state)}</li>)}</ul>
        <div className={timelines.length>1?'mission-site-grid':''}>{timelines.map(timeline=><section className="mission-site-card" key={timeline.site_id}>
          {timelines.length>1&&<button type="button" className="obs-button" aria-pressed={timeline.site_id===selected} onClick={()=>inspect(cursor,timeline)}>{names[timeline.site_id]??timeline.site_id}</button>}
          <p className="muted">{timeline.site_id} · {timeline.observer.latitude_deg.toFixed(6)}°, {timeline.observer.longitude_deg_east.toFixed(6)}° E · {timeline.observer.elevation_m.toFixed(2)} m</p>
          <MissionTimelineChart timeline={timeline} bounds={bounds} cursor={cursor} onPick={time=>inspect(time,timeline)} compact={timelines.length>1}/>
          <dl className="mission-totals">{states.map(state=><div key={state}><dt>{conditionLabel(state)}</dt><dd>{hours(timeline.summary.duration_s[state])}</dd></div>)}</dl>
          <p>{hours(timeline.summary.qualifying_favourable_s)} meets the minimum · longest favourable {hours(timeline.summary.longest_favourable_s)} · longest unfavourable {hours(timeline.summary.longest_unfavourable_s)}</p>
          <p className="muted">{timeline.nominal_sample_count} nominal + {timeline.refinement_sample_count} refinement samples · {timeline.summary.transition_count} combined mission transitions</p>
        </section>)}</div>
        <p className="muted">Hatched segments indicate unresolved or invalid evidence. Matching samples can miss changes between their timestamps.</p>
      </section>
      <section className="mission-inspector" aria-label="Timeline inspection">
        <h2>Inspect timeline · {names[result.site_id]??result.site_id}</h2>
        <label className="mission-scrub">Time cursor <output>{shownUtc(new Date(cursor).toISOString())}</output>
          <input type="range" min={bounds[0]} max={bounds[1]} step="any" value={Math.max(bounds[0],Math.min(cursor,bounds[1]))}
            aria-valuetext={shownUtc(new Date(cursor).toISOString())} onChange={event=>inspect(Number(event.target.value))}/>
        </label>
        <div className="mission-actions">
          <button className="obs-button" onClick={()=>step(-1)} disabled={cursor<=epoch(result.start_utc)}>Previous sample</button>
          <button className="obs-button" onClick={()=>step(1)} disabled={cursor>=epoch(result.end_utc)}>Next sample</button>
          <button className="obs-button" onClick={()=>setZoom([epoch(row.start_utc),epoch(row.end_utc)])}>Zoom to interval</button>
          <button className="obs-button" onClick={()=>setZoom(undefined)} disabled={!zoom}>Reset zoom</button>
        </div>
        {result.transitions.length>0&&<label className="mission-jump">Transition brackets
          <select value="" onChange={event=>{
            if (!event.target.value) return
            const transition = result.transitions[Number(event.target.value)]
            const start = epoch(transition.start_utc), end = epoch(transition.end_utc)
            inspect(start+(end-start)/2)
            setZoom([start,end])
          }}><option value="">Select a bracket to inspect</option>
            {result.transitions.map((event,i)=><option value={i} key={i}>{shownUtc(event.start_utc)} · {trackNames[event.track]} · {conditionLabel(event.from_state)} → {conditionLabel(event.to_state)}</option>)}</select>
        </label>}
        <p>{shownUtc(row.start_utc)} to {shownUtc(row.end_utc)} · {hours(row.duration_s)}{row.requires_sampling?' · Further sampling may narrow this bracket.':''}</p>
        {!!brackets?.length&&<ul>{brackets.map(event=><li key={event.track+event.start_utc}>
          {trackNames[event.track]}: {conditionLabel(event.from_state)} → {conditionLabel(event.to_state)} · bracket {shownUtc(event.start_utc)} to {shownUtc(event.end_utc)}
        </li>)}</ul>}
        <dl className="mission-totals">{trackOrder.map(track=><div key={track}><dt>{trackNames[track]}</dt><dd>{conditionLabel(row.tracks[track])}</dd></div>)}</dl>
        {matched&&<p>At this sample: {trackOrder.map(track=>`${trackNames[track]}: ${conditionLabel(matched.tracks[track])}`).join(' · ')}</p>}
        <p>Native observer: {result.observer.easting_m.toFixed(2)} m E, {result.observer.northing_m.toFixed(2)} m N · {result.observer.latitude_deg.toFixed(6)}°, {result.observer.longitude_deg_east.toFixed(6)}° E · {result.observer.elevation_m.toFixed(2)} m</p>
        {sourceTimes('Solar calculation UTC','solar_source_utc')}{sourceTimes('Earth calculation UTC','earth_source_utc')}
        <p>Evidence: {[...new Set([...(matched?[matched]:[first,last]).flatMap(sample=>sample ? [sample.solar_reason,sample.earth_reason,sample.disc_evidence,...sample.flags] : []),...result.quality_flags])].filter((flag):flag is string=>!!flag).map(conditionLabel).join(' · ')||'No quality flags reported.'}</p>
        <details><summary>Favourable windows</summary>
          {result.summary.favourable_windows.length ? <ul>{result.summary.favourable_windows.map(window=><li key={window.start_utc}>
            {shownUtc(window.start_utc)} to {shownUtc(window.end_utc)} · {hours(window.duration_s)} · {window.meets_minimum?'Meets minimum':'Below minimum'}
          </li>)}</ul> : <p>No confirmed favourable interval in the sampled period.</p>}
        </details>
        <details><summary>Classification and data sources</summary><ul>{result.classification_rules.map(rule=><li key={rule}>{rule}</li>)}</ul>
          <p><a href={result.terrain.source_url}>{result.terrain.file}</a> · {result.terrain.resolution_m.join(' × ')} m · {result.celestial.source}</p>
          <p>{result.solar_engine.method.name} · {result.earth_engine.method.name}</p>
        </details>
      </section>
    </>}
  </div>
}
