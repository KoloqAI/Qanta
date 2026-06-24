export type JobEventType =
  | 'run_started'
  | 'step_started'
  | 'step_finished'
  | 'tool_result'
  | 'progress'
  | 'run_finished'
  | 'run_error'

export interface ScanCandidate {
  ticker: string
  fit_score: number
  archetype: string
  family: string
}

export interface ExplorationFunnel {
  trials: number
  backtested: number
  validated: number
  survivors: number
}

export interface JobEvent {
  type: JobEventType
  step_id?: string
  label?: string
  status?: 'running' | 'done' | 'failed'
  progress?: { current: number; total: number }
  tool_name?: string
  tool_result?: string
  error?: string
  timestamp: string
  candidates?: ScanCandidate[]
  is_sample_fallback?: boolean
  funnel?: ExplorationFunnel
}

const KNOWN_TYPES: ReadonlySet<string> = new Set<string>([
  'run_started', 'step_started', 'step_finished',
  'tool_result', 'progress', 'run_finished', 'run_error',
  'heartbeat',
])

export function normalizeJobEvent(raw: Record<string, unknown>): JobEvent {
  const type = (raw.type ?? raw.event ?? 'progress') as JobEventType
  if (!KNOWN_TYPES.has(type)) {
    console.warn('[normalizeJobEvent] unmapped event type:', type, raw)
  }
  return {
    type,
    step_id: raw.step_id as string | undefined,
    label: (raw.label ?? raw.message ?? raw.step) as string | undefined,
    status: raw.status as JobEvent['status'],
    progress: raw.progress as JobEvent['progress'],
    tool_name: raw.tool_name as string | undefined,
    tool_result: raw.tool_result as string | undefined,
    error: (raw.error ?? raw.detail) as string | undefined,
    timestamp: (raw.timestamp ?? raw.ts ?? new Date().toISOString()) as string,
    candidates: raw.candidates as JobEvent['candidates'],
    is_sample_fallback: raw.is_sample_fallback as boolean | undefined,
    funnel: raw.funnel as JobEvent['funnel'],
  }
}

export function isTerminal(type: JobEventType): boolean {
  return type === 'run_finished' || type === 'run_error'
}
