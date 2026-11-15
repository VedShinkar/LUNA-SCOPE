import type { Affine, Band } from './terrain'

export type Coordinates = { latitude: number; longitude: number }
export type LunarLevel = 'moon' | 'polar' | 'site'
export type LunarSite = { site_id: string; name: string; source_url: string; reference: (Coordinates & {basis: string; url: string}) | null } & (
  {available: false} | ({available: true; bounds: [number, number, number, number]; easting: number; northing: number; source_resolution_m: [number, number]} & Coordinates)
)
export type Context = {
  radius_m: number
  sites: LunarSite[]
  global_shape: [number, number]
  global_resolution_deg: number
  global_source_url: string
  polar_source_url: string
  imagery: boolean
}
export type PolarGrid = {
  width: number
  height: number
  transform: Affine
  resolution: [number, number]
  source_resolution: [number, number]
  source: string
  source_url: string
  elevation: Band
  quad_valid: boolean[]
}
export type Profile = { distance_m: number; elevation_m: (number | null)[]; source: string; sampling: string;
  distance_along_m?: number[]; coordinates?: Coordinates[]; projected?: {easting:number;northing:number}[];
  source_file?: string; source_url?: string; max_interval_m?: number }
export type SurfaceSample = { elevation_m: number | null; source: string }

const base = '/terrain/explorer'
export const albedoUrl = `${base}/moon/albedo`

async function load(path: string, signal: AbortSignal, body?: object) {
  const response = await fetch(base + path, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
  } : { signal })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `Lunar data request failed (${response.status}).`)
  }
  return response
}

export async function loadContext(signal: AbortSignal): Promise<Context> {
  return (await load('/context', signal)).json()
}

export async function loadMoon(context: Context, signal: AbortSignal): Promise<Float32Array> {
  const buffer = await (await load('/moon/elevation', signal)).arrayBuffer()
  const values = new Float32Array(buffer)
  if (values.length !== context.global_shape[0] * context.global_shape[1]) throw new Error('Unexpected LOLA grid size.')
  return values
}

export async function loadPolar(detail: 'overview' | 'approach', signal: AbortSignal, siteId?: string): Promise<PolarGrid> {
  return (await load(`/polar?${new URLSearchParams({detail, ...(siteId ? {site_id: siteId} : {})})}`, signal)).json()
}

export async function loadProfile(start: Coordinates, end: Coordinates, level: LunarLevel, signal: AbortSignal, siteId?: string): Promise<Profile> {
  return (await load('/profile', signal, { start, end, level, ...(siteId ? {site_id: siteId} : {}) })).json()
}

export async function loadSurface(point: Coordinates, level: 'moon' | 'polar', signal: AbortSignal): Promise<SurfaceSample> {
  const params = new URLSearchParams({ latitude: String(point.latitude), longitude: String(point.longitude), level })
  return (await load(`/surface?${params}`, signal)).json()
}

export async function loadCrossSection(siteId: string, vertices: Coordinates[], signal: AbortSignal): Promise<Profile> {
  return (await load('/cross-section', signal, { site_id: siteId, vertices })).json()
}
