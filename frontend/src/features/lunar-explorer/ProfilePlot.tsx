import type { Profile } from '../../services/lunar'
import { useMemo, useState } from 'react'

export function ProfilePlot({ profile, onSample, activeSample }: { profile: Profile; onSample?: (index:number)=>void; activeSample?:number }) {
  const [active,setActive]=useState(0)
  const heights = profile.elevation_m.filter(value => value != null)
  const units = profile.distance_m >= 1000 ? `${(profile.distance_m / 1000).toLocaleString(undefined, { maximumFractionDigits: 2 })} km`
    : `${profile.distance_m.toFixed(1)} m`
  const lo = Math.min(...heights), hi = Math.max(...heights)
  const count=profile.elevation_m.length
  const distance=(i:number)=>profile.distance_along_m?.[i] ?? profile.distance_m*i/Math.max(1,count-1)
  const x=(i:number)=>42+190*(profile.distance_m ? distance(i)/profile.distance_m : 0)
  const y=(v:number)=>73-61*(v-lo)/(hi-lo||1)
  const index=Math.min(activeSample ?? active,Math.max(0,count-1)), value=profile.elevation_m[index]
  const path = useMemo(()=>profile.elevation_m.map((height, index, values) => height == null ? '' :
    `${index && values[index - 1] != null ? 'L' : 'M'}${x(index)},${y(height)}`
  ).join(' '),[profile])
  const select = (i:number) => {setActive(i);onSample?.(i)}
  const end = profile.elevation_m.at(-1), start = profile.elevation_m[0]
  const interval = index ? distance(index) - distance(index-1) : 0
  const previous = profile.elevation_m[index-1]
  const gradient = interval > 0 && previous != null && value != null ? Math.atan2(value-previous, interval) * 180 / Math.PI : null
  const coordinate = profile.coordinates?.[index]
  return <div className="profile-result">
    <div className="profile-distance">{units} <small>surface distance</small></div>
    <p className="muted">{heights.length}/{count} valid samples{profile.max_interval_m && ` · ≤ ${profile.max_interval_m} m spacing`}{heights.length > 0 && ` · ${lo.toFixed(1)} to ${hi.toFixed(1)} m · range ${(hi-lo).toFixed(1)} m`}{start != null && end != null && ` · net change ${(end-start).toFixed(1)} m`}</p>
    {heights.length ? <>
      <svg viewBox="0 0 240 103" role="img" aria-label="Elevation in metres by surface distance" onPointerMove={event=>{
        const rect=event.currentTarget.getBoundingClientRect()
        const target=(event.clientX-rect.left)/rect.width*240
        let lo=0, hi=count-1
        while(lo<hi){const mid=(lo+hi)>>1;if(x(mid)<target)lo=mid+1;else hi=mid}
        select(lo>0 && Math.abs(x(lo-1)-target)<Math.abs(x(lo)-target) ? lo-1 : lo)
      }}>
        <path d="M42 12 V73 H232" stroke="#46586b" /><path d={path} fill="none" stroke="#85dce3" strokeWidth="1.6" />
        <g fill="#a5b9cd" fontSize="8" fontFamily="monospace"><text x="1" y="13">{Math.round(hi)} m</text><text x="1" y="74">{Math.round(lo)} m</text><text x="42" y="88">0 m</text><text x="232" y="88" textAnchor="end">{units}</text></g>
        {[0,count-1].map((i,k)=>profile.elevation_m[i]!=null&&<circle key={k} cx={x(i)} cy={y(profile.elevation_m[i]!)} r="2.7" fill="#d6faff"/>)}
        <path d={`M${x(index)} 12V73`} stroke="#9cb6cd" strokeDasharray="2 2"/>{value!=null&&<circle cx={x(index)} cy={y(value)} r="3" fill="#f3dcac"/>}
      </svg>
      <input type="range" aria-label="Profile sample" min="0" max={count-1} value={index} onChange={e=>select(Number(e.target.value))}/>
      <p className="muted">{distance(index).toFixed(1)} m along path · {value==null?'NoData':`${value.toLocaleString(undefined,{maximumFractionDigits:2})} m elevation`}{coordinate && ` · ${coordinate.latitude.toFixed(5)}°, ${coordinate.longitude.toFixed(5)}°`}{gradient !== null && ` · Profile gradient ${gradient.toFixed(1)}°`}</p>
    </> : <p className="muted">The path has no valid elevation samples.</p>}
    <p className="muted">{profile.source} · {profile.sampling}</p>
  </div>
}
