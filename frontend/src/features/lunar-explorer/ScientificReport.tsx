import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { getStatistics, type LayerName, type RasterStatistics } from '../../services/terrain'
import type { LunarSite, Profile } from '../../services/lunar'
import { LiquidGlassButton } from '../../components/ui/liquid-glass'
import { layerNames } from './layers'
import { ProfilePlot } from './ProfilePlot'

type ReportRow = { site: LunarSite; layer: LayerName; stats?: RasterStatistics }
export function downloadCsv(rows: unknown[][], filename = 'luna-scope-scientific-analysis.csv') {
  const csv = rows.map(row => row.map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function ScientificReportDialog({ dialog, title, generated, loading = false, onCsv, children }: {
  dialog:RefObject<HTMLDialogElement|null>; title:string; generated:string; loading?:boolean; onCsv:()=>void; children:ReactNode
}) {
  return createPortal(<dialog ref={dialog} className="scientific-report glass-surface" aria-label={title}>
    <header><div className="eyebrow">LUNA-SCOPE · Scientific report</div><h2>{title}</h2><p>{generated} UTC</p></header>
    {children}
    <footer className="history-actions"><LiquidGlassButton label="Export CSV" disabled={loading} onClick={onCsv}/><LiquidGlassButton label="Print / Save PDF" disabled={loading} onClick={()=>window.print()}/><LiquidGlassButton label="Close Report" onClick={()=>dialog.current?.close()}/></footer>
  </dialog>,document.body)
}

export function ReportActions({ title, sites, layer, profile, assumptions, threshold, triggerLabel }: {
  title: string; sites: LunarSite[]; layer: LayerName; profile?: Profile; assumptions?: string; threshold?: number; triggerLabel?: string
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const request = useRef<AbortController>(null)
  const [rows, setRows] = useState<ReportRow[]>([])
  const [generated, setGenerated] = useState('')
  const [loading, setLoading] = useState(false)
  const [images, setImages] = useState<{label:string; url:string}[]>([])
  useEffect(() => () => request.current?.abort(), [])
  async function open() {
    request.current?.abort()
    const abort = new AbortController()
    request.current = abort
    setRows([])
    setGenerated(new Date().toISOString())
    setLoading(!profile)
    const captures: {label:string; url:string}[] = []
    for (const site of sites) {
      const pane = sites.length === 1 ? document.getElementById('terrain-viewport') : document.querySelector(`[data-site="${CSS.escape(site.site_id)}"]`)
      const canvas = pane?.querySelector<HTMLCanvasElement>('canvas[data-engine]')
      if (!canvas?.clientWidth) continue
      canvas.dispatchEvent(new CustomEvent('terrain-report-capture', {detail:{save: (url:string)=>captures.push({label:site.name, url})}}))
    }
    setImages(captures)
    dialog.current?.showModal()
    if (profile) return
    const layers: LayerName[] = sites.length === 1
      ? ['coverage', 'uncertainty', 'elevation_uncertainty'].includes(layer)
        ? ['coverage', 'uncertainty', 'elevation_uncertainty']
        : ['elevation', 'slope', 'roughness', 'coverage', 'uncertainty', 'elevation_uncertainty']
      : [layer]
    const result = await Promise.all(sites.flatMap(site => layers.map(async item => ({site, layer:item,
      stats: await getStatistics(site.site_id, item, abort.signal, item === layer ? threshold : undefined).catch(() => undefined)}))))
    if (!abort.signal.aborted) { setRows(result); setLoading(false) }
  }
  function csv() {
    if (profile) {
      downloadCsv([['site_id','source','sampling','distance_m','elevation_m','latitude_deg','longitude_deg'], ...profile.elevation_m.map((value,i) => [sites[0]?.site_id,profile.source,profile.sampling,profile.distance_along_m?.[i] ?? profile.distance_m*i/Math.max(1,profile.elevation_m.length-1),value,profile.coordinates?.[i]?.latitude,profile.coordinates?.[i]?.longitude])])
      return
    }
    downloadCsv([['site_id','site_name','layer','unit','minimum','mean','maximum','valid','invalid','total','direct_observations','bounds_m','resolution_m','source_raster','source_url','assumptions','generated_utc','screening_threshold','within_threshold','exceeds_threshold'],
      ...rows.map(({site,layer,stats}) => [site.site_id,site.name,layer,stats?.unit,stats?.minimum,stats?.mean,stats?.maximum,stats?.valid,stats?.invalid,stats?.total,stats?.direct,stats?.bounds.join(' / '),stats?.resolution.join(' × '),stats?.file,stats?.source_url,assumptions,generated,stats?.screening?.threshold,stats?.screening?.within,stats?.screening?.exceeds])])
  }
  return <><LiquidGlassButton label={triggerLabel ?? (profile ? 'Profile Report' : 'Scientific Report')} onClick={open} />
    <ScientificReportDialog dialog={dialog} title={title} generated={generated.replace(/Z$/,'')} loading={loading} onCsv={csv}>
      {loading ? <p role="status">Reading native raster statistics…</p> : <>
        {profile ? <><p>{sites[0]?.name} · {profile.source} · {profile.sampling}</p><ProfilePlot profile={profile}/></> :
          <><p>Scope: full native site rasters. Extents differ by site. Statistics exclude masked and nonfinite cells and intersect layer validity with elevation validity.</p>{rows.map(({site,layer,stats}) => <section key={`${site.site_id}:${layer}`}>
            <h3>{site.name} · {site.site_id} · {layerNames[layer]}</h3>
            {site.available && <p>{site.latitude.toFixed(5)}° latitude · {site.longitude.toFixed(5)}° longitude</p>}
            {stats ? <><p>{stats.minimum ?? 'Unavailable'} min · {stats.mean?.toFixed(3) ?? 'Unavailable'} mean · {stats.maximum ?? 'Unavailable'} max · {stats.unit}</p><p>{stats.valid.toLocaleString()} valid / {stats.total.toLocaleString()} cells · {stats.resolution.join(' × ')} m/px. Bounds: {stats.bounds.join(', ')} m (west, south, east, north).</p><p>{stats.source_kind}: {stats.file} · <a href={stats.source_url}>Source product</a></p>{stats.direct !== undefined && <p>{stats.direct.toLocaleString()} cells with one or more LOLA returns.</p>}</> : <p>Analysis incomplete: source raster statistics unavailable.</p>}
            {stats?.screening && <p>{stats.screening.within.toLocaleString()} cells within the configured threshold · {stats.screening.exceeds.toLocaleString()} exceed it · {stats.invalid.toLocaleString()} have insufficient data.</p>}
          </section>)}</>}
        {assumptions && <p>Configured assumptions: {assumptions}. Threshold screening does not establish landing safety.</p>}
        {images.map(image=><figure key={image.label}><img src={image.url} alt={`${image.label} terrain view captured at report generation`} /><figcaption>{image.label} · Active terrain display at report generation</figcaption></figure>)}
      </>}
    </ScientificReportDialog>
  </>
}
