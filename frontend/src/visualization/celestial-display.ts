type Vector = [number, number, number]
const RADIANS = Math.PI / 180

export function projectedSceneDirection([east, north, up]: Vector, longitude: number): Vector {
  // South-polar stereographic grid: true north points radially outward.
  const longitudeRadians = longitude * RADIANS
  const cosine = Math.cos(longitudeRadians), sine = Math.sin(longitudeRadians)
  return [east * cosine + north * sine, up, east * sine - north * cosine]
}

export function skyPosition(azimuth: number, elevation: number, limit: number) {
  return { x: 46 + azimuth * 468 / 360, y: 109 - elevation * 81 / limit }
}

export function inputUtc(value: string) {
  return new Date(value.length === 16 ? `${value}:00Z` : `${value}Z`).toISOString()
}

export function stepUtc(utc: string, seconds: number) {
  return new Date(Date.parse(utc) + seconds * 1000).toISOString().slice(0, 19)
}
