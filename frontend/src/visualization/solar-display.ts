import type { RegionAnalysis, RegionFrame, SolarState } from '../services/illumination'
import type { TerrainGrid } from '../services/terrain'

export const solarColors = { illuminated:'#f0c47c', shadowed:'#385b80', unknown:'#899299', invalid:'#24313f', clear:'#6eacaa' }

export function displayState(state: SolarState, native: string) {
  return state === 'unknown' && native === 'clear' ? 'clear' : state
}

export function solarTexture(grid: TerrainGrid, map: RegionAnalysis, frame: RegionFrame): (string | null)[] {
  return nativeWindowColors(grid, map.site_id, map.region,
    frame.states.map((state,index) => solarColors[displayState(state, frame.native_states[index])]))
}

export function nativeWindowColors(grid: TerrainGrid, siteId: string,
  region: {left:number;top:number;width:number}, samples: string[]): (string | null)[] {
  const window = grid.sampling.window
  const colors = Array<string | null>(grid.width * grid.height).fill(null)
  if (!window || grid.sampling.stride !== 1 || grid.site_id !== siteId) return colors
  samples.forEach((color, index) => {
    const col = region.left + index % region.width - window[0]
    const row = region.top + Math.floor(index / region.width) - window[1]
    if (row >= 0 && col >= 0 && row < grid.height && col < grid.width) {
      colors[row*grid.width+col] = color
    }
  })
  return colors
}
