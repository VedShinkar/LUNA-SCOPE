import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'

type GlassButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string
  icon?: ReactNode
  iconOnly?: boolean
}

export function LiquidGlassButton({ label, icon, iconOnly, className = '', type = 'button', children, ...props }: GlassButtonProps) {
  return <button {...props} type={type} title={props.title ?? label} aria-label={props['aria-label'] ?? label}
    className={`glass-control ${className}`} data-icon-only={iconOnly || undefined}>
    {icon && <span className="glass-icon" aria-hidden="true">{icon}</span>}
    {!iconOnly && <span className="glass-label">{label}</span>}{children}
  </button>
}

export function LiquidGlassDock({ className = '', ...props }: HTMLAttributes<HTMLElement>) {
  return <nav {...props} className={`glass-surface glass-dock ${className}`} />
}

export function GlassSurface({ as:Element = 'section', className = '', onPointerMove, ...props }: HTMLAttributes<HTMLElement> & {
  as?: 'nav' | 'section' | 'aside' | 'div'
}) {
  return <Element {...props} className={`glass-surface reactive-glass ${className}`}
    onPointerMove={event=>{
      onPointerMove?.(event)
      if (event.pointerType !== 'mouse' || !window.matchMedia('(prefers-reduced-motion: no-preference)').matches) return
      const surface = event.currentTarget
      const bounds = surface.getBoundingClientRect()
      surface.style.setProperty('--glass-x', `${event.clientX-bounds.left}px`)
      surface.style.setProperty('--glass-y', `${event.clientY-bounds.top}px`)
    }}/>
}
