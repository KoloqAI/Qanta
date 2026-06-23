import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, apiMutate } from '../../lib/api'
import { useNavigate } from 'react-router-dom'
import { ActivityFeed } from './ActivityFeed'
import { useJobStream } from '../../hooks/useJobStream'
import { useToast } from '../../hooks/useToast'
import { useState } from 'react'

interface ArchetypeDetail {
  id: string
  name: string
  family: string
  horizon: string
  thesis: string
  status: string
  source: string
  exclusion_reason?: string
  watches?: string[]
  param_grid: Record<string, unknown>
  scan: Record<string, unknown>
  template: Record<string, unknown>
  exploration_funnel: {
    runs: number
    total_trials: number
    total_survivors: number
  }
}

interface ArchetypePanelProps {
  archetypeId: string
  onClose: () => void
}

function statusBadge(status: string) {
  const cls =
    status === 'has-live'
      ? 'bg-gain/20 text-gain font-medium'
      : status === 'has-survivors'
        ? 'bg-gain/10 text-gain'
        : status === 'explored'
          ? 'bg-indigo/10 text-indigo'
          : status === 'excluded'
            ? 'bg-loss/10 text-loss'
            : 'bg-surface text-muted'
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded ${cls}`}>
      {status}
    </span>
  )
}

function humanizeScan(scan: Record<string, unknown>): string {
  if (scan.all_of && Array.isArray(scan.all_of)) {
    return (scan.all_of as Record<string, unknown>[])
      .map(c => humanizeScan(c))
      .join('\nAND ')
  }
  if (scan.any_of && Array.isArray(scan.any_of)) {
    return (scan.any_of as Record<string, unknown>[])
      .map(c => humanizeScan(c))
      .join('\nOR ')
  }
  const entries = Object.entries(scan)
  if (entries.length === 1) {
    const [op, args] = entries[0]
    if (Array.isArray(args)) {
      if (args.length === 2) return `${args[0]} ${op} ${args[1]}`
      if (args.length === 3) return `${args[1]} ≤ ${args[0]} ≤ ${args[2]}`
    }
  }
  return JSON.stringify(scan)
}

export function ArchetypePanel({ archetypeId, onClose }: ArchetypePanelProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [jobId, setJobId] = useState<string | null>(null)
  const stream = useJobStream(jobId)

  const { data, isLoading, isError } = useQuery<ArchetypeDetail>({
    queryKey: ['library', archetypeId],
    queryFn: async () => apiFetch(`/api/library/${archetypeId}`),
  })

  const scanMut = useMutation({
    mutationFn: () =>
      apiMutate<{ job_id: string }>(
        `/api/library/${archetypeId}/scan`,
        {},
      ),
    onSuccess: (res) => {
      setJobId(res.job_id)
      toast('Scan started', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const exploreMut = useMutation({
    mutationFn: () =>
      apiMutate<{ job_id: string; status: string }>(
        `/api/library/${archetypeId}/explore`,
        { budget: 10 },
      ),
    onSuccess: (res) => {
      setJobId(res.job_id)
      queryClient.invalidateQueries({ queryKey: ['library', archetypeId] })
      toast('Exploration sweep queued', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const BTN =
    'px-3 py-1.5 rounded-lg text-xs font-medium transition disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-indigo focus-visible:ring-offset-1'

  /* ---- Loading skeleton ---- */
  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-hairline">
          <div className="h-5 w-32 bg-inset animate-pulse rounded" />
          <button
            onClick={onClose}
            className="text-muted hover:text-ink text-lg leading-none"
            aria-label="Close panel"
          >
            &times;
          </button>
        </div>
        <div className="flex-1 p-4 space-y-3">
          <div className="h-4 w-48 bg-inset animate-pulse rounded" />
          <div className="h-4 w-full bg-inset animate-pulse rounded" />
          <div className="h-20 bg-inset animate-pulse rounded" />
          <div className="h-4 w-2/3 bg-inset animate-pulse rounded" />
        </div>
      </div>
    )
  }

  /* ---- Error state ---- */
  if (isError || !data) {
    return (
      <div className="flex flex-col h-full">
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-hairline">
          <span className="text-sm text-muted">Archetype detail</span>
          <button
            onClick={onClose}
            className="text-muted hover:text-ink text-lg leading-none"
            aria-label="Close panel"
          >
            &times;
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <p className="text-sm text-loss">Failed to load archetype detail</p>
        </div>
      </div>
    )
  }

  const a = data

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-hairline bg-surface">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-sm text-ink font-medium truncate">
              {a.name}
            </h2>
            {statusBadge(a.status)}
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-inset text-faint shrink-0">
              {a.horizon}
            </span>
          </div>
          <span className="text-[10px] text-faint">{a.family}</span>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-ink text-lg leading-none shrink-0 ml-2 focus-visible:ring-2 focus-visible:ring-indigo rounded"
          aria-label="Close panel"
        >
          &times;
        </button>
      </div>

      {/* Scrollable info */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="p-4 space-y-4">
          {/* Exclusion warning */}
          {a.status === 'excluded' && (
            <div className="rounded-lg border border-loss/30 bg-loss/5 p-3 flex items-start gap-2">
              <span className="text-loss mt-0.5 shrink-0">&#9888;</span>
              <div>
                <p className="text-xs text-loss font-medium">
                  Excluded from exploration
                </p>
                <p className="text-[10px] text-muted">
                  {a.exclusion_reason ?? 'Unknown reason'}
                </p>
              </div>
            </div>
          )}

          {/* Thesis */}
          <div>
            <h3 className="text-[10px] text-muted uppercase tracking-wider mb-1">
              Thesis
            </h3>
            <p className="text-sm text-ink">{a.thesis}</p>
          </div>

          {/* Watched features */}
          {a.watches && a.watches.length > 0 && (
            <div>
              <h3 className="text-[10px] text-muted uppercase tracking-wider mb-1">
                Watched features
              </h3>
              <div className="flex flex-wrap gap-1">
                {a.watches.map(w => (
                  <span
                    key={w}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-inset text-muted font-mono"
                  >
                    {w}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Scan logic */}
          <div>
            <h3 className="text-[10px] text-muted uppercase tracking-wider mb-1">
              Scan logic
            </h3>
            <pre className="bg-inset rounded-lg p-3 text-[11px] font-mono text-ink overflow-x-auto whitespace-pre-wrap">
              {humanizeScan(a.scan)}
            </pre>
          </div>

          {/* Param grid */}
          <div>
            <h3 className="text-[10px] text-muted uppercase tracking-wider mb-1">
              Param grid
            </h3>
            <div className="bg-inset rounded-lg p-3 overflow-x-auto">
              <table className="text-[11px] w-full">
                <tbody>
                  {Object.entries(a.param_grid).map(([key, val]) => (
                    <tr
                      key={key}
                      className="border-b border-hairline last:border-0"
                    >
                      <td className="py-1 pr-3 text-muted font-mono">
                        {key}
                      </td>
                      <td className="py-1 text-ink font-mono">
                        {typeof val === 'object'
                          ? JSON.stringify(val)
                          : String(val)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Exploration funnel */}
          <div>
            <h3 className="text-[10px] text-muted uppercase tracking-wider mb-1">
              Exploration funnel
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {(
                [
                  ['Runs', a.exploration_funnel.runs],
                  ['Trials', a.exploration_funnel.total_trials],
                  ['Survivors', a.exploration_funnel.total_survivors],
                ] as const
              ).map(([label, count]) => (
                <div
                  key={label}
                  className="bg-inset rounded-lg p-2.5 text-center"
                >
                  <div className="font-mono text-sm text-ink">{count}</div>
                  <div className="text-[10px] text-muted">{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div className="shrink-0 border-t border-hairline bg-surface px-4 py-3">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              setJobId(null)
              scanMut.mutate()
            }}
            disabled={scanMut.isPending}
            className={`${BTN} bg-indigo text-white hover:bg-indigo/90`}
          >
            {scanMut.isPending ? 'Scanning...' : 'Run scan'}
          </button>
          <button
            onClick={() => {
              setJobId(null)
              exploreMut.mutate()
            }}
            disabled={exploreMut.isPending}
            className={`${BTN} border border-indigo text-indigo hover:bg-indigo/5`}
          >
            {exploreMut.isPending ? 'Queuing...' : 'Explore'}
          </button>
          <button
            onClick={() =>
              navigate('/assistant', {
                state: {
                  seedArchetype: {
                    id: a.id,
                    name: a.name,
                    thesis: a.thesis,
                    family: a.family,
                    template: a.template,
                  },
                },
              })
            }
            className={`${BTN} border border-hairline text-ink hover:bg-inset`}
          >
            Author from this
          </button>
          <button
            onClick={() =>
              navigate('/backtest', {
                state: { preselectedArchetypeId: archetypeId },
              })
            }
            className={`${BTN} border border-hairline text-ink hover:bg-inset`}
          >
            Open in Sandbox
          </button>
        </div>
      </div>

      {/* Activity feed */}
      <ActivityFeed
        events={stream.events}
        status={stream.status}
        error={stream.error}
      />
    </div>
  )
}
