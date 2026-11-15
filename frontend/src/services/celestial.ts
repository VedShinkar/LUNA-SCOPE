import type { MapPoint } from './terrain'

export type Vector = [number, number, number]
export type Direction = {
  azimuth_deg: number | null
  elevation_deg: number
  enu_unit_vector: Vector
  body_fixed_unit_vector: Vector
  angular_diameter_deg: number
  above_local_horizontal: boolean
}
export type CelestialEpoch = { utc: string; et_tdb_s: number; sun: Direction; earth: Direction }
export type Observer = {
  site_id: string; latitude_deg: number; longitude_deg_east: number; elevation_m: number
  easting_m: number; northing_m: number; datum: string; source_url: string; source_file: string; placement: string
  source_pixel_row: number; source_pixel_column: number
}
type Kernel = { file: string; url: string; sha256: string }
type Conventions = Record<string, string | boolean>
export type CelestialResult = {
  status: 'computed'; observer: Observer; quality_flags: string[]; conventions: Conventions
  ephemeris: string; kernels: Kernel[]; samples: CelestialEpoch[]
}
export type CelestialMetadata = {
  coverage: { start_utc: string; end_utc: string } | null
  sites: { site_id: string; name: string; observer: Observer | null; error: string | null }[]
  error: string | null; ephemeris: string; kernels: Kernel[]; conventions: Conventions
  limits: { max_samples: number; min_step_seconds: number; max_step_seconds: number }
}
export type TimeQuery = { utc: string } | { start_utc: string; end_utc: string; step_seconds: number }

async function request<T>(path: string, signal: AbortSignal, body?: object): Promise<T> {
  const response = await fetch(`/terrain/explorer/celestial/${path}`, body ?
    {method: 'POST', signal, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {signal})
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(typeof payload.detail === 'string' ? payload.detail : `Celestial calculation failed (HTTP ${response.status}).`)
  }
  return response.json()
}

export const getCelestialMetadata = (signal: AbortSignal) => request<CelestialMetadata>('metadata', signal)
export function getCelestialGeometry(siteId: string, point: MapPoint | null, query: TimeQuery, signal: AbortSignal) {
  return request<CelestialResult>('utc' in query ? 'geometry' : 'series', signal, {
    ...query, site_id: siteId, point: point ? {easting_m: point.easting, northing_m: point.northing} : null,
  })
}
