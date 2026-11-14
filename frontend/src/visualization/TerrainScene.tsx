import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { LayerName, MapPoint, TerrainGrid } from '../services/terrain'
import { colorPosition, layerBand, layerStyle } from '../features/lunar-explorer/layers'
import { buildTerrain, elevationAtHit } from './terrain-geometry'

export type Hit = MapPoint & { elevation: number; index: number; x: number; y: number }
export type Selected = MapPoint & { elevation: number }
type Props = {
  grid: TerrainGrid
  layer: LayerName
  threshold: number
  exaggeration: number
  contours: boolean
  reset: number
  selected: Selected | null
  onHover: (hit: Hit | null) => void
  onSelect: (hit: Hit) => void
  onHeading: (degrees: number) => void
  fromGlobe?: boolean
}

function CameraControls({ size, reset, onHeading, fromGlobe }: Pick<Props, 'reset' | 'onHeading' | 'fromGlobe'> & { size: number }) {
  const { camera, gl, invalidate, size: viewport } = useThree()
  const orbit = useRef<OrbitControls | null>(null)
  const arrival = useRef<{ start: number; from: THREE.Vector3; to: THREE.Vector3 } | null>(null)
  const first = useRef(true)
  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement)
    controls.enableDamping = true
    controls.minDistance = size * 0.035
    controls.maxDistance = size * 3.2
    controls.maxPolarAngle = Math.PI * 0.48
    const changed = () => {
      const east = camera.position.x - controls.target.x
      const south = camera.position.z - controls.target.z
      const vertical = camera.position.y - controls.target.y
      const tilt = vertical / Math.hypot(east, south, vertical)
      onHeading(Math.atan2(east, south * tilt) * 180 / Math.PI)
      invalidate()
    }
    controls.addEventListener('change', changed)
    orbit.current = controls
    return () => { controls.dispose(); orbit.current = null }
  }, [camera, gl, invalidate, onHeading, size])
  useEffect(() => {
    if (!orbit.current) return
    const fit = Math.max(1.12, 1.35 * viewport.height / viewport.width)
    const target = new THREE.Vector3(size * 0.20 * fit, size * 0.61 * fit, size * 0.83 * fit)
    if (first.current && fromGlobe && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      camera.position.set(-450, 25000 * Math.max(1, viewport.height / viewport.width), 2150)
      arrival.current = { start: performance.now(), from: camera.position.clone(), to: target }
      orbit.current.enabled = false
    } else {
      arrival.current = null
      orbit.current.enabled = true
      camera.position.copy(target)
    }
    first.current = false
    orbit.current.target.set(0, 0, 0)
    orbit.current.update()
    invalidate()
  }, [camera, invalidate, size, reset, viewport.height, viewport.width, fromGlobe])
  useFrame(() => {
    if (arrival.current && orbit.current) {
      const t = THREE.MathUtils.smoothstep(performance.now() - arrival.current.start, 0, 850)
      camera.position.lerpVectors(arrival.current.from, arrival.current.to, t)
      if (t === 1) {
        arrival.current = null
        orbit.current.enabled = true
      }
      invalidate()
    }
    orbit.current?.update()
  })
  return null
}

function Terrain({ grid, layer, threshold, exaggeration, contours, reset, selected, onHover, onSelect, onHeading, fromGlobe }: Props) {
  const data = useMemo(() => buildTerrain(grid), [grid])
  const geometry = useMemo(() => {
    const result = new THREE.BufferGeometry()
    result.setAttribute('position', new THREE.BufferAttribute(data.positions, 3))
    const uv = new Float32Array(grid.width * grid.height * 2)
    for (let i = 0; i < grid.width * grid.height; i++) {
      uv[i * 2] = (i % grid.width + 0.5) / grid.width
      uv[i * 2 + 1] = (Math.floor(i / grid.width) + 0.5) / grid.height
    }
    result.setAttribute('uv', new THREE.BufferAttribute(uv, 2))
    result.setIndex(data.indices)
    result.computeVertexNormals()
    return result
  }, [data, grid])
  useEffect(() => () => geometry.dispose(), [geometry])
  const texture = useMemo(() => {
    const band = layerBand(grid, layer)
    const style = layerStyle(grid, layer, threshold)
    const palette = style.colors.map(color => new THREE.Color(color))
    const color = new THREE.Color()
    const rgb = new Uint8Array(grid.width * grid.height * 4)
    for (let i = 0; i < grid.width * grid.height; i++) {
      const value = band?.values[i]
      if (value == null || (layer === 'aspect' && value < 0)) color.set('#464b57')
      else {
        const position = colorPosition(grid, layer, value, threshold)
        const lo = Math.floor(position)
        color.copy(palette[lo] ?? palette[0])
        if (position !== lo) color.lerp(palette[(lo + 1) % palette.length], position - lo)
      }
      color.convertLinearToSRGB()
      rgb[i * 4] = Math.round(color.r * 255)
      rgb[i * 4 + 1] = Math.round(color.g * 255)
      rgb[i * 4 + 2] = Math.round(color.b * 255)
      rgb[i * 4 + 3] = 255
    }
    const map = new THREE.DataTexture(rgb, grid.width, grid.height)
    map.colorSpace = THREE.SRGBColorSpace
    map.magFilter = THREE.NearestFilter
    map.minFilter = THREE.NearestFilter
    map.needsUpdate = true
    return map
  }, [grid, layer, threshold])
  useEffect(() => () => texture.dispose(), [texture])
  const material = useMemo(() => {
    const result = new THREE.MeshStandardMaterial({ map: texture, roughness: 1 })
    if (contours && layer === 'elevation') {
      result.customProgramCacheKey = () => 'lunar-elevation-contours'
      result.onBeforeCompile = shader => {
        shader.uniforms.terrainDatum = { value: data.datum }
        shader.vertexShader = 'varying float terrainHeight;\n' + shader.vertexShader.replace(
          '#include <begin_vertex>', '#include <begin_vertex>\nterrainHeight = position.y;')
        shader.fragmentShader = 'varying float terrainHeight; uniform float terrainDatum;\n' +
          shader.fragmentShader.replace('#include <map_fragment>', `#include <map_fragment>
            float level = (terrainHeight + terrainDatum) / 200.0;
            float width = max(fwidth(level), 0.002);
            float contour = 1.0 - smoothstep(0.0, width, abs(fract(level + 0.5) - 0.5));
            diffuseColor.rgb *= 1.0 - 0.32 * contour;`)
      }
    }
    return result
  }, [texture, contours, layer, data.datum])
  useEffect(() => () => material.dispose(), [material])
  function hit(event: ThreeEvent<PointerEvent | MouseEvent>): Hit | null {
    if (!event.uv) return null
    const col = Math.min(grid.width - 1, Math.max(0, Math.floor(event.uv.x * grid.width)))
    const row = Math.min(grid.height - 1, Math.max(0, Math.floor(event.uv.y * grid.height)))
    return {
      easting: data.center.easting + event.point.x,
      northing: data.center.northing - event.point.z,
      elevation: elevationAtHit(event.point.y, exaggeration, data.datum),
      index: row * grid.width + col,
      x: event.nativeEvent.offsetX, y: event.nativeEvent.offsetY,
    }
  }
  return <>
    <CameraControls size={data.size} reset={reset} onHeading={onHeading} fromGlobe={fromGlobe} />
    <hemisphereLight args={['#e0e6ef', '#504234', 1.45]} />
    <directionalLight position={[-9000, 5100, -6500]} color="#fff0db" intensity={2.55} />
    <directionalLight position={[2500, 2000, 6000]} color="#91add0" intensity={0.35} />
    <mesh geometry={geometry} material={material} scale={[1, exaggeration, 1]}
      onPointerMove={event => onHover(hit(event))}
      onPointerOut={() => onHover(null)}
      onClick={event => {
        if (event.delta > 4) return
        const selection = hit(event)
        if (selection) onSelect(selection)
      }} />
    {selected && <mesh position={[
      selected.easting - data.center.easting,
      (selected.elevation - data.datum) * exaggeration + data.size * 0.003,
      data.center.northing - selected.northing,
    ]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={1} raycast={() => undefined}>
      <ringGeometry args={[data.size * 0.0045, data.size * 0.006, 36]} />
      <meshBasicMaterial color="#70e3ec" depthTest={false} depthWrite={false} side={THREE.DoubleSide} />
    </mesh>}
  </>
}

export default function TerrainScene(props: Props) {
  return <Canvas frameloop="demand" dpr={[1, 1.75]} camera={{ fov: 43, near: 10, far: 130000 }}
    gl={{ antialias: true, alpha: true }}
    onPointerMissed={() => props.onHover(null)}>
    <Terrain {...props} />
  </Canvas>
}
