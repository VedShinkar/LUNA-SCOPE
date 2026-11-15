import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import type { LayerName, MapPoint, TerrainGrid } from '../services/terrain'
import { colorPosition, layerBand, layerStyle } from '../features/lunar-explorer/layers'
import { buildTerrain, elevationAtHit } from './terrain-geometry'
import { projectedSceneDirection } from './celestial-display'

export type Hit = MapPoint & { elevation: number; index: number; x: number; y: number }
export type Selected = MapPoint & { elevation: number | null }
export type CelestialOverlay = {
  longitude: number
  directions: { vector: [number, number, number]; color: string; above: boolean }[]
}
export type RelativeCamera = { azimuth: number; inclination: number; zoom: number }
export type CameraLink = { subscribe: (receive: (state: RelativeCamera) => void) => () => void; publish: (state: RelativeCamera) => void }
type TerrainCapture = CustomEvent<{ save: (image: string) => void }>

function ReportCapture() {
  const { gl, scene, camera } = useThree()
  useEffect(() => {
    const capture = (event: Event) => {
      gl.render(scene, camera)
      ;(event as TerrainCapture).detail.save(gl.domElement.toDataURL('image/jpeg', .82))
    }
    const canvas = gl.domElement
    canvas.addEventListener('terrain-report-capture', capture)
    return () => canvas.removeEventListener('terrain-report-capture', capture)
  }, [gl, scene, camera])
  return null
}
type Props = {
  grid: TerrainGrid
  layer: LayerName
  threshold: number
  exaggeration: number
  contours: boolean
  reset: number
  overhead?: boolean
  selected: Selected | null
  profileEndpoints?: Selected[]
  profilePath?: Selected[]
  profileMarker?: Selected
  onProfilePick?: (hit: Hit) => void
  onHover: (hit: Hit | null) => void
  onSelect: (hit: Hit) => void
  onHeading: (degrees: number) => void
  fromGlobe?: boolean
  cameraLink?: CameraLink
  colorRange?: [number, number]
  elevationRamp?: 'default'|'ice'
  roughnessThreshold?: number
  celestial?: CelestialOverlay
  surfaceColors?: (string | null)[]
}

function CelestialRays({ overlay, origin, size }: { overlay: CelestialOverlay; origin: [number, number, number]; size: number }) {
  const rays = useMemo(() => overlay.directions.map(ray => {
    const axis = new THREE.Vector3(...projectedSceneDirection(ray.vector, overlay.longitude))
    const length = size * 0.28
    const tip = axis.clone().multiplyScalar(length)
    const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis)
    const segments = ray.above ? [new THREE.Vector3(), tip] : Array.from({length: 16}, (_, i) =>
      axis.clone().multiplyScalar(length * (Math.floor(i / 2) + (i % 2) * 0.56) / 7.56))
    return {...ray, tip, quaternion, geometry: new THREE.BufferGeometry().setFromPoints(segments)}
  }), [overlay, size])
  useEffect(() => () => rays.forEach(ray => ray.geometry.dispose()), [rays])
  return <group position={origin}>
    <mesh rotation={[-Math.PI / 2, 0, 0]} renderOrder={2} raycast={() => undefined}>
      <ringGeometry args={[size * 0.077, size * 0.078, 80]} />
      <meshBasicMaterial color="#91aabc" depthTest={false} depthWrite={false} transparent opacity={0.7} side={THREE.DoubleSide}/>
    </mesh>
    {rays.map(ray => <group key={ray.color}>
      <lineSegments geometry={ray.geometry} renderOrder={3} raycast={() => undefined}>
        <lineBasicMaterial color={ray.color} depthTest={false} depthWrite={false} />
      </lineSegments>
      <mesh position={ray.tip} quaternion={ray.quaternion} renderOrder={3} raycast={() => undefined}>
        <coneGeometry args={[size * 0.006, size * 0.022, 12]}/>
        <meshBasicMaterial color={ray.color} depthTest={false} depthWrite={false} />
      </mesh>
    </group>)}
  </group>
}

function CameraControls({ size, reset, onHeading, fromGlobe, overhead, focus, cameraLink }: Pick<Props, 'reset' | 'onHeading' | 'fromGlobe'|'overhead'|'cameraLink'> & { size: number; focus?: THREE.Vector3 }) {
  const { camera, gl, invalidate, size: viewport } = useThree()
  const orbit = useRef<OrbitControls | null>(null)
  const arrival = useRef<{ start: number; from: THREE.Vector3; to: THREE.Vector3 } | null>(null)
  const first = useRef(true)
  const applying = useRef(false)
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
      if (!applying.current) cameraLink?.publish({ azimuth: controls.getAzimuthalAngle(), inclination: controls.getPolarAngle(), zoom: controls.getDistance() / size })
      invalidate()
    }
    controls.addEventListener('change', changed)
    orbit.current = controls
    return () => { controls.dispose(); orbit.current = null }
  }, [camera, gl, invalidate, onHeading, size, cameraLink])
  useEffect(() => {
    if (!orbit.current || !viewport.width || !viewport.height) return
    const fit = Math.max(1.12, 1.35 * viewport.height / viewport.width)
    const centre=focus??new THREE.Vector3()
    const target = (overhead ? new THREE.Vector3(0,size*1.22*fit,size*.002) : new THREE.Vector3(size * 0.20 * fit, size * 0.61 * fit, size * 0.83 * fit)).add(centre)
    if ((!first.current || fromGlobe) && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      if(first.current)camera.position.set(-450, size*2.6, size*.26)
      arrival.current = { start: performance.now(), from: camera.position.clone(), to: target }
      orbit.current.enabled = false
    } else {
      arrival.current = null
      orbit.current.enabled = true
      camera.position.copy(target)
    }
    first.current = false
    orbit.current.target.copy(centre)
    orbit.current.update()
    invalidate()
  }, [camera, invalidate, size, reset, viewport.height, viewport.width, fromGlobe, overhead, focus])
  useEffect(() => cameraLink?.subscribe(state => {
    const controls = orbit.current
    if (!controls) return
    applying.current = true
    const newPosition = new THREE.Vector3().setFromSphericalCoords(state.zoom * size, state.inclination, state.azimuth)
    camera.position.copy(controls.target).add(newPosition)
    controls.update()
    applying.current = false
    invalidate()
  }), [cameraLink, camera, size, invalidate])
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

function Terrain({ grid, layer, threshold, exaggeration, contours, reset, selected, profileEndpoints, profilePath, profileMarker, onProfilePick, onHover, onSelect, onHeading, fromGlobe, overhead, cameraLink, colorRange, elevationRamp, roughnessThreshold, celestial, surfaceColors }: Props) {
  const data = useMemo(() => buildTerrain(grid), [grid])
  const focus=useMemo(()=>overhead&&selected?new THREE.Vector3(selected.easting-data.center.easting,((selected.elevation??data.datum)-data.datum)*exaggeration,data.center.northing-selected.northing):undefined,[overhead,selected,data,exaggeration])
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
  const trace = useMemo(() => {
    const coords: number[] = []
    function add(point: Selected) {
      coords.push(point.easting-data.center.easting, (point.elevation!-data.datum)*exaggeration+data.size*.002, data.center.northing-point.northing)
    }
    profilePath?.forEach((point,i) => {
      if (i && point.elevation != null && profilePath[i-1].elevation != null) { add(profilePath[i-1]); add(point) }
    })
    return new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(coords,3))
  },[profilePath,data,exaggeration])
  useEffect(()=>()=>trace.dispose(),[trace])
  const texture = useMemo(() => {
    const band = layerBand(grid, layer)
    const style = layerStyle(grid, layer, threshold, colorRange, elevationRamp, roughnessThreshold)
    const palette = style.colors.map(color => new THREE.Color(color))
    const color = new THREE.Color()
    const rgb = new Uint8Array(grid.width * grid.height * 4)
    for (let i = 0; i < grid.width * grid.height; i++) {
      const value = band?.values[i]
      const override = surfaceColors?.[i]
      if (override && grid.valid[i]) color.set(override)
      else if (value == null || (layer === 'aspect' && value < 0)) color.set('#464b57')
      else {
        const position = colorPosition(grid, layer, value, threshold, colorRange, roughnessThreshold)
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
  }, [grid, layer, threshold, colorRange, elevationRamp, roughnessThreshold, surfaceColors])
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
    <CameraControls size={data.size} reset={reset} onHeading={onHeading} fromGlobe={fromGlobe} overhead={overhead} focus={focus} cameraLink={cameraLink} />
    <hemisphereLight args={['#e0e6ef', '#504234', 1.45]} />
    <directionalLight position={[-9000, 5100, -6500]} color="#fff0db" intensity={2.55} />
    <directionalLight position={[2500, 2000, 6000]} color="#91add0" intensity={0.35} />
    <mesh geometry={geometry} material={material} scale={[1, exaggeration, 1]}
      onPointerMove={event => onHover(hit(event))}
      onPointerOut={() => onHover(null)}
      onClick={event => {
        if (event.delta > 4) return
        const selection = hit(event)
        if (!selection) return
        if (event.shiftKey && onProfilePick) onProfilePick(selection)
        else onSelect(selection)
      }} />
    <lineSegments geometry={trace} raycast={()=>undefined}><lineBasicMaterial color="#6feaff" depthTest={false}/></lineSegments>
    {celestial && selected?.elevation != null && <CelestialRays overlay={celestial} size={data.size}
      origin={[selected.easting - data.center.easting, (selected.elevation - data.datum) * exaggeration, data.center.northing - selected.northing]} />}
    {[selected, profileMarker, ...(profileEndpoints ?? [])].map((marker, index) => marker?.elevation != null && <mesh key={index} position={[
      marker.easting - data.center.easting,
      (marker.elevation - data.datum) * exaggeration + data.size * 0.003,
      data.center.northing - marker.northing,
    ]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={1} raycast={() => undefined}>
      <ringGeometry args={[data.size * 0.0045, data.size * 0.006, 36]} />
      <meshBasicMaterial color={index===1?'#ffdf9b':'#70e3ec'} depthTest={false} depthWrite={false} side={THREE.DoubleSide} />
    </mesh>)}
  </>
}

export default function TerrainScene(props: Props) {
  return <Canvas frameloop="demand" dpr={props.cameraLink ? [1, 1.25] : [1, 1.75]} camera={{ fov: 43, near: 10, far: 130000 }}
    gl={{ antialias: true, alpha: true }}
    onPointerMissed={() => props.onHover(null)}>
    <Terrain {...props} />
    <ReportCapture />
  </Canvas>
}
