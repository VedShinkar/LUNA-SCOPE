import type { LayerName, TerrainGrid } from '../../services/terrain'

type Swatch = [color: string, label: string]
export const layerNames: Record<LayerName, string> = {
  elevation: 'Elevation', slope: 'Calculated slope', nasa_slope: 'NASA reference slope', aspect: 'Aspect', roughness: 'Roughness', roughness_35m: 'Roughness · 35 m', roughness_75m: 'Roughness · 75 m',
  coverage: 'Observation Count', uncertainty: 'Slope Uncertainty', elevation_uncertainty: 'Elevation Uncertainty',
  hazards: 'Combined hazard', suitability: 'Slope threshold', roughness_screen: 'Roughness threshold · 15 m', horizon: 'Local horizon',
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
  return grid.layers[layer === 'suitability' ? 'slope' : layer === 'roughness_screen' ? 'roughness' : layer]
}

export function layerStyle(grid: TerrainGrid, layer: LayerName, threshold: number, colorRange?: [number, number], ramp = 'default', roughnessThreshold = 2) {
  const suitability: Swatch[] = [[unknown, 'Unknown'], ['#71b7aa', `≤ ${threshold}°`], ['#e07457', `> ${threshold}°`]]
  const categorical = { coverage, hazards: hazard, suitability, aspect }[layer as 'coverage' | 'hazards' | 'suitability' | 'aspect']
  if (categorical) return { colors: categorical.map(([color]) => color), labels: categorical.map(([, label]) => label), categorical: true }
  if (layer === 'roughness_screen') return {colors: [unknown, '#71b7aa', '#e07457'], labels: ['NoData', `≤ ${roughnessThreshold} m`, `> ${roughnessThreshold} m`], categorical: true}
  const range = colorRange ?? grid.elevation.range ?? [0, 1]
  const slopeRange = colorRange ?? [0, 45]
  const slopeLabels = [0, 1, 2, 3].map(i => `${Number((slopeRange[0] + (slopeRange[1] - slopeRange[0]) * i / 3).toFixed(1))}°${i === 3 ? '+' : ''}`)
  const styles: Partial<Record<LayerName, { colors: string[]; labels: string[] }>> = {
    elevation: { colors: ramp === 'ice' ? ['#13223d','#376388','#80bbd3','#e6f6fc'] : elevation, labels: [`${Math.round(range[0]).toLocaleString()} m`, `${Math.round(range[1]).toLocaleString()} m`] },
    slope: { colors: slope, labels: slopeLabels },
    nasa_slope: { colors: slope, labels: slopeLabels },
    roughness: { colors: roughness, labels: ['0 m', '1 m', '2 m', '3 m+'] },
    roughness_35m: { colors: roughness, labels: ['0 m', '1 m', '2 m', '3 m+'] },
    roughness_75m: { colors: roughness, labels: ['0 m', '1 m', '2 m', '3 m+'] },
    uncertainty: { colors: uncertainty, labels: ['0°', '2°', '4°', '6°+'] },
    elevation_uncertainty: { colors: uncertainty, labels: ['0 m', '1 m', '2 m', '3 m+'] },
  }
  return { ...(styles[layer] ?? styles.elevation!), categorical: false }
}

export function colorPosition(grid: TerrainGrid, layer: LayerName, value: number, threshold: number, colorRange?: [number, number], roughnessThreshold = 2) {
  if (layer === 'suitability') return value <= threshold ? 1 : 2
  if (layer === 'roughness_screen') return value <= roughnessThreshold ? 1 : 2
  if (layer === 'hazards') return value
  if (layer === 'coverage') return Math.min(value, 2)
  if (layer === 'aspect') return ((value % 360 + 360) % 360) / 90
  const [min, max] = colorRange ?? (layer === 'elevation' ? grid.elevation.range ?? [0, 1] :
    [0, layer === 'slope' || layer === 'nasa_slope' ? 45 : layer === 'uncertainty' ? 6 : 3])
  return 3 * Math.min(1, Math.max(0, (value - min) / (max - min || 1)))
}

export function sampleLabel(layer: LayerName, value: number | null | undefined, threshold: number, roughnessThreshold = 2) {
  if (value == null) return 'Unknown'
  if (layer === 'hazards') return hazard[value]?.[1] ?? 'Unknown'
  if (layer === 'suitability') return `${value.toFixed(2)}° · ${value <= threshold ? 'Within configured threshold' : 'Exceeds configured threshold'}`
  if (layer === 'roughness_screen') return `${value.toFixed(2)} m · ${value <= roughnessThreshold ? 'Within configured threshold' : 'Exceeds configured threshold'}`
  if (layer === 'coverage') return value === 0 ? 'Interpolated' : `${value} LOLA returns`
  if (layer === 'aspect' && value < 0) return 'Flat'
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 }) +
    (layer === 'uncertainty' ? '° RMS' : layer === 'elevation_uncertainty' ? ' m RMS' : ['slope', 'nasa_slope', 'aspect'].includes(layer) ? '°' : ' m')
}
