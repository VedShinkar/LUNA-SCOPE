import type { Measurement } from './survey-tools.ts'

export const HISTORY_KEY = 'luna-scope.measurement-history.v1'

type StorageAccess = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
export type HistoryEdit =
  | { type: 'save'; record: Measurement }
  | { type: 'rename'; id: string; name: string }
  | { type: 'delete'; id: string }
  | { type: 'clear' }

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const nullableNumber = (value: unknown) => value === null || finite(value)
const date = (value: unknown) => typeof value === 'string' && Number.isFinite(Date.parse(value))
const coordinates = (value: unknown) => object(value) && finite(value.latitude) && Math.abs(value.latitude) <= 90 &&
  finite(value.longitude) && Math.abs(value.longitude) <= 180

function validRecord(value: unknown): value is Measurement {
  if (!object(value) || typeof value.id !== 'string' || !value.id || typeof value.name !== 'string' ||
    typeof value.source !== 'string' || !date(value.timestamp) ||
    !(value.siteId === null || (typeof value.siteId === 'string' && value.siteId.length > 0)) ||
    !(value.siteName === undefined || typeof value.siteName === 'string') ||
    !Array.isArray(value.coordinates) || !value.coordinates.every(coordinates) || !object(value.values)) return false

  if (value.provenance !== undefined) {
    const p = value.provenance
    if (!object(p) || !['productUrl', 'sourceFile', 'crs', 'sampling'].every(key => p[key] === undefined || typeof p[key] === 'string') ||
      (p.resolution !== undefined && (!Array.isArray(p.resolution) || p.resolution.length !== 2 || !p.resolution.every(n => finite(n) && n > 0)))) return false
  }

  const data = value.values
  if (value.kind === 'Elevation profile') {
    if (!(value.coordinates.length >= 2 && value.coordinates.length <= 32 && finite(data.distance_m) && data.distance_m >= 0 &&
      typeof data.source === 'string' && typeof data.sampling === 'string' &&
      Array.isArray(data.elevation_m) && data.elevation_m.every(nullableNumber))) return false
    const length = data.elevation_m.length
    return (data.coordinates === undefined || (Array.isArray(data.coordinates) && data.coordinates.length === length && data.coordinates.every(coordinates))) &&
      (data.projected === undefined || (Array.isArray(data.projected) && data.projected.length === length && data.projected.every(p => object(p) && finite(p.easting) && finite(p.northing)))) &&
      (data.distance_along_m === undefined || (Array.isArray(data.distance_along_m) && data.distance_along_m.length === length && data.distance_along_m.every((d, i, distances) => finite(d) && d >= 0 && (!i || d >= distances[i-1]))))
  }

  return value.kind === 'Terrain sample' && value.siteId !== null && value.coordinates.length === 1 &&
    object(value.projected) && finite(value.projected.easting) && finite(value.projected.northing) &&
    data.is_valid === true && ['elevation_m', 'slope_deg', 'aspect_deg'].every(key => nullableNumber(data[key])) &&
    object(data.roughness) && ['roughness_15m_m', 'roughness_35m_m', 'roughness_75m_m'].every(key => nullableNumber((data.roughness as Record<string, unknown>)[key])) &&
    object(data.hazard_classification) && typeof data.hazard_classification.physical_hazard_class === 'string' &&
    typeof data.hazard_classification.combined_screening_class === 'string' &&
    object(data.uncertainty_and_observation) && nullableNumber(data.uncertainty_and_observation.elevation_uncertainty_m_rms) &&
    nullableNumber(data.uncertainty_and_observation.slope_uncertainty_deg_rms) &&
    (data.uncertainty_and_observation.lola_observation_count === undefined || nullableNumber(data.uncertainty_and_observation.lola_observation_count))
}

function migrate(data: unknown) {
  // Add explicit migrations here before validating records from older schemas.
  if (!object(data) || data.version !== 1 || !Array.isArray(data.records)) return undefined
  return data.records as unknown[]
}

export type HistorySnapshot = { records: Measurement[]; warning?: string; unsaved?: boolean }

export function decodeHistory(raw: string | null): HistorySnapshot & { blocked?: boolean } {
  if (raw === null) return { records: [] }
  let data: unknown
  try { data = JSON.parse(raw) } catch {
    return { records: [], warning: 'Saved history could not be read because its JSON is damaged. Clear history to replace it.', blocked: true }
  }
  const entries = migrate(data)
  if (!entries) return { records: [], warning: 'Saved history uses an unsupported or damaged format. Clear history to replace it.', blocked: true }

  const records = new Map<string, Measurement>()
  let damaged = false
  for (const entry of entries) {
    if (validRecord(entry)) records.set(entry.id, entry)
    else damaged = true
  }
  return { records: [...records.values()], warning: damaged ? 'Some saved records were damaged. The valid measurements were restored.' : undefined }
}

function applyEdit(records: Measurement[], edit: HistoryEdit): Measurement[] {
  switch (edit.type) {
    case 'save': return [...records.filter(record => record.id !== edit.record.id), edit.record]
    case 'rename': return records.map(record => record.id === edit.id ? { ...record, name: edit.name } : record)
    case 'delete': return records.filter(record => record.id !== edit.id)
    case 'clear': return []
  }
}

export function createMeasurementHistory(storage: () => StorageAccess) {
  let pending: HistoryEdit[] = []
  let snapshot: HistorySnapshot = { records: [] }

  function refresh() {
    try {
      const saved = decodeHistory(storage().getItem(HISTORY_KEY))
      snapshot = { records: pending.reduce(applyEdit, saved.records), warning: saved.warning, unsaved: pending.length > 0 }
    } catch {
      snapshot = { ...snapshot, warning: 'Browser storage is unavailable. History changes may be lost when this tab closes.' }
    }
    return snapshot
  }
  refresh()

  function edit(change?: HistoryEdit) {
    if (change) {
      pending = change.type === 'clear' ? [change] : [...pending, change]
      snapshot = { ...snapshot, records: applyEdit(snapshot.records, change), unsaved: true }
    }
    if (!pending.length) return refresh()
    try {
      const target = storage()
      const saved = decodeHistory(target.getItem(HISTORY_KEY))
      if (saved.blocked && pending[0].type !== 'clear') {
        snapshot = { ...snapshot, warning: saved.warning }
        return snapshot
      }
      const records = pending.reduce(applyEdit, saved.records)
      if (records.length === 0 && pending.some(item => item.type === 'clear')) target.removeItem(HISTORY_KEY)
      else target.setItem(HISTORY_KEY, JSON.stringify({ version: 1, updatedAt: new Date().toISOString(), records }))
      pending = []
      snapshot = { records, warning: saved.blocked ? undefined : saved.warning }
    } catch (error) {
      const full = object(error) && error.name === 'QuotaExceededError'
      snapshot = { ...snapshot, warning: full ? 'Browser storage is full. Export your measurements or free storage and retry.' : 'History changes could not be saved to browser storage. Export your measurements or retry.' }
    }
    return snapshot
  }

  return { get snapshot() { return snapshot }, edit, refresh }
}
