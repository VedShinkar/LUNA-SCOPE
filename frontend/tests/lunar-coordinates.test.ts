import { equal, ok } from 'node:assert/strict'
import { test } from 'node:test'
import { lunarCoordinates, lunarPosition, polarCoordinates, sampleGlobal } from '../src/visualization/lunar-coordinates.ts'

test('global axes and Site04 projection use east-positive longitude', () => {
  const prime = lunarPosition({ latitude: 0, longitude: 0 }, 1)
  equal(prime[2], 1)
  const east = lunarPosition({ latitude: 0, longitude: 90 }, 1)
  equal(east[0], 1)
  const site = polarCoordinates(-1000, -7000)
  ok(Math.abs(site.latitude + 89.76681145215035) < 1e-10)
  ok(Math.abs(site.longitude + 171.86989764584402) < 1e-10)
  const restored = lunarCoordinates(...lunarPosition(site, 1737400))
  ok(Math.abs(restored.latitude - site.latitude) < 1e-10)
  ok(Math.abs(restored.longitude - site.longitude) < 1e-10)
})

test('pixel centres and the antimeridian use continuous source sampling', () => {
  const grid = new Float32Array([2, 4, 6, 8, 12, 14, 16, 18])
  equal(sampleGlobal(grid, 4, 2, { latitude: 45, longitude: -135 }), 2)
  equal(sampleGlobal(grid, 4, 2, { latitude: -45, longitude: 135 }), 18)
  equal(sampleGlobal(grid, 4, 2, { latitude: 0, longitude: 180 }), 10)
  equal(sampleGlobal(grid, 4, 2, { latitude: 0, longitude: -180 }), 10)
})
