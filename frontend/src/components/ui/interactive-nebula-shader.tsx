import { useFrame, useThree } from '@react-three/fiber'
import { useMemo } from 'react'
import { Color, Vector2 } from 'three'

const vertex = `varying vec2 screen; void main(){ screen = uv; gl_Position = vec4(position.xy, .999, 1.); }`
const fragment = `
  varying vec2 screen;
  uniform vec2 cursor;
  uniform float time, aspect, intensity, opacity, centerDimming;
  uniform vec3 tint;
  float hash(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
  float noise(vec2 p){
    vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f);
    return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+1.),f.x),f.y);
  }
  void main(){
    vec2 p=(screen-.5)*vec2(aspect,1.);
    vec2 q=p*4.3+vec2(time,-time*.5)-cursor*.13;
    q+=vec2(noise(q*.8),noise(q*.9+7.))*1.15;
    float cloud=noise(q)*.56+noise(q*2.1)*.29+noise(q*4.3)*.15;
    float arc=1.-smoothstep(.03,.54,abs(p.y-.21*sin(p.x*1.9)-.15*p.x));
    float openSky=mix(1.,smoothstep(.14,.72,length(p)),centerDimming);
    float grain=(hash(gl_FragCoord.xy)-.5)*.018;
    float veil=clamp((smoothstep(.31,.83,cloud)*arc*openSky+grain)*intensity*opacity,0.,1.);
    gl_FragColor=vec4(mix(vec3(.0015,.003,.007),tint,veil),1.);
    #include <colorspace_fragment>
  }
`

export function InteractiveNebulaShader({ intensity = .88, speed = .035, hue = 213, opacity = .62,
  interactionEnabled = true, centerDimming = .82 }: {
  intensity?: number; speed?: number; hue?: number; opacity?: number; interactionEnabled?: boolean; centerDimming?: number
}) {
  const { size } = useThree()
  const reduced = useMemo(() => matchMedia('(prefers-reduced-motion: reduce)'), [])
  const uniforms = useMemo(() => ({ time: {value: 0}, cursor: {value: new Vector2()}, aspect: {value: 1},
    tint: {value: new Color()}, intensity: {value: 0}, opacity: {value: 0}, centerDimming: {value: 0} }), [])
  useFrame(({ pointer }, delta) => {
    uniforms.aspect.value = size.width / Math.max(1, size.height)
    uniforms.tint.value.setHSL(hue / 360, .57, .24)
    uniforms.intensity.value = intensity
    uniforms.opacity.value = opacity
    uniforms.centerDimming.value = centerDimming
    if (!reduced.matches) uniforms.time.value += Math.min(delta, .05) * speed
    if (interactionEnabled && !reduced.matches) uniforms.cursor.value.lerp(pointer, .13)
    else uniforms.cursor.value.set(0, 0)
  })
  // The existing demand loop animates this only while the scene is already drawing.
  return <mesh name="observatory-nebula" renderOrder={-10} frustumCulled={false} raycast={() => undefined}>
    <planeGeometry args={[2, 2]} />
    <shaderMaterial uniforms={uniforms} vertexShader={vertex} fragmentShader={fragment} depthTest={false} depthWrite={false} toneMapped={false} />
  </mesh>
}
