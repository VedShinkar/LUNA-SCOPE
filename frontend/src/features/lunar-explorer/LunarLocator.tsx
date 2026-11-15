import { useEffect, useRef, useState } from 'react'
import { albedoUrl, type Coordinates, type LunarSite } from '../../services/lunar'
import { polarCoordinates } from '../../visualization/lunar-coordinates'
import type { TerrainGrid } from '../../services/terrain'
import { LiquidGlassButton } from '../../components/ui/liquid-glass'
import { siteCode } from './copy'
import { footprint, locatorPoint } from './survey-tools'

const size=132, radius=61, mid=size/2, rad=Math.PI/180
let texture: ImageData | undefined
export function LunarLocator({sites, siteId, onSite, grid}: {sites:LunarSite[];siteId:string;onSite:(s:LunarSite)=>void;grid?:TerrainGrid}) {
  const [centre,setCentre]=useState<Coordinates>({latitude:-74,longitude:-60})
  const [ready,setReady]=useState(Boolean(texture))
  const [zoom,setZoom]=useState(false)
  const canvas=useRef<HTMLCanvasElement>(null)
  const drag=useRef<{x:number;y:number}|null>(null)
  const site=sites.find(s=>s.site_id===siteId)
  const scale=zoom?radius*8:radius
  useEffect(()=>{
    const p=site?.available?site:site?.reference
    if(p)setCentre({latitude:zoom?p.latitude:-84,longitude:p.longitude})
  },[site,zoom])
  useEffect(()=>{
    if(texture) return
    const image=new Image()
    image.onload=()=>{
      const map=document.createElement('canvas'); map.width=720;map.height=360
      const ctx=map.getContext('2d'); if(!ctx)return
      ctx.drawImage(image,0,0,720,360);texture=ctx.getImageData(0,0,720,360);setReady(true)
    }
    image.src=albedoUrl
    return ()=>{image.onload=null}
  },[])
  useEffect(()=>{
    const ctx=canvas.current?.getContext('2d'); if(!ctx)return
    const frame=ctx.createImageData(size,size), phi=centre.latitude*rad, cp=Math.cos(phi), sp=Math.sin(phi)
    for(let j=0;j<size;j++)for(let i=0;i<size;i++){
      const x=(i-mid)/scale,y=(mid-j)/scale,z2=1-x*x-y*y;if(z2<0)continue
      const z=Math.sqrt(z2), lat=Math.asin(Math.max(-1,Math.min(1,y*cp+z*sp))),lon=Math.atan2(x,z*cp-y*sp)+centre.longitude*rad
      const shade=.78+.22*z, w=(j*size+i)*4
      if(texture){
        const u=Math.floor(((lon/(2*Math.PI)+1.5)%1)*texture.width),v=Math.min(texture.height-1,Math.floor((.5-lat/Math.PI)*texture.height)),k=(v*texture.width+u)*4
        for(let c=0;c<3;c++)frame.data[w+c]=texture.data[k+c]*shade
      }else frame.data.fill(59*shade,w,w+3)
      frame.data[w+3]=255
    }
    ctx.putImageData(frame,0,0)
  },[centre,ready,scale])
  const project=(p:Coordinates)=>locatorPoint(p,centre)
  const xy=(p:{x:number;y:number})=>`${mid+p.x*scale},${mid-p.y*scale}`
  const outline=grid?.sampling.window ? footprint(grid.transform,grid.width,grid.height).map(p=>polarCoordinates(p.easting,p.northing)) : site?.available ? [
    [site.bounds[0],site.bounds[1]],[site.bounds[2],site.bounds[1]],[site.bounds[2],site.bounds[3]],[site.bounds[0],site.bounds[3]],
  ].map(([e,n])=>polarCoordinates(e,n)) : []
  const polygon=outline.map(project)
  const gridLine=(latitude:number)=>Array.from({length:73},(_,i)=>project({latitude,longitude:i*5-180})).map((p,i,a)=>p.depth<0?'':`${i&&a[i-1].depth>=0?'L':'M'}${xy(p)}`).join(' ')
  const rotate=(x:number,y:number)=>setCentre(p=>({longitude:(p.longitude+x+540)%360-180,latitude:Math.max(-90,Math.min(90,p.latitude+y))}))
  return <aside className="glass-surface lunar-locator" aria-label="Lunar locator">
    <div className="locator-heading"><strong>Lunar Locator</strong><button type="button" className="locator-zoom" aria-pressed={zoom} aria-label="Magnify polar locator" onClick={()=>setZoom(v=>!v)}>{zoom?'8×':'1×'}</button></div>
    <div className="locator-disc" tabIndex={0} aria-label="Rotate locator with arrow keys"
      onKeyDown={e=>{const moves:Record<string,number[]>={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,10],ArrowDown:[0,-10]};if(moves[e.key]){e.preventDefault();rotate(moves[e.key][0],moves[e.key][1])}}}
      onPointerDown={e=>{if((e.target as Element).closest('button'))return;drag.current={x:e.clientX,y:e.clientY};e.currentTarget.setPointerCapture(e.pointerId)}}
      onPointerMove={e=>{if(!drag.current)return;rotate((drag.current.x-e.clientX)*.8,(e.clientY-drag.current.y)*.8);drag.current={x:e.clientX,y:e.clientY}}}
      onLostPointerCapture={()=>{drag.current=null}}>
      <canvas ref={canvas} width={size} height={size} aria-hidden="true" />
      <svg viewBox={`0 0 ${size} ${size}`} aria-hidden="true">{[-80,-60,-30,0,30,60].map(lat=><path key={lat} d={gridLine(lat)} />)}{polygon.length===4&&polygon.every(p=>p.depth>=0)&&<polygon vectorEffect="non-scaling-stroke" points={polygon.map(xy).join(' ')} />}</svg>
      {sites.map(s=>{const target=s.available?s:s.reference;if(!target)return null;const p=project(target);if(p.depth<0||Math.abs(p.x*scale)>=mid-4||Math.abs(p.y*scale)>=mid-4)return null;return <button key={s.site_id} className="locator-marker" style={{left:`${(mid+p.x*scale)/size*100}%`,top:`${(mid-p.y*scale)/size*100}%`}} aria-label={`Locate ${s.name}`} title={s.name} aria-pressed={s.site_id===siteId} onClick={()=>onSite(s)} />})}
    </div>
    <div className="locator-sites">{sites.map(s=><LiquidGlassButton key={s.site_id} label={siteCode(s.site_id)} title={s.name} aria-label={`Select ${s.name}`} aria-pressed={s.site_id===siteId} onClick={()=>{const p=s.available?s:s.reference;if(p)setCentre({latitude:zoom?p.latitude:-84,longitude:p.longitude});onSite(s)}} />)}</div>
    <small>{site?.name ?? 'Landing sites'}{grid?.sampling.window ? ' · native window' : ''}</small>
  </aside>
}
