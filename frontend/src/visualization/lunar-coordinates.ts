import type { Coordinates } from '../services/lunar.ts'

export const LUNAR_RADIUS_M = 1_737_400
const rad = Math.PI / 180

// +Y is lunar north, +Z is the prime meridian, +X is 90° east.
export function lunarPosition({ latitude, longitude }: Coordinates, radius: number): [number, number, number] {
  const phi = latitude * rad
  const lambda = longitude * rad
  const horizontal = radius * Math.cos(phi)
  return [horizontal * Math.sin(lambda), radius * Math.sin(phi), horizontal * Math.cos(lambda)]
}

export function lunarCoordinates(x: number, y: number, z: number): Coordinates {
  return { latitude: Math.atan2(y, Math.hypot(x, z)) / rad, longitude: Math.atan2(x, z) / rad }
}

export function polarCoordinates(easting: number, northing: number): Coordinates {
  return {
    latitude: 2 * Math.atan(Math.hypot(easting, northing) / (2 * LUNAR_RADIUS_M)) / rad - 90,
    longitude: Math.atan2(easting, northing) / rad,
  }
}

export function polarPosition({ latitude, longitude }: Coordinates) {
  const radius = 2 * LUNAR_RADIUS_M * Math.tan((90 + latitude) * rad / 2)
  return { easting: radius * Math.sin(longitude * rad), northing: radius * Math.cos(longitude * rad) }
}

// Interpolate the pixel-centred global grid, wrapping longitude and clamping latitude.
export function sampleGlobal(values: Float32Array, width: number, height: number, point: Coordinates) {
  const x = ((point.longitude + 180) % 360 + 360) % 360 / 360 * width - 0.5
  const y = Math.max(0, Math.min(height - 1, (90 - point.latitude) / 180 * height - 0.5))
  const col = Math.floor(x)
  const row = Math.floor(y)
  const left = (col + width) % width
  const right = (left + 1) % width
  const lower = Math.min(height - 1, row + 1)
  const across = (r: number) => values[r * width + left] * (1 - (x - col)) + values[r * width + right] * (x - col)
  return across(row) * (1 - (y - row)) + across(lower) * (y - row)
}
