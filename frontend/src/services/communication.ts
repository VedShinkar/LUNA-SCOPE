import type { Observer, Vector } from './celestial'
import type { MapPoint } from './terrain'

export type State = 'visible' | 'obstructed' | 'unresolved'
export type Disc = 'fully_visible' | 'partially_visible' | 'fully_obscured' | 'unresolved'
export type Criterion = 'centre' | 'any_disc' | 'full_disc' | 'centre_with_mask'
export type EarthSample = {
  utc: string; earth_azimuth_deg: number | null; earth_elevation_deg: number; earth_angular_radius_deg: number
  earth_enu_unit_vector: Vector; upper_limb_elevation_deg: number; lower_limb_elevation_deg: number
  centre_above_horizontal: boolean; centre_state: State; centre_native_clear: boolean; centre_reason: string
  antenna_eligible: boolean; criterion_state: State; native_horizon_deg: number | null; centre_nodata_cells: number
  clearance_deg: { centre: number | null; upper_limb: number | null; lower_limb: number | null }
  rms_horizon_deg: [number, number] | null; rms_sensitive: boolean | null
  disc_state: Disc; disc_evidence: string; disc_probe_counts: Record<State,number>; native_clear_probes: number
}
type Provenance = {
  site_id: string; criterion: Criterion; antenna_min_elevation_deg: number
  terrain: { file: string; source_url: string; resolution_m: [number,number]; bounds_m: number[]; rms_source_url: string | null }
}
export type EarthPoint = Provenance & {
  observer: Observer; samples: EarthSample[]; requested_sample_count: number; refinement_sample_count: number
  summary: { duration_s: Record<State,number>; longest_visible_s: number; longest_interruption_s: number
    fraction_classified_time_visible: number | null
    intervals: { state: State; start_utc: string; end_utc: string; duration_s: number }[]
    transitions: { start_utc: string; end_utc: string; from_state: State; to_state: State }[] }
}
export type EarthRegion = Provenance & {
  utc: string; region: {left: number; top: number; width: number; height: number}
  counts: Record<string,number>; percent_of_valid: Record<string,number | null>; cells: (EarthSample | null)[]
}
export type EpochQuery = { utc: string } | { start_utc: string; end_utc: string; step_seconds: number }

async function request<T>(path: string, site: string, point: MapPoint | null, body: object,
  mask: number, criterion: Criterion, signal: AbortSignal): Promise<T> {
  const response = await fetch(`/terrain/explorer/communication/${path}`, {
    method:'POST', signal, headers:{'Content-Type':'application/json'},
    body:JSON.stringify({site_id:site,point:point && {easting_m:point.easting,northing_m:point.northing},
      antenna_min_elevation_deg:mask,criterion,...body}),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `Earth visibility request failed (HTTP ${response.status}).`)
  }
  return response.json()
}

export const getEarthPoint = (site: string, point: MapPoint | null, query: EpochQuery, mask: number, criterion: Criterion, signal: AbortSignal) =>
  request<EarthPoint>('utc' in query ? 'point' : 'series', site, point, query, mask, criterion, signal)

export const getEarthRegion = (site: string, point: MapPoint | null, utc: string, side: number, mask: number, criterion: Criterion, signal: AbortSignal) =>
  request<EarthRegion>('region', site, point, {utc,side}, mask, criterion, signal)
