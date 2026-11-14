export type Affine = [number, number, number, number, number, number]
export type LayerName = 'elevation' | 'slope' | 'aspect' | 'roughness' | 'coverage' |
  'uncertainty' | 'elevation_uncertainty' | 'hazards' | 'suitability' | 'horizon'
export type Band = { values: (number | null)[]; unit: string; range: [number, number] | null }
export type TerrainGrid = {
  site_id: string
  site_name: string
  source: string
  source_file: string
  source_url: string
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

export function getGrid(limit: number, signal: AbortSignal, centre?: MapPoint) {
  const params = new URLSearchParams({ max_dimension: String(limit) })
  if (centre) {
    params.set('easting_m', String(centre.easting))
    params.set('northing_m', String(centre.northing))
  }
  return request<TerrainGrid>(`/terrain/explorer/grid?${params}`, signal)
}

export async function getPoint(point: MapPoint, signal: AbortSignal) {
  const result = await request<TerrainPoint>('/terrain/point', signal, {
    easting_m: point.easting, northing_m: point.northing,
  })
  if (!result.is_valid) throw new Error('Native-grid measurements are unavailable at this location.')
  return result
}

export function getHorizon(point: MapPoint, signal: AbortSignal) {
  return request<Horizon>('/terrain/horizon', signal, {
    observer_x: point.easting, observer_y: point.northing, observer_height_m: 2, azimuth_step_deg: 5,
  })
}
