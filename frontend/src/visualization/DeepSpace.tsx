import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import { BufferAttribute, Color, type Group, type ShaderMaterial } from 'three'

// A seeded, illustrative sky. It is independent of lunar coordinates and ephemerides.
const shells = [
  { radius: 12800, count: 330, follow: .86, seed: 9251 },
  { radius: 19800, count: 650, follow: .93, seed: 2753 },
  { radius: 28700, count: 1040, follow: .98, seed: 6221 },
]

const vertexShader = `
  #include <common>
  #include <logdepthbuf_pars_vertex>
  attribute vec3 starTone;
  attribute vec2 starShape;
  uniform float pixelRatio;
  varying vec3 tone;
  varying float strength;
  void main() {
    tone = starTone;
    strength = starShape.y;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = starShape.x * pixelRatio;
    #include <logdepthbuf_vertex>
  }
`
const fragmentShader = `
  #include <common>
  #include <logdepthbuf_pars_fragment>
  varying vec3 tone;
  varying float strength;
  void main() {
    float r = length(gl_PointCoord - 0.5) * 2.0;
    if (r > 1.0) discard;
    #include <logdepthbuf_fragment>
    gl_FragColor = vec4(tone, strength * (1.0 - smoothstep(0.08, 1.0, r)));
    #include <colorspace_fragment>
  }
`

function starAttributes(radius: number, count: number, seed: number) {
  const random = () => {
    seed = (Math.imul(1664525, seed) + 1013904223) >>> 0
    return seed / 4294967296
  }
  const position = new Float32Array(count * 3)
  const tone = new Float32Array(count * 3)
  const shape = new Float32Array(count * 2)
  const palette = ['#b6c8df', '#e9eef7', '#f0ddc5'].map(value => new Color(value))
  for (let i = 0; i < count; i++) {
    const y = random() * 2 - 1
    const angle = random() * Math.PI * 2
    const ring = Math.sqrt(1 - y * y)
    position.set([ring * Math.cos(angle) * radius, y * radius, ring * Math.sin(angle) * radius], i * 3)
    palette[Math.floor(random() * palette.length)].toArray(tone, i * 3)
    const magnitude = random() ** 3
    shape.set([1.2 + 2.9 * magnitude, .24 + .59 * magnitude], i * 2)
  }
  return [new BufferAttribute(position, 3), new BufferAttribute(tone, 3), new BufferAttribute(shape, 2)] as const
}

function StarShell({ radius, count, follow, seed }: typeof shells[number]) {
  const [position, tone, shape] = useMemo(() => starAttributes(radius, count, seed), [radius, count, seed])
  const group = useRef<Group>(null)
  const material = useRef<ShaderMaterial>(null)
  const drift = useRef(0)
  const reduced = useMemo(() => matchMedia('(prefers-reduced-motion: reduce)'), [])
  const uniforms = useMemo(() => ({ pixelRatio: { value: 1 } }), [])
  useFrame(({ camera, gl }, delta) => {
    if (!group.current || !material.current) return
    group.current.position.copy(camera.position).multiplyScalar(follow)
    // Demand-driven: let the sky settle when the viewer stops moving.
    if (!reduced.matches) drift.current += Math.min(delta, .04) * .0004
    group.current.rotation.y = drift.current
    material.current.uniforms.pixelRatio.value = gl.getPixelRatio()
  })
  return <group ref={group}>
    <points raycast={() => undefined} frustumCulled={false}>
      <bufferGeometry>
        <primitive attach="attributes-position" object={position} />
        <primitive attach="attributes-starTone" object={tone} />
        <primitive attach="attributes-starShape" object={shape} />
      </bufferGeometry>
      <shaderMaterial ref={material} uniforms={uniforms} vertexShader={vertexShader} fragmentShader={fragmentShader}
        transparent depthWrite={false} toneMapped={false} />
    </points>
  </group>
}

export function DeepSpace() {
  return <>{shells.map(shell => <StarShell key={shell.seed} {...shell} />)}</>
}
