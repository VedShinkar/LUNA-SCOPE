import type { MapPoint } from '../../services/terrain'

export type WorkspaceObserver = { siteId:string; point:MapPoint } | null

export function pointForSite(observer:WorkspaceObserver, siteId:string): MapPoint|null {
  return observer?.siteId === siteId ? observer.point : null
}
