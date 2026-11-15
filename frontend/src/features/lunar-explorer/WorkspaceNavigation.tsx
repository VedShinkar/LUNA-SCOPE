import { CalendarClock, ClipboardList, FileText, GitCompare, Globe2, LayoutGrid, Mountain, Radio, ScanLine, Sun } from 'lucide-react'
import { GlassSurface, LiquidGlassButton } from '../../components/ui/liquid-glass'
import type { MapPoint } from '../../services/terrain'

const destinations = [
  { id:'overview', name:'Overview', icon:LayoutGrid },
  { id:'terrain', name:'Terrain analysis', icon:Mountain },
  { id:'celestial', name:'Celestial geometry', icon:Globe2 },
  { id:'illumination', name:'Solar illumination', icon:Sun },
  { id:'communication', name:'Earth visibility', icon:Radio },
  { id:'operations', name:'Operations timeline', icon:CalendarClock },
  { id:'comparison', name:'Terrain comparison', icon:GitCompare },
  { id:'intelligence', name:'Mission Intelligence', icon:ClipboardList },
  { id:'scenarios', name:'Scenario comparison', icon:GitCompare },
  { id:'copilot', name:'Mission Copilot', icon:ScanLine },
  { id:'reports', name:'Reports and history', icon:FileText },
] as const

export type WorkspaceId = typeof destinations[number]['id']
export type ScienceSelection = {
  initialSite: string
  initialPoint?: MapPoint | null
  onSelection: (siteId:string, point:MapPoint|null) => void
  onEpoch?: (utc:string)=>void
}

export function WorkspaceNavigation({ active, onSelect }: {active:WorkspaceId;onSelect:(page:WorkspaceId)=>void}) {
  return <GlassSurface as="nav" className="workspace-navigation" aria-label="Site analysis workspaces">
    <div className="workspace-navigation-list">
      {destinations.map(({id,name,icon:Icon}) => <LiquidGlassButton key={id} label={name} icon={<Icon/>}
        aria-current={active===id?'page':undefined}
        onClick={()=>onSelect(id)}/>)}
    </div>
  </GlassSurface>
}
