export type Status = 'ok' | 'needs_review' | 'excluded'

export interface Drawing {
  id: string
  number: number
  label: string
  filename: string
  status: Status
  review_reasons: string[]
  approved_with_reasons?: string[]
  exclude_reason: string
  has_inkmap: boolean
  synthetic: boolean
  registration: { method: string; corners: number[][] | null; markers_found: number[] }
  quality: Record<string, number>
  work_size: [number, number]
}

export interface Analysis {
  status: 'none' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  step?: string
  done?: number
  total?: number
  log?: string[]
  error?: string
  finished_at?: number
  stale?: boolean
}

export interface Consensus {
  fingerprint: string
  hash: string
  visual_summary: string
  uncertainty: string
  dominant_composition: string
  included_count: number
  composition: Record<string, number>
  features: { key: string; present_count: number; uncertain_count: number; level: string }[]
  approval?: { correction: string }
  observations: { id: string; composition: string; description: string }[]
}
export interface AIVersion {
  id: string; asset: string; sha256: string; fingerprint: string; consensus_hash: string; created_at: number
}
export interface AIRow {
  id: string; number: number; label: string; position: number; rank: number; score: number
  explanation: string; reliable: boolean; tied: boolean
}
export interface AIState {
  job: Analysis & { action?: string; id?: string }
  versions: AIVersion[]
  consensus?: Consensus
  approved_reference?: string
  reference_approved_at?: number
  match?: { ranking: AIRow[]; reference_id: string; reference_hash: string; review_required: boolean; close_match: boolean
    approval?: { winner: string; override: boolean; note: string } }
  fingerprint: string
  stale: boolean
  ready: boolean
}
export interface AIConfig {
  configured: boolean; error?: string; estimated_calls: number; estimate: string; generation_estimate: string; notice: string
  config?: { vision_model: string; image_model: string; match_model: string; batch_size: number }
}

export interface Session {
  id: string
  name: string
  demo: boolean
  created_at: number
  revision: number
  drawings: Record<string, Drawing>
  analysis: Analysis
  result_mode: 'legacy' | 'ai'
  ai: AIState
  counts: { total: number; ok: number; needs_review: number; excluded: number }
  analysis_stale: boolean
}

export interface SessionSummary { id: string; name: string; demo: boolean; created_at: number; drawings: number }

export interface RankRow {
  id: string
  number: number
  label: string
  position: number
  rank: number
  distance: number
  tied: boolean
  components?: number[]
  registration?: string
  approved_with_reasons?: string[]
}

export interface Results {
  mode?: 'ai' | 'legacy'
  algorithm_version: string
  n_included: number
  winner: string
  most_deviant: string
  ranking: RankRow[]
  excluded: { id: string; number: number; label: string; reason: string }[]
  config: { sigmas_px: number[]; weights: number[]; canvas: number[] }
  seed: number
  created_at: number
  stale: boolean
  demo: boolean
}

export interface Who { id: string; number: number; label: string }

export type Phase = 'standby' | 'analyzing' | 'composite' | 'search' | 'narrowing' | 'match' | 'result'

export interface PresentationView {
  session_id: string
  demo: boolean
  mode: 'standby' | 'analyzing' | 'show'
  phase: Phase
  paused: boolean
  phase_elapsed: number
  phase_duration: number | null
  n?: number
  n_uploaded?: number
  result_key?: string
  result_mode?: 'ai' | 'legacy'
  reference_asset?: string
  fragments?: Who[]
  explanation?: string
  analysis?: Analysis
  stages?: { asset: string; count: number; added: Who }[]
  order?: Who[]
  candidates?: Who[]
  shortlist?: Who[]
  winner?: Who
  winner_tied?: boolean
  top?: (Who & RankRow)[]
  most_deviant?: Who & RankRow
  gallery?: (Who & RankRow)[]
  excluded_count?: number
  method?: { algorithm_version: string; sigmas_px?: number[]; weights?: number[]; canvas: number[]; description?: string }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: {} }
  if (body instanceof FormData) init.body = body
  else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json' }
  }
  const r = await fetch(url, init)
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new ApiError(r.status, data.error ?? `HTTP ${r.status}`)
  return data as T
}

const s = (id: string) => `/api/sessions/${encodeURIComponent(id)}`

export const api = {
  aiConfig: (count: number) => req<AIConfig>('GET', `/api/ai/config?count=${count}`),
  aiCheck: () => req('POST', '/api/ai/check'),
  aiAction: (id: string, action: string, body: Record<string, unknown> = {}) => req('POST', `${s(id)}/ai/${action}`, body),
  listSessions: () => req<SessionSummary[]>('GET', '/api/sessions'),
  createSession: (name: string, demo: boolean) => req<Session>('POST', '/api/sessions', { name, demo }),
  getSession: (id: string) => req<Session>('GET', s(id)),
  deleteSession: (id: string) => req('DELETE', s(id)),
  upload: (id: string, files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f, f.name))
    return req<{ added: Drawing[]; errors: { filename: string; error: string }[] }>('POST', `${s(id)}/drawings`, fd)
  },
  demoDrawings: (id: string, count: number, problems: boolean) =>
    req<{ added: Drawing[] }>('POST', `${s(id)}/demo-drawings`, { count, problems }),
  patchDrawing: (id: string, did: string, patch: Record<string, unknown>) =>
    req<Drawing>('PATCH', `${s(id)}/drawings/${did}`, patch),
  analyze: (id: string, startShow: boolean) => req<Analysis>('POST', `${s(id)}/analyze`, { start_show: startShow }),
  results: (id: string) => req<Results>('GET', `${s(id)}/results`),
  presentation: (id: string) => req<PresentationView>('GET', `${s(id)}/presentation`),
  command: (id: string, action: string) => req<PresentationView>('POST', `${s(id)}/presentation`, { action }),
}

export const assetUrl = (sid: string, asset: string, key: string | number = '') =>
  `${s(sid)}/assets/${asset}${key !== '' ? `?k=${encodeURIComponent(String(key))}` : ''}`

export const exportUrl = (sid: string, name: string) => `${s(sid)}/export/${name}`

export const fmtD = (d: number) => d.toExponential(4)

export const statusText = (s: string) => (s === 'ok' ? 'Godkänd' : s === 'needs_review' ? 'Granska' : 'Utesluten')
