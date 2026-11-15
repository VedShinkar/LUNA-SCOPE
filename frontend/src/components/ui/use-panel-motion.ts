import { useGSAP } from '@gsap/react'
import { gsap } from 'gsap'
import type { RefObject } from 'react'

gsap.registerPlugin(useGSAP)

export function usePanelMotion(scope: RefObject<HTMLElement | null>, panel: unknown) {
  useGSAP(() => {
    const media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('[data-enter-panel]', { opacity: 0, y: 6, duration: .24, ease: 'power2.out' })
    })
    return () => media.revert()
  }, { scope, dependencies: [panel], revertOnUpdate: true })
}
