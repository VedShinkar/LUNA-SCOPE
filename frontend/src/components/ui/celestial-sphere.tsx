import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Component, useEffect, useMemo, useRef, type ReactNode } from 'react'
import { Color, Vector2, type Group } from 'three'

type SphereProps = { hue?: number; speed?: number; zoom?: number; particleSize?: number }
const vertex = `varying vec3 positionOnSphere; void main(){positionOnSphere=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`
const fragment = `
  varying vec3 positionOnSphere;
  uniform vec3 tint;
  uniform vec2 cursor;
  uniform float phase;
  float field(vec3 p){return sin(p.x+sin(p.y*1.9))+sin(p.y+cos(p.z*2.3))+cos(p.z+p.x*.73);}
  void main(){
    vec3 n=normalize(positionOnSphere);
    vec3 p=n*8.+vec3(cursor*.34,phase);
    float cloud=smoothstep(-.15,2.4,field(p)+field(p*2.7)*.28+field(p*5.3)*.12);
    float edge=pow(1.-max(0.,n.z),2.);
    gl_FragColor=vec4(tint*(.16+.62*cloud+.35*edge),1.);
    #include <colorspace_fragment>
  }
`

function Sphere({hue = 210, speed = .13, zoom = 1, particleSize = .018}: SphereProps) {
  const group = useRef<Group>(null)
  const { gl, invalidate } = useThree()
  const motion = useMemo(() => matchMedia('(prefers-reduced-motion: reduce)'), [])
  const uniforms = useMemo(() => ({tint: {value: new Color()}, phase: {value: 0}, cursor: {value: new Vector2()}}), [])
  const stars = useMemo(() => {
    const points = new Float32Array(360 * 3)
    for (let i = 0; i < 360; i++) {
      const y = 1 - 2 * (i + .5) / 360, theta = i * 2.39996323, ring = Math.sqrt(1 - y * y), radius = 1.04 + (i % 13) * .047
      points.set([Math.cos(theta) * ring * radius, y * radius, Math.sin(theta) * ring * radius], i * 3)
    }
    return points
  }, [])
  useEffect(() => {
    const host = gl.domElement
    let frame = 0, last = 0, visible = false
    const tick = (time: number) => {
      if (!document.hidden && visible && !motion.matches && time - last > 45) {
        uniforms.phase.value += Math.min((time - last) / 1000, .06) * speed
        last = time
        invalidate()
      }
      frame = requestAnimationFrame(tick)
    }
    const update = () => {
      cancelAnimationFrame(frame)
      if (!document.hidden && visible && !motion.matches) frame = requestAnimationFrame(tick)
      else uniforms.cursor.value.set(0, 0)
      invalidate()
    }
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; update() })
    observer.observe(host)
    motion.addEventListener('change', update)
    document.addEventListener('visibilitychange', update)
    return () => { observer.disconnect(); cancelAnimationFrame(frame); motion.removeEventListener('change', update); document.removeEventListener('visibilitychange', update) }
  }, [gl, invalidate, motion, speed, uniforms])
  useFrame(({pointer}) => {
    uniforms.tint.value.setHSL(hue / 360, .62, .44)
    if (!motion.matches) uniforms.cursor.value.lerp(pointer, .12)
    if (group.current) group.current.rotation.y = uniforms.phase.value * .5 + uniforms.cursor.value.x * .23
  })
  return <group ref={group} scale={zoom}>
    <mesh><sphereGeometry args={[1, 48, 32]} /><shaderMaterial vertexShader={vertex} fragmentShader={fragment} uniforms={uniforms} toneMapped={false} /></mesh>
    <points><bufferGeometry><bufferAttribute attach="attributes-position" args={[stars, 3]} /></bufferGeometry><pointsMaterial color="#c3e8ff" size={particleSize} transparent opacity={.73} depthWrite={false} /></points>
  </group>
}

class PreviewBoundary extends Component<{children: ReactNode}, {failed: boolean}> {
  state = {failed: false}
  static getDerivedStateFromError() { return {failed: true} }
  render() { return this.state.failed ? null : this.props.children }
}

// This workspace replaces the Moon view, so the two full scene renderers never coexist.
export default function CelestialSphere(props: SphereProps) {
  return <figure className="celestial-preview" aria-label="Illustrative celestial field">
    <PreviewBoundary><Canvas frameloop="demand" dpr={[1, 1.35]} camera={{position: [0, 0, 4.5], fov: 44}} fallback={null}><Sphere {...props} /></Canvas></PreviewBoundary>
    <figcaption>Illustrative celestial field</figcaption>
  </figure>
}
