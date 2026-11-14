import type { Affine, Band } from './terrain'

export type Coordinates = { latitude: number; longitude: number }
export type LunarLevel = 'moon' | 'polar' | 'site04'
export type Context = {
  radius_m: number
  site04: (Coordinates & { bounds: [number, number, number, number]; easting: number; northing: number }) | null
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
export type Profile = { distance_m: number; elevation_m: (number | null)[]; source: string; sampling: string }

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

export async function loadPolar(detail: 'overview' | 'approach', signal: AbortSignal): Promise<PolarGrid> {
  return (await load(`/polar?detail=${detail}`, signal)).json()
}

export async function loadProfile(start: Coordinates, end: Coordinates, level: LunarLevel, signal: AbortSignal): Promise<Profile> {
  return (await load('/profile', signal, { start, end, level })).json()
}
