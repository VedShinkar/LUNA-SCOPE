import { Canvas, useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { gsap } from 'gsap'
import { albedoUrl, type Context, type Coordinates, type LunarSite, type PolarGrid } from '../services/lunar'
import { lunarCoordinates, lunarPosition, polarCoordinates, sampleGlobal } from './lunar-coordinates'
import { DeepSpace } from './DeepSpace'
import { InteractiveNebulaShader } from '../components/ui/interactive-nebula-shader'

export type Destination = { point: Coordinates; distance: number; enterSite?: boolean }
export type SurfaceHit = Coordinates & { landmark?: string }
type Props = {
  context: Context
  heights: Float32Array
  overview?: PolarGrid
  approach?: PolarGrid
  destination: Destination
  imagery: boolean
  relief: boolean
  graticule: boolean
  nebula: boolean
  regionalRelief: boolean
  activeSite?: LunarSite
  measuring: boolean
  measurement: Coordinates[]
  onPoint: (point: Coordinates) => void
  selected: SurfaceHit | null
  onSelect: (point: SurfaceHit) => void
  onHover: (point: SurfaceHit | null) => void
  onRange: (distance: number) => void
  onView: (point: Coordinates, distance: number) => void
  onArrival: () => void
}

const vec = (point: Coordinates, radius: number) => new THREE.Vector3(...lunarPosition(point, radius))
const radians = Math.PI / 180
const clamp = THREE.MathUtils.clamp
const ease = THREE.MathUtils.smoothstep

function Camera({ destination, radius, onRange, onView, onArrival, motion }: Pick<Props, 'destination' | 'onRange' | 'onView' | 'onArrival'> & { radius: number; motion: { busy: boolean } }) {
  const { camera, gl, size, invalidate } = useThree()
  const controls = useRef<OrbitControls | null>(null)
  const flight = useRef<{
    progress: number; from: THREE.Vector3; rotation: THREE.Quaternion; startRadius: number; distance: number; enter?: boolean
  } | null>(null)
  const gesture = useRef(false)
  const range = useRef(Infinity)
  const previousAltitude = useRef(Infinity)
  const previousDirection = useRef(new THREE.Vector3())
  useEffect(() => {
    const orbit = new OrbitControls(camera, gl.domElement)
    orbit.enableDamping = true
    orbit.enablePan = false
    orbit.minDistance = radius + 10
    orbit.maxDistance = radius * 7
    orbit.zoomSpeed = 0.7
    orbit.addEventListener('change', () => invalidate())
    orbit.addEventListener('start', () => { gesture.current = true; motion.busy = true })
    orbit.addEventListener('end', () => { gesture.current = false; motion.busy = Boolean(flight.current) })
    controls.current = orbit
    return () => orbit.dispose()
  }, [camera, gl, radius, invalidate, motion])
  useEffect(() => {
    const from = camera.position.clone().normalize()
    const target = vec(destination.point, 1)
    // OrbitControls constrains the exact poles. Keep the destination just off its singularity.
    if (Math.abs(target.y) > 0.999999999) target.set(0, Math.sign(target.y), 0.00003).normalize()
    const rotation = new THREE.Quaternion().setFromUnitVectors(from, target)
    const aspect = Math.max(0.1, size.width / size.height)
    const fit = destination.distance > 1000 ? Math.max(1, 0.88 / aspect) : Math.max(1, 1 / aspect)
    const distance = Math.min(radius * 6, Math.max(15, destination.distance * fit))
    const active = { progress: 0, from, rotation, startRadius: camera.position.length(), distance, enter: destination.enterSite }
    flight.current = active
    motion.busy = true
    if (controls.current) controls.current.enabled = false
    const tween = gsap.to(active, {
      progress: 1, duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : active.enter ? 2.15 : 1.85,
      ease: 'power2.inOut', onUpdate: () => invalidate(),
    })
    return () => { tween.kill(); flight.current = null; motion.busy = false }
  }, [camera, destination, radius, size.width, size.height, invalidate, motion])

  useFrame(() => {
    const orbit = controls.current
    if (!orbit) return
    const active = flight.current
    if (active) {
      const fraction = active.progress
      const rotation = new THREE.Quaternion().slerp(active.rotation, ease(fraction, 0, 0.75))
      const altitude = Math.exp(THREE.MathUtils.lerp(Math.log(Math.max(15, active.startRadius - radius)), Math.log(active.distance), fraction))
      camera.position.copy(active.from).applyQuaternion(rotation).multiplyScalar(radius + altitude)
      orbit.update()
      if (fraction >= 1) {
        flight.current = null
        orbit.enabled = true
        motion.busy = gesture.current
        if (active.enter) onArrival()
      }
    } else orbit.update()
    const altitude = camera.position.length() - radius
    if (altitude < 700) {
      const n = camera.position.clone().normalize()
      // Near the pole, orient the view toward increasing polar northing so the
      // regional approach and the projected Site04 view share grid north.
      const gridNorth = new THREE.Vector3(0, 0, 1).addScaledVector(n, -n.z).normalize()
      const bodyNorth = new THREE.Vector3(0, 1, 0).addScaledVector(n, -n.y).normalize()
      camera.up.copy(bodyNorth.lerp(gridNorth, 1 - ease(altitude, 320, 700)))
      if (camera.up.lengthSq() < 1e-5) camera.up.copy(gridNorth)
      camera.lookAt(orbit.target)
      camera.up.set(0, 1, 0)
    }
    if (Math.abs(altitude - range.current) > Math.max(1, altitude * 0.035)) {
      range.current = altitude
      onRange(altitude)
    }
    const direction = camera.position.clone().normalize()
    if (previousDirection.current.distanceToSquared(direction) > 0.000001 || Math.abs(previousAltitude.current - altitude) > 1) {
      previousDirection.current.copy(direction)
      previousAltitude.current = altitude
      onView(lunarCoordinates(direction.x, direction.y, direction.z), altitude)
    }
  })
  return null
}

function PointerResponse({ motion, surface, marker, site, onHover }: {
  motion: { busy: boolean }
  surface: React.RefObject<THREE.Mesh | null>
  marker: React.RefObject<THREE.Mesh | null>
  site?: Coordinates & { name: string }
  onHover: Props['onHover']
}) {
  const { camera, gl, invalidate, size } = useThree()
  const offset = useRef({ x: 0, y: 0 })
  const landmarkHover = useRef(false)
  useEffect(() => {
    const canvas = gl.domElement
    const ray = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    const reduced = matchMedia('(prefers-reduced-motion: reduce)')
    const tweenOptions = { duration: 0.55, ease: 'power3.out', onUpdate: () => invalidate() }
    const xTo = gsap.quickTo(offset.current, 'x', tweenOptions)
    const yTo = gsap.quickTo(offset.current, 'y', tweenOptions)
    let lastPick = -Infinity
    let timer: ReturnType<typeof setTimeout> | undefined
    let pending: { x: number; y: number } | undefined
    const pick = () => {
      timer = undefined
      if (!pending || motion.busy || !surface.current) return
      lastPick = performance.now()
      pointer.set(pending.x, pending.y)
      ray.setFromCamera(pointer, camera)
      if (site && marker.current?.visible && ray.intersectObject(marker.current, false).length) {
        landmarkHover.current = true
        invalidate()
        onHover({ latitude: site.latitude, longitude: site.longitude, landmark: site.name })
        return
      }
      landmarkHover.current = false
      invalidate()
      const intersection = ray.intersectObject(surface.current, false)[0]
      onHover(intersection ? lunarCoordinates(intersection.point.x, intersection.point.y, intersection.point.z) : null)
    }
    const move = (event: PointerEvent) => {
      if (event.pointerType === 'touch' || event.buttons || motion.busy) return
      const rect = canvas.getBoundingClientRect()
      const x = clamp(2 * (event.clientX - rect.left) / rect.width - 1, -1, 1)
      const y = clamp(1 - 2 * (event.clientY - rect.top) / rect.height, -1, 1)
      if (!reduced.matches) { xTo(x * 0.017); yTo(y * 0.017) }
      pending = { x, y }
      if (timer === undefined) timer = setTimeout(pick, Math.max(0, 120 - (performance.now() - lastPick)))
    }
    const clear = () => {
      pending = undefined
      landmarkHover.current = false
      clearTimeout(timer)
      timer = undefined
      xTo(0)
      yTo(0)
      onHover(null)
    }
    canvas.addEventListener('pointermove', move)
    canvas.addEventListener('pointerleave', clear)
    canvas.addEventListener('pointerdown', clear)
    canvas.addEventListener('wheel', clear, { passive: true })
    reduced.addEventListener('change', clear)
    return () => {
      canvas.removeEventListener('pointermove', move)
      canvas.removeEventListener('pointerleave', clear)
      canvas.removeEventListener('pointerdown', clear)
      canvas.removeEventListener('wheel', clear)
      reduced.removeEventListener('change', clear)
      clearTimeout(timer)
      xTo.tween.kill()
      yTo.tween.kill()
    }
  }, [camera, gl, invalidate, marker, motion, onHover, site, surface])
  useFrame(() => {
    if (marker.current) {
      const material = marker.current.material as THREE.MeshBasicMaterial
      material.color.set(landmarkHover.current ? '#ffffff' : '#81e6e8')
    }
    if (!(camera instanceof THREE.PerspectiveCamera) || !size.width || !size.height) return
    const { x, y } = offset.current
    if (motion.busy || Math.abs(x) + Math.abs(y) < 0.00005) {
      if (camera.view?.enabled) camera.clearViewOffset()
    } else camera.setViewOffset(size.width, size.height, x * size.width, -y * size.height, size.width, size.height)
  })
  return null
}

type ElevationGrid = Pick<PolarGrid, 'width' | 'height' | 'transform' | 'elevation' | 'quad_valid'>

function patch(grid: ElevationGrid | undefined) {
  if (!grid) return undefined
  const [a, b, c, d, e, f] = grid.transform
  const determinant = a * e - b * d
  return (point: Coordinates, coarse: number) => {
    if (point.latitude > -85) return coarse
    const rho = 3474800 * Math.tan((90 + point.latitude) * radians / 2)
    const x = rho * Math.sin(point.longitude * radians) - c
    const y = rho * Math.cos(point.longitude * radians) - f
    const col = (e * x - b * y) / determinant - 0.5
    const row = (a * y - d * x) / determinant - 0.5
    const edge = Math.min(col, row, grid.width - 1 - col, grid.height - 1 - row)
    if (edge <= 0) return coarse
    const j = Math.floor(col), i = Math.floor(row)
    if (!grid.quad_valid[i * (grid.width - 1) + j]) return coarse
    const k = i * grid.width + j
    const values = grid.elevation.values
    const top = THREE.MathUtils.lerp(values[k]!, values[k + 1]!, col - j)
    const bottom = THREE.MathUtils.lerp(values[k + grid.width]!, values[k + grid.width + 1]!, col - j)
    const fine = THREE.MathUtils.lerp(top, bottom, row - i)
    const coverage = ease(-point.latitude, 85, 85.35)
    return THREE.MathUtils.lerp(coarse, fine, coverage * ease(edge, 0, Math.min(grid.width, grid.height) * 0.12))
  }
}

function globeGeometry(radius: number, sample: (point: Coordinates) => number, polar: boolean, centreLatitude?: number) {
  const cols = 720
  // One index buffer spans the entire globe. Latitude rings become denser near
  // the pole while every ring shares the same longitude samples.
  const latitudes = Array.from({ length: 361 }, (_, row) => 90 - row * 0.5)
  if (polar) {
    latitudes.splice(350)
    for (let latitude = -85; latitude > -90;) {
      latitudes.push(latitude)
      latitude -= centreLatitude !== undefined && Math.abs(latitude - centreLatitude) < .82 ? .005 : .02
    }
    latitudes.push(-90)
  }
  const rows = latitudes.length - 1
  const geometry = new THREE.SphereGeometry(1, cols, rows)
  const positions = geometry.getAttribute('position')
  let north = 0, south = 0
  for (let col = 0; col < cols; col++) {
    north += sample({ latitude: 90, longitude: col / 2 - 180 }) / cols
    south += sample({ latitude: -90, longitude: col / 2 - 180 }) / cols
  }
  for (let i = 0; i < positions.count; i++) {
    const row = Math.floor(i / (cols + 1))
    const point = { latitude: latitudes[row], longitude: (i % (cols + 1)) / 2 - 180 }
    const elevation = row === 0 ? north : row === rows ? south : sample(point)
    positions.setXYZ(i, ...lunarPosition(point, radius + elevation / 1000))
  }
  geometry.computeVertexNormals()
  const normals = geometry.getAttribute('normal')
  const normal = new THREE.Vector3()
  for (let row = 1; row < rows; row++) {
    const start = row * (cols + 1), end = start + cols
    normal.set(normals.getX(start) + normals.getX(end), normals.getY(start) + normals.getY(end),
      normals.getZ(start) + normals.getZ(end)).normalize()
    normals.setXYZ(start, normal.x, normal.y, normal.z)
    normals.setXYZ(end, normal.x, normal.y, normal.z)
  }
  for (let col = 0; col <= cols; col++) {
    normals.setXYZ(col, 0, 1, 0)
    normals.setXYZ(rows * (cols + 1) + col, 0, -1, 0)
  }
  geometry.computeBoundingSphere()
  return geometry
}

function useSurfaceMaterial(texture: THREE.Texture | null, graticule: boolean, polar: boolean) {
  const material = useMemo(() => {
    const result = new THREE.MeshStandardMaterial({ color: texture ? '#ffffff' : '#aaa6a0', map: texture, roughness: 1 })
    result.customProgramCacheKey = () => 'lunar-surface'
    result.onBeforeCompile = shader => {
      shader.uniforms.linesEnabled = { value: graticule }
      shader.uniforms.polarEnabled = { value: polar }
      shader.vertexShader = 'varying vec3 lunarPosition;\n' + shader.vertexShader.replace(
        '#include <begin_vertex>', '#include <begin_vertex>\nlunarPosition=position;')
      shader.fragmentShader = 'varying vec3 lunarPosition; uniform bool linesEnabled; uniform bool polarEnabled;\n' +
        shader.fragmentShader.replace('#include <map_fragment>', `
          vec3 n = normalize(lunarPosition);
          float lon = atan(n.x,n.z);
          float lat = asin(clamp(n.y,-1.0,1.0));
          #ifdef USE_MAP
            vec2 mapUV = vec2(lon/6.28318530718+0.5,lat/3.14159265359+0.5);
            vec2 derivX = dFdx(mapUV), derivY = dFdy(mapUV);
            derivX.x -= floor(derivX.x+0.5);
            derivY.x -= floor(derivY.x+0.5);
            vec3 albedo = textureGrad(map,mapUV,derivX,derivY).rgb;
            float blend = polarEnabled ? smoothstep(1.50,1.55,-lat) : 0.0;
            diffuseColor.rgb *= mix(albedo,vec3(0.39,0.38,0.36),blend);
          #endif
          if(linesEnabled) {
            vec2 ll = vec2(lon,lat) / 0.2617993878;
            vec2 width = max(fwidth(ll),vec2(0.000001));
            vec2 line = abs(fract(ll+0.5)-0.5)/width;
            diffuseColor.rgb = mix(diffuseColor.rgb,vec3(0.24,0.62,0.71),0.52*(1.0-smoothstep(0.0,1.0,min(line.x,line.y))));
          }
        `).replace('#include <emissivemap_fragment>', `
          #include <emissivemap_fragment>
          // A narrow artistic edge fill on the actual terrain, with no atmosphere shell.
          float grazing = 1.0 - max(dot(normal, normalize(vViewPosition)), 0.0);
          totalEmissiveRadiance += vec3(0.019, 0.025, 0.032) * pow(grazing, 8.0);
        `)
    }
    return result
  }, [texture, graticule, polar])
  useEffect(() => () => material.dispose(), [material])
  return material
}

function Moon({ context, heights, overview, approach, imagery, relief, graticule, nebula, regionalRelief, activeSite, destination,
  onPoint, onHover, onSelect, selected, measuring, measurement, onRange, onView, onArrival }: Props) {
  const radius = context.radius_m / 1000
  const [height, width] = context.global_shape
  const global = useMemo(() => (p: Coordinates) => relief ? sampleGlobal(heights, width, height, p) : 0,
    [heights, width, height, relief])
  const polar = regionalRelief ? overview : undefined
  const close = polar ? approach : undefined
  const site = activeSite?.available ? activeSite : activeSite?.reference ? { ...activeSite.reference, name: activeSite.name } : undefined
  const centreLatitude = close && site ? site.latitude : undefined
  const sampler = useMemo(() => {
    const broad = patch(polar), fine = patch(close)
    return (point: Coordinates, altitude: number) => {
      const value = global(point)
      const region = broad?.(point, value) ?? value
      const detailed = fine?.(point, region) ?? region
      return THREE.MathUtils.lerp(region, detailed, 1 - ease(altitude, 100, 210))
    }
  }, [global, polar, close])
  const geometry = useMemo(() => {
    const base = globeGeometry(radius, point => sampler(point, 250), Boolean(polar), centreLatitude)
    if (close) {
      const finer = globeGeometry(radius, point => sampler(point, 95), Boolean(polar), centreLatitude)
      base.morphAttributes.position = [finer.getAttribute('position')]
      base.morphAttributes.normal = [finer.getAttribute('normal')]
      finer.dispose()
    }
    return base
  }, [radius, sampler, polar, close, centreLatitude])
  useEffect(() => () => geometry.dispose(), [geometry])
  const { camera, invalidate } = useThree()
  const texture = useMemo(() => {
    if (!context.imagery) return null
    const map = new THREE.TextureLoader().load(albedoUrl, () => invalidate())
    map.colorSpace = THREE.SRGBColorSpace
    map.wrapS = THREE.RepeatWrapping
    map.anisotropy = 4
    return map
  }, [context.imagery, invalidate])
  useEffect(() => () => texture?.dispose(), [texture])
  const material = useSurfaceMaterial(imagery ? texture : null, graticule, Boolean(polar))
  const marker = useRef<THREE.Mesh>(null)
  const pin = useRef<THREE.Mesh>(null)
  const surface = useRef<THREE.Mesh>(null)
  const motion = useRef({ busy: false }).current
  const globeMesh = useMemo(() => new THREE.Mesh(geometry, material), [geometry, material])
  useFrame(() => {
    const altitude = camera.position.length() - radius
    const morph = surface.current?.morphTargetInfluences
    if (morph?.length) {
      morph[0] = 1 - ease(altitude, 100, 210)
    }
    if (selected && pin.current) {
      const normal = vec(selected, 1)
      const distance = camera.position.distanceTo(normal.clone().multiplyScalar(radius))
      pin.current.position.copy(normal).multiplyScalar(radius + sampler(selected, altitude) / 1000 + Math.max(0.15, distance * 0.001))
      pin.current.scale.setScalar(Math.max(0.1, distance * 0.012))
      pin.current.quaternion.copy(camera.quaternion)
      pin.current.visible = camera.position.dot(normal) > radius
    }
    if (!site || !marker.current) return
    const normal = vec(site, 1)
    const heightAtSite = sampler(site, altitude)
    const distance = camera.position.distanceTo(normal.clone().multiplyScalar(radius))
    marker.current.position.copy(normal).multiplyScalar(radius + heightAtSite / 1000 + Math.max(0.3, distance * 0.001))
    marker.current.scale.setScalar(Math.max(0.25, distance * 0.009))
    marker.current.quaternion.copy(camera.quaternion)
    marker.current.visible = camera.position.dot(normal) > radius
  })
  function pick(event: ThreeEvent<MouseEvent>) {
    if (event.delta > 5 || motion.busy) return
    const point = event.point
    const coordinates = lunarCoordinates(point.x, point.y, point.z)
    if (measuring) onPoint(coordinates)
    else onSelect(coordinates)
  }
  return <>
    <Camera destination={destination} radius={radius} onRange={onRange} onView={onView} onArrival={onArrival} motion={motion} />
    <PointerResponse motion={motion} surface={surface} marker={marker} site={site} onHover={onHover} />
    {nebula && <InteractiveNebulaShader />}
    <DeepSpace />
    {/* Fixed display lights; never used by scientific calculations. */}
    <ambientLight intensity={0.18} color="#dce6f5" />
    <directionalLight position={[-2.6, -0.65, 1.35]} intensity={3.1} color="#fff5e8" />
    <directionalLight position={[0.7, -2, -0.4]} intensity={0.42} color="#c1d4ee" />
    <primitive object={globeMesh} ref={surface} onClick={pick} />
    {site && <mesh ref={marker} onClick={event => {
      if (event.delta <= 5 && marker.current?.visible && !motion.busy) {
        event.stopPropagation()
        if (measuring) onPoint(site)
        else onSelect({ latitude: site.latitude, longitude: site.longitude, landmark: site.name })
      }
    }}>
      <ringGeometry args={[0.64, 0.88, 36]} />
      <meshBasicMaterial color="#81e6e8" transparent opacity={0.95} side={THREE.DoubleSide} depthWrite={false} depthTest={false} />
    </mesh>}
    {selected && <mesh ref={pin} renderOrder={2} raycast={() => undefined}>
      <ringGeometry args={[0.29, 0.34, 36]} />
      <meshBasicMaterial color="#a5f1ec" side={THREE.DoubleSide} depthWrite={false} depthTest={false} />
    </mesh>}
    {measurement.map((point, index) => <mesh key={index}
      position={lunarPosition(point, radius + sampler(point, destination.distance) / 1000 + 1)} raycast={() => undefined}>
      <sphereGeometry args={[Math.max(0.2, destination.distance * 0.003), 12, 8]} />
      <meshBasicMaterial color="#85dce3" />
    </mesh>)}
  </>
}

export default function MoonScene(props: Props) {
  return <Canvas frameloop="demand" dpr={[1, 1.6]} camera={{ position: [0, 320, 6900], near: 0.3, far: 34000, fov: 45 }}
    gl={{ antialias: true, alpha: true, logarithmicDepthBuffer: true }}>
    <Moon {...props} />
  </Canvas>
}
