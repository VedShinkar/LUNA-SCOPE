import type { Affine, TerrainGrid } from '../services/terrain.ts'

export function projectedPoint([a, b, c, d, e, f]: Affine, col: number, row: number) {
  return { easting: a * col + b * row + c, northing: d * col + e * row + f }
}

export function elevationAtHit(worldY: number, exaggeration: number, datum: number) {
  return worldY / exaggeration + datum
}

export function buildTerrain(grid: TerrainGrid) {
  const { width, height, transform, valid, quad_valid, elevation } = grid
  const center = projectedPoint(transform, width / 2, height / 2)
  const corners = [[0.5, 0.5], [width - 0.5, 0.5], [0.5, height - 0.5], [width - 0.5, height - 0.5]]
  const size = Math.max(...corners.map(([col, row]) => {
    const p = projectedPoint(transform, col, row)
    return 2 * Math.hypot(p.easting - center.easting, p.northing - center.northing)
  }))
  const datum = elevation.range ? (elevation.range[0] + elevation.range[1]) / 2 : 0
  const positions = new Float32Array(width * height * 3)
  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const index = row * width + col
      const point = projectedPoint(transform, col + 0.5, row + 0.5)
      positions[index * 3] = point.easting - center.easting
      positions[index * 3 + 1] = valid[index] ? elevation.values[index]! - datum : 0
      positions[index * 3 + 2] = center.northing - point.northing
    }
  }
  const indices = []
  const [a, b, , d, e] = transform
  const forward = a * e - b * d > 0
  for (let row = 0; row < height - 1; row++) {
    for (let col = 0; col < width - 1; col++) {
      const top = row * width + col
      const bottom = top + width
      if (!quad_valid[row * (width - 1) + col] ||
          !valid[top] || !valid[top + 1] || !valid[bottom] || !valid[bottom + 1]) continue
      if (forward) indices.push(top, top + 1, bottom, top + 1, bottom + 1, bottom)
      else indices.push(top, bottom, top + 1, top + 1, bottom, bottom + 1)
    }
  }
  return { positions, indices, center, datum, size }
}
