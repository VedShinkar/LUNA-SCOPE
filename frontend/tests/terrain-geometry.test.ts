import { deepStrictEqual, equal, ok } from 'node:assert/strict'
import { test } from 'node:test'
import type { TerrainGrid } from '../src/services/terrain.ts'
import { buildTerrain, elevationAtHit, projectedPoint } from '../src/visualization/terrain-geometry.ts'

const grid = {
  width: 3, height: 2, transform: [4, 2, 100, 2, -4, 200],
  elevation: { range: [10, 50], values: [10, 20, 30, 40, 50, 50], unit: 'm' },
  valid: [true, true, true, true, true, true], quad_valid: [true, true],
} as TerrainGrid

test('affine pixel centres map to easting, up, and negative northing with upward faces', () => {
  for (const transform of [grid.transform, [4, 2, 100, -2, 4, 200] as const]) {
    const data = buildTerrain({ ...grid, transform: [...transform] })
    const point = projectedPoint([...transform], 2.5, 0.5)
    deepStrictEqual([...data.positions.slice(6, 9)], [
      point.easting - data.center.easting, 30 - data.datum, data.center.northing - point.northing,
    ])
    const [a, b, c] = data.indices.slice(0, 3).map(index => data.positions.slice(index * 3, index * 3 + 3))
    const crossY = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2])
    ok(crossY > 0)
  }
})

test('faces spanning an invalid native block or masked vertex are omitted', () => {
  equal(buildTerrain({ ...grid, quad_valid: [false, true] }).indices.length, 6)
  equal(buildTerrain({ ...grid, valid: [true, false, true, true, true, true] }).indices.length, 0)
})

test('visual exaggeration leaves the recovered elevation in metres', () => {
  const data = buildTerrain(grid)
  for (const exaggeration of [1, 2.5, 4]) {
    equal(elevationAtHit(data.positions[1] * exaggeration, exaggeration, data.datum), 10)
  }
})
