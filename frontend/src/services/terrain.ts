export type Affine = [number, number, number, number, number, number]
export type LayerName = 'elevation' | 'slope' | 'aspect' | 'roughness' | 'coverage' |
  'roughness_35m' | 'roughness_75m' | 'nasa_slope' | 'uncertainty' | 'elevation_uncertainty' | 'hazards' | 'suitability' | 'roughness_screen' | 'horizon'
export type Band = { values: (number | null)[]; unit: string; range: [number, number] | null }
export type TerrainGrid = {
  site_id: string
  site_name: string
  source: string
  source_file: string
  source_url: string
  elevation_source_url: string
  width: number
  height: number
  source_width: number
  source_height: number
  source_transform: Affine
  transform: Affine
  crs: string
  crs_wkt: string
  source_resolution: [number, number]
  resolution: [number, number]
  pixel_registration: string
  source_raster_type: string | null
  horizontal_unit: string
  nodata_percent: number
  sampling: { method: string; stride: number; offset: number; window?: [number, number, number, number] | null }
  elevation: Band
  valid: boolean[]
  quad_valid: boolean[]
  layers: Partial<Record<LayerName, Band>>
  layer_sources: Partial<Record<LayerName, {file: string; kind: 'raw' | 'processed'; url: string | null}>>
  observation_support: {direct_percent: number; interpolated_percent: number; missing_percent: number} | null
  unavailable: Partial<Record<LayerName, string>>
}

export type MapPoint = { easting: number; northing: number }
export type TerrainPoint = {
  is_valid: boolean
  elevation_m: number | null
  slope_deg: number | null
  aspect_deg: number | null
  roughness: { roughness_15m_m: number | null; roughness_35m_m: number | null; roughness_75m_m: number | null }
  hazard_classification: {
    physical_hazard_class: string
    combined_screening_class: string
  }
  uncertainty_and_observation: {
    lola_observation_count?: number
    elevation_uncertainty_m_rms: number | null
    slope_uncertainty_deg_rms: number | null
  }
}
export type Horizon = {
  azimuths_deg: number[]
  horizon_angles_deg: (number | null)[]
}

export type Comparison = { source: string; sites: { site_id: string; metrics: {
  elevation: {minimum_m: number; maximum_m: number} | null
  observations: {direct_observation_percentage: number} | null
  roughness: {small?: {statistics?: {median_m?: number}}} | null
  hazards: Record<string, number> | null
  nasa_slope_median_deg: number | null
  slope_uncertainty_median_deg: number | null
  elevation_uncertainty_median_m: number | null
} | null }[] }

export const getComparison = (signal: AbortSignal) => request<Comparison>('/terrain/explorer/comparison', signal)

export type RasterStatistics = {
  site_id: string; layer: LayerName; file: string; unit: string; valid: number; invalid: number; total: number
  minimum: number | null; maximum: number | null; mean: number | null; bounds: number[]; resolution: number[]
  width: number; height: number; source_url: string; source_kind: string; direct?: number; direct_percent?: number | null
  histogram?: { edges: number[]; counts: number[]; outside: number }
  screening?: { threshold: number; within: number; exceeds: number }
}

export function getStatistics(siteId: string, layer: LayerName, signal: AbortSignal, threshold?: number) {
  const params = new URLSearchParams({ site_id: siteId, layer })
  if (threshold !== undefined) params.set('threshold', String(threshold))
  return request<RasterStatistics>(`/terrain/explorer/statistics?${params}`, signal)
}

async function request<T>(path: string, signal: AbortSignal, body?: object): Promise<T> {
  const response = await fetch(path, body ? {
    signal, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  } : { signal })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `Terrain request failed (${response.status}).`)
  }
  return response.json()
}

export async function getGrid(siteId: string, limit: number, signal: AbortSignal, centre?: MapPoint) {
  const params = new URLSearchParams({ site_id: siteId, max_dimension: String(limit) })
  if (centre) {
    params.set('easting_m', String(centre.easting))
    params.set('northing_m', String(centre.northing))
  }
  const grid = await request<TerrainGrid>(`/terrain/explorer/grid?${params}`, signal)
  if (grid.site_id !== siteId) throw new Error(`The server did not return ${siteId} terrain.`)
  return grid
}

export async function getPoint(siteId: string, point: MapPoint, signal: AbortSignal) {
  const result = await request<TerrainPoint>('/terrain/point', signal, {
    site_id: siteId, easting_m: point.easting, northing_m: point.northing,
  })
  if (!result.is_valid) throw new Error('Native-grid measurements are unavailable at this location.')
  return result
}

export function getHorizon(siteId: string, point: MapPoint, signal: AbortSignal) {
  return request<Horizon>('/terrain/horizon', signal, {
    site_id: siteId, observer_x: point.easting, observer_y: point.northing, observer_height_m: 2, azimuth_step_deg: 5,
  })
}
