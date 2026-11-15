import { useRef, useState } from 'react'
import { LiquidGlassButton } from '../../components/ui/liquid-glass'
import type { MissionProfile, MissionTimeline } from '../../services/mission'
import { conditionLabel, hours, missionCsv, shownUtc, trackNames } from '../../visualization/mission-display'
import { MissionTimelineChart } from './MissionTimelineChart'
import { downloadCsv, ScientificReportDialog } from './ScientificReport'

export function ProfileAssumptions({ profile, step }: {profile:MissionProfile;step:number}) {
  const earth = {centre:'Earth centre',any_disc:'any part of the Earth disc',full_disc:'the entire Earth disc'}[profile.earth_requirement]
  return <p><strong>{profile.name} · profile v{profile.version}</strong> · Solar centre {profile.solar_required?'required':'tracked only'} · Requires {earth} ·
    {' '}{profile.prefer_full_disc?'full-disc preference enabled · ':''}antenna ≥ {profile.minimum_antenna_elevation_deg}° · minimum continuous window {hours(profile.minimum_window_s)} · nominal step {hours(step)}</p>
}

export default function MissionReport({ timelines, names }: {timelines:MissionTimeline[];names:Record<string,string>}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [generated,setGenerated] = useState('')
  const title = timelines.length>1 ? 'Site Operational Window Comparison Report' : 'Mission Timeline Report'
  function open() {
    setGenerated(new Date().toISOString().replace('Z',''))
    dialog.current?.showModal()
  }
  const first = timelines[0]
  return <><LiquidGlassButton label={title} onClick={open}/>
    <ScientificReportDialog dialog={dialog} title={title} generated={generated}
      onCsv={()=>downloadCsv(missionCsv(timelines),timelines.length>1?'luna-scope-operational-window-comparison.csv':'luna-scope-mission-timeline.csv')}>
      <p>{shownUtc(first.start_utc)} to {shownUtc(first.end_utc)} · {timelines.length} {timelines.length===1?'observer':'observers'}</p>
      <ProfileAssumptions profile={first.profile} step={first.step_seconds}/>
      <p>Sampled native-terrain evidence for solar-centre illumination, Earth visibility and the assumed antenna elevation mask. Unresolved time includes brackets between differing observations. Equipment performance is outside this analysis.</p>
      {timelines.map(timeline=>{
        const totals = timeline.summary
        return <section key={timeline.site_id} className="mission-report-site">
          <h3>{names[timeline.site_id]??timeline.site_id} · {timeline.site_id}</h3>
          <p>{timeline.observer.latitude_deg.toFixed(6)}°, {timeline.observer.longitude_deg_east.toFixed(6)}° east · {timeline.observer.elevation_m.toFixed(2)} m · native pixel centre</p>
          <p>{hours(totals.duration_s.favourable)} favourable · {hours(totals.qualifying_favourable_s)} meets minimum · {hours(totals.duration_s.unfavourable)} unfavourable · {hours(totals.duration_s.conditional)} conditional · {hours(totals.duration_s.unresolved)} unresolved · {hours(totals.duration_s.invalid)} invalid</p>
          <MissionTimelineChart timeline={timeline} compact/>
          {(['solar','earth_centre','earth_disc','antenna'] as const).map(track=>{
            const durations:Record<string,number> = {}
            for (const row of timeline.intervals) durations[row.tracks[track]] = (durations[row.tracks[track]]??0)+row.duration_s
            return <p key={track}><strong>{trackNames[track]}</strong> · {Object.entries(durations).map(([state,time])=>`${conditionLabel(state)} ${hours(time)}`).join(' · ')}</p>
          })}
          <p><a href={timeline.terrain.source_url}>{timeline.terrain.file}</a> · {timeline.terrain.resolution_m.join(' × ')} m · SHA-256 <code>{timeline.terrain.source_dem_sha256}</code></p>
          <p>{timeline.celestial.source} · {timeline.celestial.kernels.map(item=><a key={item.file} href={item.url} title={`SHA-256 ${item.sha256}`}>{item.file}{' '}</a>)}</p>
          <p>{timeline.solar_engine.method.name} · {timeline.earth_engine.method.name}</p>
          <p>Quality flags: {[...new Set([...timeline.quality_flags,...timeline.solar_engine.flags,...timeline.earth_engine.flags])].map(conditionLabel).join(' · ')}</p>
          <h3>Transition brackets</h3>
          {timeline.transitions.length ? <ul>{timeline.transitions.map((event,index)=><li key={index}>
            {trackNames[event.track]} · {conditionLabel(event.from_state)} → {conditionLabel(event.to_state)} · {shownUtc(event.start_utc)} to {shownUtc(event.end_utc)}
          </li>)}</ul> : <p>No differing classified observations bracket a transition.</p>}
          <h3>Favourable intervals</h3>
          {totals.favourable_windows.length ? <ul>{totals.favourable_windows.map(window=><li key={window.start_utc}>
            {shownUtc(window.start_utc)} to {shownUtc(window.end_utc)} · {hours(window.duration_s)} · {window.meets_minimum?'Meets minimum':'Below minimum'}
          </li>)}</ul> : <p>No confirmed favourable interval in the sampled period.</p>}
        </section>
      })}
    </ScientificReportDialog>
  </>
}
