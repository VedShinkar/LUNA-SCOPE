import type { Observer, Vector } from './celestial'
import type { Affine, MapPoint } from './terrain'

export type SolarState = 'illuminated' | 'shadowed' | 'unknown' | 'invalid'
export type SolarSample = {
  utc: string; state: SolarState; native_state: 'clear' | 'shadowed' | 'unknown'; reason: string
  solar_azimuth_deg: number | null; solar_elevation_deg: number; solar_angular_radius_deg: number
  centre_above_horizontal: boolean; sun_enu_unit_vector: Vector; native_horizon_deg: number | null
  horizon_distance_m: number | null; traced_distance_m: number; nodata_along_ray: number
  rms_horizon_deg: [number, number] | null; rms_sensitive: boolean | null
}
type Counts = Record<SolarState | 'valid_cells' | 'classified', number>
type Interval = { state: string; start_utc: string; end_utc: string; duration_s: number }
type Summary = {
  duration_s: Record<string, number>; longest_clear_s: number; longest_shadow_s: number; gap_count: number
  fraction_known_time_clear: number | null; intervals: Interval[]
  transitions: { start_utc: string; end_utc: string; from: string; to: string }[]
  gaps: {first_shadow_utc: string; last_shadow_utc: string; duration_s: number; bracket_s: number}[]
}
type Provenance = {
  site_id: string; terrain: { file: string; source_url: string; resolution_m: [number, number]; bounds_m: number[]; rms_source_url: string | null }
  celestial: { source: string }; classification: Record<string,string>; quality_flags: string[]
}
export type ObserverAnalysis = Provenance & { observer: Observer; samples: SolarSample[]; summary: Summary; native_summary: Summary }
export type RegionFrame = {
  utc: string; states: SolarState[]; native_states: Array<SolarState | 'clear'>; counts: Counts
  native_clear: number; rms_sensitive: number; lit_percent_of_valid_cells: number | null
  lit_percent_of_classified_cells: number | null
}
export type RegionAnalysis = Provenance & {
  region: { left: number; top: number; width: number; height: number; affine: Affine }
  frames: RegionFrame[]
}
export type SolarQuery = { utc: string } | { start_utc: string; end_utc: string; step_seconds: number }

async function request<T>(path: string, siteId: string, point: MapPoint | null, body: object, signal: AbortSignal): Promise<T> {
  const response = await fetch(`/terrain/explorer/illumination/${path}`, {
    method: 'POST', signal, headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({site_id:siteId, point:point && {easting_m:point.easting,northing_m:point.northing}, ...body}),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `Illumination request failed (HTTP ${response.status}).`)
  }
  return response.json()
}

export function getSolarObserver(siteId: string, point: MapPoint | null, times: SolarQuery, signal: AbortSignal) {
  return request<ObserverAnalysis>('utc' in times ? 'point' : 'series', siteId, point, times, signal)
}

export function getSolarRegion(siteId: string, point: MapPoint | null, times: string[], side: number, signal: AbortSignal) {
  return request<RegionAnalysis>('region', siteId, point, {times_utc:times,side}, signal)
}
