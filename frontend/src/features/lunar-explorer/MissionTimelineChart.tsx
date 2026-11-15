import { useId } from 'react'
import type { MissionTimeline } from '../../services/mission'
import { conditionLabel, epoch, missionColors, trackNames, trackOrder, trackTone } from '../../visualization/mission-display'

export type TimeBounds = [number,number]

export function MissionTimelineChart({ timeline, bounds, cursor, onPick, compact=false }: {
  timeline:MissionTimeline; bounds?:TimeBounds; cursor?:number; onPick?:(time:number)=>void; compact?:boolean
}) {
  const pattern = useId()
  const [start,end] = bounds ?? [epoch(timeline.start_utc),epoch(timeline.end_utc)]
  const width = compact ? 480 : 900
  const left = 147
  const right = width-18
  const x = (time:number) => left+(time-start)/(end-start)*(right-left)
  const ticks = Array.from({length:compact?3:5},(_,index)=>start+(end-start)*index/(compact?2:4))
  return <div className={`mission-chart-wrap ${compact?'compact':''}`} tabIndex={!compact?0:undefined}
    role={!compact?'region':undefined} aria-label={!compact?'Scrollable UTC tracks':undefined}>
    <svg className="mission-chart" viewBox={`0 0 ${width} 205`} role="img" aria-label={`${timeline.site_id} five-track UTC timeline`}>
      <defs>
        <pattern id={`${pattern}-unknown`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V6" stroke="#263447" strokeWidth="2"/></pattern>
        <pattern id={`${pattern}-invalid`} width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 0L6 6M6 0L0 6" stroke="#9aa5b3" strokeWidth=".75"/></pattern>
      </defs>
      {ticks.map((time,index)=>{
        const iso = new Date(time).toISOString()
        return <g key={time}>
          <path d={`M${x(time)} 18V167`} className="mission-chart-grid"/>
          <text x={x(time)} y="181" textAnchor={index===0?'start':index===ticks.length-1?'end':'middle'}>{iso.slice(5,10)} {iso.slice(11,19)}</text>
        </g>
      })}
      {trackOrder.map((track,index)=>{
        const y = 20+index*29
        return <g key={track}>
          <text x="6" y={y+14} className={track==='mission'?'mission-chart-key':''}>{trackNames[track]}</text>
          <rect x={left} y={y} width={right-left} height="21" fill="#233047" rx="2"/>
          {timeline.intervals.map(row=>{
            const low = Math.max(start,epoch(row.start_utc))
            const high = Math.min(end,epoch(row.end_utc))
            if (high<=low) return null
            const state = row.tracks[track]
            const tone = trackTone(state)
            return <g key={row.start_utc} onClick={onPick?()=>onPick(low+(high-low)/2):undefined}>
              <rect x={x(low)} y={y} width={x(high)-x(low)} height="21" fill={missionColors[tone]}>
                <title>{trackNames[track]} · {conditionLabel(state)} · {row.start_utc} to {row.end_utc}</title>
              </rect>
              {(tone==='unresolved'||tone==='invalid') && <rect x={x(low)} y={y} width={x(high)-x(low)} height="21"
                fill={`url(#${pattern}-${tone==='unresolved'?'unknown':'invalid'})`} pointerEvents="none"/>}
            </g>
          })}
        </g>
      })}
      {cursor!==undefined && cursor>=start && cursor<=end && <path d={`M${x(cursor)} 13V167`} stroke="#f1f7fb" strokeWidth="1.4" pointerEvents="none"/>}
      <text x={right} y="198" textAnchor="end">UTC</text>
    </svg>
  </div>
}
