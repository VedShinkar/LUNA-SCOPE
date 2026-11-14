import type { LayerName, TerrainGrid } from '../../services/terrain'

type Swatch = [color: string, label: string]
export const layerNames: Record<LayerName, string> = {
  elevation: 'Elevation', slope: 'Slope', aspect: 'Aspect', roughness: 'Roughness',
  coverage: 'LOLA coverage', uncertainty: 'Slope uncertainty', elevation_uncertainty: 'Elevation uncertainty',
  hazards: 'Combined hazard', suitability: 'Slope suitability', horizon: 'Local horizon',
}

const unknown = '#464b57'
const hazard: Swatch[] = [[unknown, 'Unknown'], ['#589b92', 'Low'], ['#e1ab63', 'Moderate'], ['#df655e', 'High']]
const coverage: Swatch[] = [['#424d62', 'Interpolated'], ['#4bb6c1', '1 return'], ['#c9f5ed', '2+ returns']]
const aspect: Swatch[] = [['#77c7db', 'North'], ['#a9c97f', 'East'], ['#e9a060', 'South'], ['#a783d4', 'West']]
const slope = ['#354554', '#688e91', '#d5af76', '#d86e4b']
const elevation = ['#524942', '#82776a', '#b9ac97', '#e8d9bd']
const uncertainty = ['#353c52', '#6c6094', '#ac85ce', '#efcfff']
const roughness = ['#34464e', '#597f87', '#9db5a7', '#e4cfaa']

export function layerBand(grid: TerrainGrid, layer: LayerName) {
  if (layer === 'elevation') return grid.elevation
  return grid.layers[layer === 'suitability' ? 'slope' : layer]
}

export function layerStyle(grid: TerrainGrid, layer: LayerName, threshold: number) {
  const suitability: Swatch[] = [[unknown, 'Unknown'], ['#71b7aa', `≤ ${threshold}°`], ['#e07457', `> ${threshold}°`]]
  const categorical = { coverage, hazards: hazard, suitability, aspect }[layer as 'coverage' | 'hazards' | 'suitability' | 'aspect']
  if (categorical) return { colors: categorical.map(([color]) => color), labels: categorical.map(([, label]) => label), categorical: true }
  const range = grid.elevation.range ?? [0, 1]
  const styles: Partial<Record<LayerName, { colors: string[]; labels: string[] }>> = {
    elevation: { colors: elevation, labels: [`${Math.round(range[0]).toLocaleString()} m`, `${Math.round(range[1]).toLocaleString()} m`] },
    slope: { colors: slope, labels: ['0°', '15°', '30°', '45°+'] },
    roughness: { colors: roughness, labels: ['0 m', '1 m', '2 m', '3 m+'] },
    uncertainty: { colors: uncertainty, labels: ['0°', '2°', '4°', '6°+'] },
    elevation_uncertainty: { colors: uncertainty, labels: ['0 m', '1 m', '2 m', '3 m+'] },
  }
  return { ...(styles[layer] ?? styles.elevation!), categorical: false }
}

export function colorPosition(grid: TerrainGrid, layer: LayerName, value: number, threshold: number) {
  if (layer === 'suitability') return value <= threshold ? 1 : 2
  if (layer === 'hazards') return value
  if (layer === 'coverage') return Math.min(value, 2)
  if (layer === 'aspect') return ((value % 360 + 360) % 360) / 90
  const [min, max] = layer === 'elevation' ? grid.elevation.range ?? [0, 1] :
    [0, layer === 'slope' ? 45 : layer === 'uncertainty' ? 6 : 3]
  return 3 * Math.min(1, Math.max(0, (value - min) / (max - min || 1)))
}

export function sampleLabel(layer: LayerName, value: number | null | undefined, threshold: number) {
  if (value == null) return 'Unknown'
  if (layer === 'hazards') return hazard[value]?.[1] ?? 'Unknown'
  if (layer === 'suitability') return value <= threshold ? 'Within slope limit' : 'Exceeds slope limit'
  if (layer === 'coverage') return value === 0 ? 'Interpolated' : `${value} LOLA returns`
  if (layer === 'aspect' && value < 0) return 'Flat'
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 }) +
    (['slope', 'aspect', 'uncertainty'].includes(layer) ? '°' : ' m')
}
