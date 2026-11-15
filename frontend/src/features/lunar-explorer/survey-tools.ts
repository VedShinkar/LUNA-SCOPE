import type { Coordinates, Profile } from '../../services/lunar.ts'
import type { Affine, MapPoint, TerrainPoint, LayerName } from '../../services/terrain.ts'

const rad = Math.PI / 180
export function locatorPoint(point: Coordinates, centre: Coordinates) {
  const phi = point.latitude * rad, theta = centre.latitude * rad, delta = (point.longitude - centre.longitude) * rad
  return { x: Math.cos(phi) * Math.sin(delta), y: Math.sin(phi) * Math.cos(theta) - Math.cos(phi) * Math.cos(delta) * Math.sin(theta), depth: Math.sin(phi) * Math.sin(theta) + Math.cos(phi) * Math.cos(delta) * Math.cos(theta) }
}
export function footprint(transform: Affine, width: number, height: number): MapPoint[] {
  const [a,b,c,d,e,f] = transform
  return [[0,0],[width,0],[width,height],[0,height]].map(([x,y]) => ({easting:a*x+b*y+c,northing:d*x+e*y+f}))
}
export function nativeCell([a,b,c,d,e,f]: Affine, p: MapPoint) {
  const x=p.easting-c, y=p.northing-f, det=a*e-b*d
  return {row:Math.floor((a*y-d*x)/det), col:Math.floor((e*x-b*y)/det)}
}
export const cameraPresets = ['Global Moon', 'South Polar Overview', 'Selected Landing Site', 'Terrain Close-up', 'Overhead Inspection'] as const
export type CameraPreset = typeof cameraPresets[number]
export const layerPresets = [
  {name:'Terrain Overview', layers:['elevation']},
  {name:'Slope Assessment', layers:['slope','nasa_slope']},
  {name:'Data Quality', layers:['coverage','elevation_uncertainty','uncertainty']},
  {name:'Landing Assessment', layers:['hazards','elevation','slope','roughness','suitability']},
] as const satisfies readonly {name:string; layers: readonly LayerName[]}[]
export type LayerPreset = typeof layerPresets[number]['name']
export function supportedLayers(name: LayerPreset, supports: (layer:LayerName)=>boolean) {
  const layers = layerPresets.find(p=>p.name===name)!.layers as readonly LayerName[]
  return {available:layers.filter(supports), missing:layers.filter(l=>!supports(l))}
}

export type Measurement = {id:string; name:string; siteId:string|null; siteName?:string; timestamp:string; source:string; coordinates:Coordinates[];
  provenance?: { productUrl?:string; sourceFile?:string; crs?:string; resolution?:[number, number]; sampling?:string }
} & (
  {kind:'Terrain sample'; projected:MapPoint; values:TerrainPoint} | {kind:'Elevation profile'; values:Profile}
)
export function removeMeasurement(records: Measurement[], id: string) { return records.filter(item => item.id !== id) }
export function measurementCsv(records: Measurement[]) {
  const safe = (v: unknown) => `"${String(v ?? '').replaceAll('"','""')}"`
  const rows: unknown[][] = [['id','name','type','site_id','timestamp_utc','dataset','latitude_deg','longitude_deg','easting_m','northing_m','quantity','value','unit','sample_index','along_path_m']]
  for (const r of records) {
    const base = [r.id, /^[=+\-@\t\r\n]/.test(r.name) ? `'${r.name}` : r.name,r.kind,r.siteId,r.timestamp,r.source]
    if (r.kind === 'Terrain sample') {
      const p=r.values, q=p.uncertainty_and_observation
      for (const [key,val,unit] of [['elevation',p.elevation_m,'m'],['slope',p.slope_deg,'deg'],['aspect',p.aspect_deg,'deg'],['roughness_15m',p.roughness.roughness_15m_m,'m'],['roughness_35m',p.roughness.roughness_35m_m,'m'],['roughness_75m',p.roughness.roughness_75m_m,'m'],['observation_count',q.lola_observation_count,'returns'],['elevation_uncertainty',q.elevation_uncertainty_m_rms,'m RMS'],['slope_uncertainty',q.slope_uncertainty_deg_rms,'deg RMS']] as const) {
        rows.push([...base,r.coordinates[0].latitude,r.coordinates[0].longitude,r.projected.easting,r.projected.northing,key,val,unit])
      }
    } else {
      r.coordinates.forEach((p,i)=>rows.push([...base,p.latitude,p.longitude,null,null,i===0?'start':i===r.coordinates.length-1?'end':'vertex',null,null]))
      rows.push([...base,null,null,null,null,'surface_distance',r.values.distance_m,'m'])
      r.values.elevation_m.forEach((v,i,a)=>rows.push([...base,r.values.coordinates?.[i]?.latitude,r.values.coordinates?.[i]?.longitude,r.values.projected?.[i]?.easting,r.values.projected?.[i]?.northing,'elevation',v,'m',i,r.values.distance_along_m?.[i] ?? r.values.distance_m*i/Math.max(1,a.length-1)]))
    }
  }
  return rows.map(row=>Array.from({length:15},(_,i)=>safe(row[i])).join(',')).join('\r\n')
}
