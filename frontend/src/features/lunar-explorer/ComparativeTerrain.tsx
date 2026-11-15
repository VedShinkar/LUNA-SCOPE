import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { getGrid, getStatistics, type LayerName, type RasterStatistics, type TerrainGrid } from '../../services/terrain'
import type { LunarSite } from '../../services/lunar'
import TerrainScene, { type CameraLink, type RelativeCamera, type Hit } from '../../visualization/TerrainScene'
import { layerBand, layerNames, layerStyle, sampleLabel } from './layers'
import { siteCode } from './copy'
import { ReportActions } from './ScientificReport'

const comparisonLayers: LayerName[] = ['elevation', 'slope', 'roughness', 'coverage', 'elevation_uncertainty', 'uncertainty', 'suitability', 'roughness_screen']
const noop = () => {}
const fmt = (n: number | null) => n === null ? '—' : n.toLocaleString(undefined, {maximumFractionDigits: 2})
const cells = (count: number, valid: number) => valid ? `${fmt(count)} · ${fmt(100 * count / valid)}% of valid cells` : fmt(count)

class MeshBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <p role="alert">Terrain rendering unavailable on this device.</p> : this.props.children }
}

function SitePanel({ site, grid, error, stats, layer, link, range, visible, slopeLimit, roughnessLimit }: {
  site: LunarSite; grid?: TerrainGrid; error?: string; stats?: RasterStatistics; layer: LayerName;
  link: CameraLink; range?: [number, number]; visible: boolean
  slopeLimit: number; roughnessLimit: number
}) {
  const [hit, setHit] = useState<Hit | null>(null)
  const [camera, setCamera] = useState<number>(0)
  const coords = site.available ? site : site.reference
  const band = grid && layerBand(grid, layer)
  const legend = grid && band && layerStyle(grid, layer, slopeLimit, range, 'default', roughnessLimit)
  return <article className="comparison-site" data-mobile-active={visible} data-site={site.site_id}>
    <header><div className="eyebrow">{siteCode(site.site_id)}</div><h2>{site.name}</h2>
      <p>{coords ? `${coords.latitude.toFixed(5)}°, ${coords.longitude.toFixed(5)}°` : 'Coordinates unavailable'}{grid && ` · ${grid.source_resolution.join(' × ')} m/px native`}</p></header>
    <div className="comparison-viewport" data-heading={camera.toFixed(3)}>
      {grid && band ? <MeshBoundary><TerrainScene grid={grid} layer={layer} threshold={slopeLimit} roughnessThreshold={roughnessLimit} exaggeration={1} contours={false} reset={0}
        selected={null} onHover={noop} onSelect={setHit} onHeading={setCamera} cameraLink={link} colorRange={range} /></MeshBoundary> :
        <p role="status">{error ?? (grid ? `${layerNames[layer]} unavailable. ${grid.unavailable[layer] ?? 'No verified raster.'}` : 'Loading terrain…')}</p>}
    </div>
    {legend && <div className="comparison-legend" aria-label={`${site.name} legend`}>
      {legend.labels.map((label, i) => <span key={i}><i style={{background: legend.colors[i] ?? legend.colors.at(-1)}} />{label}</span>)}<span>NoData · gray or gaps</span>
    </div>}
    {grid && <p>{grid.resolution.join(' × ')} m display spacing · <a href={grid.source_url}>NASA LOLA provenance</a></p>}
    {grid && hit && <p>Display sample · {sampleLabel(layer, band?.values[hit.index], slopeLimit, roughnessLimit)} · E {fmt(hit.easting)} m · N {fmt(hit.northing)} m</p>}
    {stats && stats.layer !== layer && <p>Statistics below describe the underlying {layerNames[stats.layer].toLowerCase()} raster.</p>}
    {stats && <><dl className="comparison-metrics"><div><dt>Minimum</dt><dd>{fmt(stats.minimum)} {stats.unit}</dd></div><div><dt>Mean</dt><dd>{fmt(stats.mean)} {stats.unit}</dd></div><div><dt>Maximum</dt><dd>{fmt(stats.maximum)} {stats.unit}</dd></div><div><dt>Valid / total</dt><dd>{fmt(stats.valid)} / {fmt(stats.total)} · {fmt(100*stats.valid/stats.total)}%</dd></div><div><dt>Invalid</dt><dd>{fmt(stats.invalid)}</dd></div>{stats.direct !== undefined && <div><dt>Cells with direct returns</dt><dd>{fmt(stats.direct)}{stats.direct_percent != null && ` · ${fmt(stats.direct_percent)}% of valid cells`}</dd></div>}</dl><p>{stats.file} · {stats.width} × {stats.height} cells</p></>}
    {stats?.screening && <dl className="comparison-metrics">
      <div><dt>Within configured threshold</dt><dd>{cells(stats.screening.within, stats.valid)}</dd></div>
      <div><dt>Exceeds configured threshold</dt><dd>{cells(stats.screening.exceeds, stats.valid)}</dd></div>
    </dl>}
    {stats?.histogram && <details><summary>Slope distribution</summary>{stats.histogram.counts.map((count,i)=><p key={i}>{stats.histogram!.edges[i]}–{stats.histogram!.edges[i+1]}° · {fmt(count)} cells</p>)}{stats.histogram.outside > 0 && <p>Outside histogram range · {fmt(stats.histogram.outside)} cells</p>}</details>}
  </article>
}

export function ComparativeTerrain({ sites }: { sites: LunarSite[] }) {
  const [layer, setLayer] = useState<LayerName>('elevation')
  const [slopeLimit, setSlopeLimit] = useState(15)
  const [roughnessLimit, setRoughnessLimit] = useState(2)
  const statsLayer = layer === 'suitability' ? 'slope' : layer === 'roughness_screen' ? 'roughness' : layer
  const threshold = layer === 'suitability' ? slopeLimit : layer === 'roughness_screen' ? roughnessLimit : undefined
  const [active, setActive] = useState('Site04')
  const [linked, setLinked] = useState(true)
  const linkedRef = useRef(true)
  const receivers = useRef(new Map<string, (state: RelativeCamera) => void>())
  const latest = useRef<RelativeCamera | undefined>(undefined)
  const frame = useRef<number>(0)
  const [grids, setGrids] = useState<Record<string, TerrainGrid>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [stats, setStats] = useState<Record<string, RasterStatistics>>({})
  const [missingStats, setMissingStats] = useState<string[]>([])
  const links = useMemo(() => Object.fromEntries(sites.map(site => {
    const id = site.site_id
    const link: CameraLink = {
      subscribe(receive) {
        receivers.current.set(id, receive)
        if (linkedRef.current && latest.current) receive(latest.current)
        return () => { receivers.current.delete(id) }
      },
      publish(state) {
        if (!linkedRef.current) return
        latest.current = state
        cancelAnimationFrame(frame.current)
        frame.current = requestAnimationFrame(() => {
          if (linkedRef.current) receivers.current.forEach((receive, other) => { if (other !== id) receive(state) })
        })
      },
    }
    return [id, link]
  })), [sites])
  useEffect(() => () => cancelAnimationFrame(frame.current), [])
  useEffect(() => {
    const abort = new AbortController()
    sites.forEach(site => {
      getGrid(site.site_id, 128, abort.signal).then(grid => {
        if (!abort.signal.aborted) setGrids(old => ({...old, [site.site_id]:grid}))
      }).catch(error => { if (!abort.signal.aborted) setErrors(old => ({...old,[site.site_id]:error.message})) })
    })
    return () => abort.abort()
  }, [sites])
  useEffect(() => {
    const abort = new AbortController()
    setStats({})
    setMissingStats([])
    const pending = setTimeout(() => {
      sites.forEach(site => {
        getStatistics(site.site_id, statsLayer, abort.signal, threshold).then(result => {
          if (!abort.signal.aborted) setStats(old => ({...old,[site.site_id]:result}))
        }).catch(() => { if (!abort.signal.aborted) setMissingStats(old => [...old, site.site_id]) })
      })
    }, threshold === undefined ? 0 : 350)
    return () => { clearTimeout(pending); abort.abort() }
  }, [statsLayer, sites, threshold])
  const range = useMemo<[number,number] | undefined>(() => {
    if (layer !== 'elevation') return
    const ranges = Object.values(grids).flatMap(grid => grid.elevation.range ? [grid.elevation.range] : [])
    if (ranges.length) return [Math.min(...ranges.map(r=>r[0])), Math.max(...ranges.map(r=>r[1]))]
  }, [grids, layer])
  return <section className="comparative-terrain" aria-label="Comparative Terrain Analysis">
    <div className="comparison-controls">
      <label>Scientific layer <select value={layer} onChange={event => setLayer(event.target.value as LayerName)}>{comparisonLayers.map(item => <option key={item} value={item}>{layerNames[item]}</option>)}</select></label>
      <label><input type="checkbox" checked={linked} onChange={event => {linkedRef.current = event.target.checked; setLinked(event.target.checked)}} /> Link cameras</label>
      <label className="comparison-mobile-picker">Visible site <select value={active} onChange={e=>setActive(e.target.value)}>{sites.map(item=><option key={item.site_id} value={item.site_id}>{item.name}</option>)}</select></label>
      {layer === 'suitability' && <label>Slope assumption (°) <input type="number" min="0" max="90" value={slopeLimit} onChange={e => setSlopeLimit(Math.max(0, Math.min(90, Number(e.target.value))))} /></label>}
      {layer === 'roughness_screen' && <label>15 m roughness assumption (m) <input type="number" min="0" max="10" step="0.1" value={roughnessLimit} onChange={e => setRoughnessLimit(Math.max(0, Math.min(10, Number(e.target.value))))} /></label>}
      <ReportActions title="Three-site comparison" sites={sites} layer={statsLayer} threshold={threshold} assumptions={layer === 'suitability' ? `Slope ≤ ${slopeLimit}°` : layer === 'roughness_screen' ? `15 m roughness ≤ ${roughnessLimit} m` : undefined} />
    </div>
    <p className="muted">Statistics use each site’s full native raster extent and exclude masked or nonfinite cells. Extents differ. Color scales are shared. Terrain previews are decimated.</p>
    {missingStats.length > 0 && <p role="status">Native statistics unavailable for {missingStats.map(siteCode).join(', ')}.</p>}
    <div className="comparison-panels">{sites.map(site => {
      const result = stats[site.site_id]
      const current = result?.layer === statsLayer && result.screening?.threshold === threshold
      return <SitePanel key={site.site_id} site={site} grid={grids[site.site_id]} stats={current ? result : undefined} error={errors[site.site_id]} layer={layer} link={links[site.site_id]} range={range} visible={site.site_id===active} slopeLimit={slopeLimit} roughnessLimit={roughnessLimit} />
    })}</div>
  </section>
}
