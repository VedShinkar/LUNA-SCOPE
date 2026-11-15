import { ArrowUpRight, Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { LiquidGlassButton } from './ui/liquid-glass'

export type Command = { label: string; group: string; run: () => void; keywords?: string }

export function CommandPalette({ commands, open, onOpen, onSearch }: {
  commands: Command[]
  open: boolean
  onOpen: (open: boolean) => void
  onSearch?: (query: string) => boolean
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [coordinateError, setCoordinateError] = useState(false)
  const matches = commands.filter(command => `${command.label} ${command.group} ${command.keywords ?? ''}`
    .toLowerCase().includes(query.trim().toLowerCase()))
  const coordinate = Boolean(onSearch && query.includes(','))

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        onOpen(!open)
      }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [open, onOpen])

  useEffect(() => {
    if (open && !dialog.current?.open) {
      setQuery('')
      setActive(0)
      setCoordinateError(false)
      dialog.current?.showModal()
      input.current?.focus()
    } else if (!open && dialog.current?.open) dialog.current.close()
  }, [open])

  function run(command?: Command) {
    if (command) { command.run(); onOpen(false) }
    else if (onSearch?.(query)) onOpen(false)
    else if (coordinate) setCoordinateError(true)
  }

  return <dialog ref={dialog} className="observatory-panel command-palette" aria-label="Command palette"
    onCancel={event => { event.preventDefault(); onOpen(false) }}
    onClick={event => { if (event.target === dialog.current) onOpen(false) }}>
    <form onSubmit={event => { event.preventDefault(); run(matches[active]) }}>
      <div className="command-input"><Search size={18} />
        <input ref={input} aria-label="Find a location or analysis tool" value={query} placeholder="Site name, coordinates, layer, or tool"
          onChange={event => { setQuery(event.target.value); setActive(0); setCoordinateError(false) }}
          onKeyDown={event => {
            if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
            event.preventDefault()
            const next = Math.max(0, Math.min(matches.length - 1, active + (event.key === 'ArrowDown' ? 1 : -1)))
            setActive(next)
            dialog.current?.querySelectorAll('.command-result')[next]?.scrollIntoView({ block: 'nearest' })
          }} />
        <LiquidGlassButton label="Close Search" iconOnly icon={<X />} onClick={() => onOpen(false)} />
      </div>
      <div className="command-results">
        {matches.map((command, index) => <button className="command-result" type="button" key={command.label}
          data-active={index === active} onClick={() => run(command)}>
          <span>{command.label}</span><small>{command.group}</small><ArrowUpRight size={14} />
        </button>)}
        {!matches.length && (coordinate ? <button className="command-result" type="submit">Fly to coordinates <ArrowUpRight size={14} /></button> :
          <p className="muted">No sites, layers, or tools match this query.</p>)}
        {coordinateError && <p className="muted" role="alert">Enter latitude (−90 to 90), then longitude (−180 to 180), in decimal degrees.</p>}
      </div>
      <footer><span><kbd>↑</kbd> <kbd>↓</kbd> Navigate</span><span><kbd>Enter</kbd> Select</span><span><kbd>Esc</kbd> Close</span></footer>
    </form>
  </dialog>
}
