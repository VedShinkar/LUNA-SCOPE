import type { EarthSample } from '../services/communication'

export type MapMode = 'centre' | 'disc' | 'mask'
export const earthPalette = {
  visible:'#70d3e9', obstructed:'#496483', unresolved:'#87929d', invalid:'#25323e',
  fully_visible:'#70d3e9', partially_visible:'#d4a968', fully_obscured:'#496483',
  eligible:'#86c5aa', ineligible:'#b58167',
}
export const earthLabels: Record<keyof typeof earthPalette,string> = {
  visible:'Centre visible', obstructed:'Centre obstructed', unresolved:'Unresolved', invalid:'NoData',
  fully_visible:'Full disc visible', partially_visible:'Partial disc visible', fully_obscured:'Disc obscured',
  eligible:'Elevation meets mask', ineligible:'Elevation below mask',
}

export function mapClass(cell: EarthSample | null, mode: MapMode): keyof typeof earthPalette {
  if (!cell) return 'invalid'
  if (mode === 'mask') return cell.antenna_eligible ? 'eligible' : 'ineligible'
  return mode === 'disc' ? cell.disc_state : cell.centre_state
}

export function discPlot(sample: EarthSample) {
  const low = Math.min(-2, sample.lower_limb_elevation_deg - 1)
  const high = Math.max(2, sample.upper_limb_elevation_deg + 1, sample.native_horizon_deg ?? 0)
  const scale = 148 / (high-low)
  const y = (elevation: number) => 22 + (high-elevation)*scale
  return { centre: y(sample.earth_elevation_deg), upper:y(sample.upper_limb_elevation_deg),
    lower:y(sample.lower_limb_elevation_deg), radius:sample.earth_angular_radius_deg*scale,
    horizontal:y(0), horizon:sample.native_horizon_deg == null ? null : y(sample.native_horizon_deg) }
}
