import type { Observer } from './celestial'
import type { MapPoint } from './terrain'

export type MissionCondition = 'favourable'|'unfavourable'|'conditional'|'unresolved'|'invalid'
export type Track = 'solar'|'earth_centre'|'earth_disc'|'antenna'|'mission'
export type MissionProfile = {
  version: '1'; name: string; solar_required: boolean; earth_requirement: 'centre'|'any_disc'|'full_disc'
  prefer_full_disc: boolean; minimum_antenna_elevation_deg: number; minimum_window_s: number
}
export type MissionRequest = {
  start_utc:string; end_utc:string; step_seconds:number; profile:MissionProfile; refine_transitions:boolean
}
export type MissionSample = {
  utc:string; solar_source_utc:string|null; earth_source_utc:string|null; tracks:Record<Track,string>
  solar_reason:string|null; earth_reason:string|null; disc_evidence:string|null; flags:string[]
}
export type MissionInterval = {
  start_utc:string; end_utc:string; duration_s:number; tracks:Record<Track,string>; requires_sampling:boolean
}
export type MissionTransition = {
  track:Track; start_utc:string; end_utc:string; from_state:string; to_state:string
}
export type MissionTimeline = {
  site_id:string; observer:Observer; start_utc:string; end_utc:string; step_seconds:number; profile:MissionProfile
  samples:MissionSample[]; intervals:MissionInterval[]; transitions:MissionTransition[]
  summary:{duration_s:Record<MissionCondition,number>;longest_favourable_s:number;longest_unfavourable_s:number
    qualifying_favourable_s:number;transition_count:number
    favourable_windows:{start_utc:string;end_utc:string;duration_s:number;meets_minimum:boolean}[]}
  nominal_sample_count:number; refinement_sample_count:number
  terrain:{file:string;source_url:string;source_dem_sha256:string;resolution_m:number[]}
  solar_engine:{method:{name:string};flags:string[]}; earth_engine:{method:{name:string};flags:string[]}
  celestial:{source:string;kernels:{file:string;url:string;sha256:string}[]}
  quality_flags:string[];classification_rules:string[]
}
export const demonstration:MissionProfile = {
  version:'1',name:'Demonstration',solar_required:true,earth_requirement:'centre',
  prefer_full_disc:false,minimum_antenna_elevation_deg:0,minimum_window_s:3600,
}
const projected = (point:MapPoint) => ({easting_m:point.easting,northing_m:point.northing})

async function request<T>(path:string, payload:object, signal:AbortSignal):Promise<T> {
  const result = await fetch(`/terrain/explorer/mission-timeline/${path}`,{
    method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),
  })
  if (!result.ok) {
    const error = await result.json().catch(()=>({}))
    throw new Error(typeof error.detail==='string' ? error.detail : `Mission timeline request failed (HTTP ${result.status}).`)
  }
  return result.json()
}

export const getMissionTimeline = (config:MissionRequest, site_id:string, point:MapPoint|null, signal:AbortSignal) =>
  request<MissionTimeline>('site',{...config,site_id,point:point && projected(point)},signal)

export const getMissionComparison = (config:MissionRequest, site:string, point:MapPoint|null, signal:AbortSignal) =>
  request<{timelines:MissionTimeline[]}>('compare',{...config,points:point ? {[site]:projected(point)} : {}},signal)

export const validateMissionProfile = (profile:MissionProfile, signal:AbortSignal) =>
  request<MissionProfile>('profile',profile,signal)
