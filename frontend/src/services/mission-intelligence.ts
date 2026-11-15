import type { Observer } from './celestial'
import type { MissionProfile, MissionTimeline } from './mission'

export type DecisionTime = {utc?:string;start_utc?:string;end_utc?:string;step_seconds:number}
export type Equipment = {name:string;minimum_antenna_elevation_deg:number}
export type DecisionPoint = {easting_m:number;northing_m:number}
export type Scenario = {site_id:string;point:DecisionPoint|null;profile:MissionProfile;equipment:Equipment|null}
export type DecisionRequest = Scenario & DecisionTime
export type DecisionContext = Partial<DecisionTime> & {profile?:MissionProfile;equipment?:Equipment|null}
export type DecisionAction = 'assessment'|'terrain'|'solar'|'earth'|'timeline'|'compare_sites'

type Criterion = {
  criterion:string;score:number|null;weight:number;data_status:string;value:number|null;units:string|null;notes:string[]
}
type Evidence = {
  data_status:string;summary?:Record<string,unknown>;provenance:Record<string,unknown>
  quality_flags?:string[];error:string|null;elevation_m?:number|null;slope_deg?:number|null;roughness_15m_m?:number|null
}
export type DecisionResult = {
  request:DecisionRequest;observer:Observer;effective_profile:MissionProfile
  assessment:{assessment_label:string;overall_data_status:string;preliminary_score:number|null
    criteria:Criterion[];missing_criteria:string[];quality_notes:string[]
    terrain:Evidence|null;illumination:Evidence|null;communication:Evidence|null}
  contributions:Record<string,number|null>;operational_screen:string;limitations:string[]
  timeline:Pick<MissionTimeline,'start_utc'|'end_utc'|'summary'|'terrain'|'celestial'|'quality_flags'|'classification_rules'>|null
  snapshot:Record<string,unknown>|null
}
export type ScenarioComparison = {
  scenarios:{name:string;result:DecisionResult|null;unavailable:string|null}[]
  ranked_groups:string[][];explanations:string[]
  differences:{baseline:string;scenario:string;changes:string[];score_delta:number|null}[]
}
export type CopilotResult = {
  action:DecisionAction;context:DecisionRequest;observer:Observer|null
  response:{evidence?:Record<string,unknown>;limitations?:string[];missing_inputs?:string[];data_statuses?:Record<string,string>;copilot_note?:string}|null
  assessment:DecisionResult|null;comparison:ScenarioComparison|null;missing_inputs:string[]
}

async function post<T>(route:string, body:object, signal:AbortSignal):Promise<T> {
  const response = await fetch(`/terrain/explorer/mission-intelligence/${route}`,{
    method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(body),
  })
  if (!response.ok) {
    const error = await response.json().catch(()=>null)
    const detail = error?.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(item=>item.msg).join(' ') : ''
    throw new Error(message || `Mission service unavailable (HTTP ${response.status}).`)
  }
  return response.json()
}

export const assessMission = (request:DecisionRequest, signal:AbortSignal) => post<DecisionResult>('assessment',request,signal)
export const compareScenarios = (request:DecisionTime & {scenarios:(Scenario & {name:string})[]}, signal:AbortSignal) =>
  post<ScenarioComparison>('compare',request,signal)
export const askMissionCopilot = (request:DecisionRequest & {action:DecisionAction}, signal:AbortSignal) =>
  post<CopilotResult>('copilot',request,signal)
