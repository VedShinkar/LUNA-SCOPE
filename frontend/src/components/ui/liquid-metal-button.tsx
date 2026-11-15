import { ArrowUpRight } from 'lucide-react'
import { useEffect, useRef, type ButtonHTMLAttributes, type MouseEvent, type ReactNode } from 'react'
import type { ShaderMount } from '@paper-design/shaders'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { label: string; icon?: ReactNode; iconOnly?: boolean; shader?: boolean }

// The Paper shader is mounted only for a featured action, never for every list row.
export function LiquidMetalButton({ label, icon = <ArrowUpRight size={16} />, iconOnly = false, shader = true,
  type = 'button', className = '', disabled, onClick, ...rest }: Props) {
  const layer = useRef<HTMLSpanElement>(null)
  const mount = useRef<ShaderMount | null>(null)
  const ripple = useRef<Animation | null>(null)
  const rippleElement = useRef<HTMLSpanElement>(null)
  const engaged = useRef({ hover: false, focus: false })
  const sync = () => mount.current?.setSpeed(document.hidden || matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 :
    engaged.current.hover || engaged.current.focus ? .7 : 0)
  useEffect(() => {
    const host = layer.current
    if (!host || !shader || disabled) return
    let cancelled = false
    let initialized: ShaderMount | undefined
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    function fallback() { host?.removeAttribute('data-shader'); initialized?.dispose(); initialized = undefined; mount.current = null }
    import('@paper-design/shaders').then(({ ShaderMount, liquidMetalFragmentShader, getShaderColorFromString }) => {
      if (cancelled) return
      try {
        initialized = new ShaderMount(host, liquidMetalFragmentShader, {
          u_colorBack: getShaderColorFromString('#141e2a'), u_colorTint: getShaderColorFromString('#c7e4f6'),
          u_repetition: 3.4, u_softness: .44, u_shiftRed: .02, u_shiftBlue: .11, u_distortion: .08,
          u_contour: .25, u_angle: 42, u_scale: 7, u_shape: 0, u_isImage: false,
        }, {alpha: true, antialias: false}, 0, 650, 1, 22000)
        mount.current = initialized
        if (host.querySelector('canvas')) host.dataset.shader = 'ready'
        sync()
      } catch { host.replaceChildren(); fallback() }
    }).catch(() => fallback())
    host.addEventListener('webglcontextlost', fallback, true)
    document.addEventListener('visibilitychange', sync)
    media.addEventListener('change', sync)
    return () => {
      cancelled = true
      host.removeEventListener('webglcontextlost', fallback, true)
      document.removeEventListener('visibilitychange', sync)
      media.removeEventListener('change', sync)
      fallback()
    }
  }, [shader, disabled])
  useEffect(() => () => ripple.current?.cancel(), [])

  function activate(event: MouseEvent<HTMLButtonElement>) {
    const node = rippleElement.current
    if (node && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const rect = event.currentTarget.getBoundingClientRect()
      node.style.left = `${event.detail ? event.clientX - rect.left : rect.width / 2}px`
      node.style.top = `${event.detail ? event.clientY - rect.top : rect.height / 2}px`
      ripple.current?.cancel()
      ripple.current = node.animate([
        { transform: 'translate(-50%,-50%) scale(.25)', opacity: .6 },
        { transform: 'translate(-50%,-50%) scale(8)', opacity: 0 },
      ], { duration: 540, easing: 'ease-out' })
    }
    onClick?.(event)
  }
  return <button {...rest} type={type} disabled={disabled} aria-label={rest['aria-label'] ?? (iconOnly ? label : undefined)}
    className={`obs-button metal-action ${className}`} onClick={activate}
    onPointerEnter={event => { engaged.current.hover = event.pointerType !== 'touch'; sync(); rest.onPointerEnter?.(event) }}
    onPointerLeave={event => { engaged.current.hover = false; sync(); rest.onPointerLeave?.(event) }}
    onFocus={event => { engaged.current.focus = true; sync(); rest.onFocus?.(event) }}
    onBlur={event => { engaged.current.focus = false; sync(); rest.onBlur?.(event) }}>
    <span ref={layer} className="metal-shader" aria-hidden="true" />
    <span className="metal-ripple-clip" aria-hidden="true"><span ref={rippleElement} /></span>
    <span className="metal-label">{!iconOnly && label}{icon && <span aria-hidden="true">{icon}</span>}</span>
  </button>
}
