import type { MissionTimeline, Track } from '../services/mission'

export const trackOrder:Track[] = ['solar','earth_centre','earth_disc','antenna','mission']
export const trackNames:Record<Track,string> = {
  solar:'Solar centre',earth_centre:'Earth centre',earth_disc:'Earth disc',antenna:'Antenna elevation',mission:'Mission condition',
}
export const missionColors = {
  favourable:'#78c4b6',unfavourable:'#cd8b74',conditional:'#d6b363',unresolved:'#8695ad',invalid:'#596371',
}
export const conditionLabel = (state:string) => state.replaceAll('_',' ').replace(/^./, value=>value.toUpperCase())
export const hours = (seconds:number) => `${(seconds/3600).toLocaleString(undefined,{maximumFractionDigits:3})} h`
export const shownUtc = (time:string) => time.replace('T',' ').replace('Z',' UTC')
export const epoch = (time:string) => Date.parse(time)

export function trackTone(state:string):keyof typeof missionColors {
  if (['illuminated','visible','fully_visible','satisfied','favourable'].includes(state)) return 'favourable'
  if (['shadowed','obstructed','fully_obscured','below_mask','unfavourable'].includes(state)) return 'unfavourable'
  if (state==='partially_visible'||state==='conditional') return 'conditional'
  return state==='invalid' ? 'invalid' : 'unresolved'
}

export function intervalIndex(timeline:MissionTimeline, time:number):number {
  const index = timeline.intervals.findIndex(row=>epoch(row.start_utc)<=time && time<epoch(row.end_utc))
  return index<0 ? (time>=epoch(timeline.end_utc) ? timeline.intervals.length-1 : 0) : index
}

export function missionCsv(timelines:MissionTimeline[]):unknown[][] {
  const header = ['record_type','site_id','latitude_deg','longitude_deg_east','elevation_m','utc','solar_source_utc','earth_source_utc',
    'solar','earth_centre','earth_disc','antenna','mission','transition_track','start_utc','end_utc','from_state','to_state','step_s','minimum_window_s',
    'solar_required','earth_requirement','prefer_full_disc','antenna_min_deg','profile_version','profile_name','source_raster','source_sha256',
    'solar_method','earth_method','ephemeris','flags']
  const rows = timelines.flatMap(timeline=>{
    const observer = timeline.observer
    const profile = timeline.profile
    const origin = [timeline.site_id,observer.latitude_deg,observer.longitude_deg_east,observer.elevation_m]
    const configuration = [timeline.step_seconds,profile.minimum_window_s,profile.solar_required,profile.earth_requirement,
      profile.prefer_full_disc,profile.minimum_antenna_elevation_deg,profile.version,
      /^[\s]*[=+\-@]/.test(profile.name) ? `'${profile.name}` : profile.name,timeline.terrain.file,
      timeline.terrain.source_dem_sha256,timeline.solar_engine.method.name,timeline.earth_engine.method.name,timeline.celestial.source]
    return [
      ...timeline.samples.map(sample=>['sample',...origin,sample.utc,sample.solar_source_utc,sample.earth_source_utc,
        ...trackOrder.map(track=>sample.tracks[track]),null,null,null,null,null,...configuration,
        [...timeline.quality_flags,...sample.flags].join('|')]),
      ...timeline.transitions.map(transition=>['transition',...origin,null,null,null,null,null,null,null,null,transition.track,
        transition.start_utc,transition.end_utc,transition.from_state,transition.to_state,...configuration,timeline.quality_flags.join('|')]),
    ]
  })
  return [header,...rows]
}
