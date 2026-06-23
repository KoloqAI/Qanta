import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, apiMutate } from '../../lib/api'
import { useNavigate } from 'react-router-dom'
import { ConfidenceBar } from '../ConfidenceBar'
import { ActivityFeed } from './ActivityFeed'
import { useJobStream } from '../../hooks/useJobStream'
import { useToast } from '../../hooks/useToast'
import { useState } from 'react'

interface StrategyData {
  id: string
  name: string
  ticker: string
  version: number
  state: string
  confidence: number
  confidence_lo: number
  confidence_hi: number
  sharpe: number
  dsr: number
  pbo: number
  peer_hit?: number
  max_dd: number
  n_trades: number
  deployment: {
    id: string
    mode: 'paper' | 'live'
    status: string
  } | null
  validation_stale: boolean
  stale_reason: string | null
}

interface StrategyPanelProps {
  strategyId: string
  onClose: () => void
}

const BTN =
  'px-3 py-1.5 rounded-lg text-xs font-medium transition disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-indigo focus-visible:ring-offset-1'
const BTN_GHOST =
  'px-3 py-1.5 border border-hairline rounded-lg text-xs transition disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-indigo focus-visible:ring-offset-1'

export function StrategyPanel({ strategyId, onClose }: StrategyPanelProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [jobId, setJobId] = useState<string | null>(null)
  const stream = useJobStream(jobId)

  const { data, isLoading, isError } = useQuery<StrategyData>({
    queryKey: ['strategy', strategyId],
    queryFn: async () => apiFetch(`/api/strategies/${strategyId}`),
  })

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['strategy', strategyId] })
    queryClient.invalidateQueries({ queryKey: ['registry'] })
  }

  const validateMut = useMutation({
    mutationFn: () =>
      apiMutate<{ job_id: string }>(
        `/api/strategies/${strategyId}/validate`,
      ),
    onSuccess: (res) => {
      setJobId(res.job_id)
      invalidateAll()
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const approveMut = useMutation({
    mutationFn: (reason: string) =>
      apiMutate(`/api/strategies/${strategyId}/approve`, {
        approved: true,
        reason,
      }),
    onSuccess: () => {
      invalidateAll()
      toast('Approved', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const rejectMut = useMutation({
    mutationFn: (reason: string) =>
      apiMutate(`/api/strategies/${strategyId}/approve`, {
        approved: false,
        reason,
      }),
    onSuccess: () => {
      invalidateAll()
      toast('Rejected', 'info')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const promoteMut = useMutation({
    mutationFn: () =>
      apiMutate(`/api/deployments/${data?.deployment?.id}/promote`),
    onSuccess: () => {
      invalidateAll()
      toast('Promoted to live', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const pauseMut = useMutation({
    mutationFn: () =>
      apiMutate(`/api/deployments/${data?.deployment?.id}/pause`),
    onSuccess: () => {
      invalidateAll()
      toast('Paused', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const flattenMut = useMutation({
    mutationFn: () =>
      apiMutate(`/api/deployments/${data?.deployment?.id}/flatten`),
    onSuccess: () => {
      invalidateAll()
      toast('Flattened', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const retireMut = useMutation({
    mutationFn: () =>
      apiMutate(`/api/deployments/${data?.deployment?.id}/retire`),
    onSuccess: () => {
      invalidateAll()
      toast('Retired', 'info')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

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
        </div>
      </div>
    )
  }

  /* ---- Error state ---- */
  if (isError || !data) {
    return (
      <div className="flex flex-col h-full">
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-hairline">
          <span className="text-sm text-muted">Strategy detail</span>
          <button
            onClick={onClose}
            className="text-muted hover:text-ink text-lg leading-none"
            aria-label="Close panel"
          >
            &times;
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <p className="text-sm text-loss">Failed to load strategy detail</p>
        </div>
      </div>
    )
  }

  const s = data
  const dep = s.deployment

  const stateChipCls =
    s.state === 'live'
      ? 'bg-gain/10 text-gain'
      : s.state === 'paper'
        ? 'bg-indigo/10 text-indigo'
        : s.state === 'validated'
          ? 'bg-gain/10 text-gain'
          : s.state === 'approved'
            ? 'bg-indigo/10 text-indigo'
            : s.state === 'rejected'
              ? 'bg-loss/10 text-loss'
              : 'bg-surface text-muted'

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-hairline bg-surface">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-sm text-ink font-medium truncate">
              {s.name}
            </h2>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${stateChipCls}`}
            >
              {s.state}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="font-mono text-xs text-muted">{s.ticker}</span>
            <span className="text-[10px] text-faint">v{s.version}</span>
          </div>
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
          {/* Key validation metrics */}
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ['DSR', s.dsr != null ? s.dsr.toFixed(3) : '--'],
                ['PBO', s.pbo != null ? s.pbo.toFixed(3) : '--'],
                [
                  'Peer Hit',
                  s.peer_hit != null ? s.peer_hit.toFixed(3) : '--',
                ],
                [
                  'C_lo',
                  s.confidence_lo != null
                    ? `${(s.confidence_lo * 100).toFixed(1)}%`
                    : '--',
                ],
              ] as const
            ).map(([label, val]) => (
              <div key={label} className="bg-inset rounded-lg p-2.5">
                <p className="text-[10px] text-muted">{label}</p>
                <p className="font-mono text-sm text-ink">{val}</p>
              </div>
            ))}
          </div>

          {/* Confidence bar */}
          {s.confidence != null && s.confidence > 0 && (
            <ConfidenceBar
              C={s.confidence}
              C_lo={s.confidence_lo}
              C_hi={s.confidence_hi}
              threshold={0.5}
              label="Deflated confidence"
            />
          )}

          {/* Deployment chip */}
          {dep && (
            <div className="flex items-center gap-2">
              <span
                className={`text-xs px-1.5 py-0.5 rounded ${
                  dep.mode === 'live'
                    ? 'bg-gain/10 text-gain'
                    : 'bg-indigo/10 text-indigo'
                }`}
              >
                {dep.mode}
              </span>
              <span className="text-xs text-muted">{dep.status}</span>
            </div>
          )}

          {/* Deep link */}
          <button
            onClick={() => navigate(`/strategy/${strategyId}`)}
            className="text-xs text-indigo hover:underline focus-visible:ring-2 focus-visible:ring-indigo rounded"
          >
            Open full Strategy Detail &rarr;
          </button>
        </div>
      </div>

      {/* Action bar — pinned between info and feed */}
      <div className="shrink-0 border-t border-hairline bg-surface px-4 py-3">
        {/* draft / backtested → Validate */}
        {(s.state === 'draft' || s.state === 'backtested') && (
          <button
            onClick={() => validateMut.mutate()}
            disabled={validateMut.isPending}
            className={`${BTN} bg-indigo text-white hover:bg-indigo/90`}
          >
            {validateMut.isPending ? 'Validating...' : 'Run Validation'}
          </button>
        )}

        {/* validated (fresh) → Approve & Deploy / Reject */}
        {s.state === 'validated' && !s.validation_stale && (
          <div className="flex gap-2">
            <button
              onClick={() => {
                if (
                  window.confirm(
                    'Risk-increasing: approve this strategy and open deployment config?',
                  )
                )
                  approveMut.mutate('')
              }}
              disabled={approveMut.isPending}
              className={`${BTN} bg-indigo text-white hover:bg-indigo/90`}
            >
              {approveMut.isPending ? 'Approving...' : 'Approve & Deploy'}
            </button>
            <button
              onClick={() => rejectMut.mutate('')}
              disabled={rejectMut.isPending}
              className={`${BTN_GHOST} text-loss hover:bg-loss/5`}
            >
              {rejectMut.isPending ? 'Rejecting...' : 'Reject'}
            </button>
          </div>
        )}

        {/* validated (stale) → Re-validate */}
        {s.state === 'validated' && s.validation_stale && (
          <div className="space-y-2">
            <p className="text-[10px] text-loss">
              Stale validation — {s.stale_reason}
            </p>
            <button
              onClick={() => validateMut.mutate()}
              disabled={validateMut.isPending}
              className={`${BTN} bg-indigo text-white hover:bg-indigo/90`}
            >
              {validateMut.isPending ? 'Re-validating...' : 'Re-validate'}
            </button>
          </div>
        )}

        {/* approved → Deploy Config (opens full detail page) */}
        {s.state === 'approved' && !dep && (
          <button
            onClick={() => navigate(`/strategy/${strategyId}`)}
            className={`${BTN} bg-indigo text-white hover:bg-indigo/90`}
          >
            Deploy Config
          </button>
        )}

        {/* paper deployment → Promote / Pause / Flatten / Retire */}
        {dep?.mode === 'paper' && dep.status === 'active' && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                if (
                  window.confirm(
                    'Risk-increasing: promote this deployment to live trading?',
                  )
                )
                  promoteMut.mutate()
              }}
              disabled={promoteMut.isPending}
              className={`${BTN} bg-indigo text-white hover:bg-indigo/90`}
            >
              {promoteMut.isPending ? 'Promoting...' : 'Promote'}
            </button>
            <button
              onClick={() => pauseMut.mutate()}
              disabled={pauseMut.isPending}
              className={`${BTN_GHOST} text-ink hover:bg-inset`}
            >
              Pause
            </button>
            <button
              onClick={() => flattenMut.mutate()}
              disabled={flattenMut.isPending}
              className={`${BTN_GHOST} text-ink hover:bg-inset`}
            >
              Flatten
            </button>
            <button
              onClick={() => retireMut.mutate()}
              disabled={retireMut.isPending}
              className={`${BTN_GHOST} text-loss hover:bg-loss/5`}
            >
              Retire
            </button>
          </div>
        )}

        {/* live deployment → Pause / Flatten / Retire */}
        {dep?.mode === 'live' && dep.status === 'active' && (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => pauseMut.mutate()}
              disabled={pauseMut.isPending}
              className={`${BTN_GHOST} text-ink hover:bg-inset`}
            >
              Pause
            </button>
            <button
              onClick={() => flattenMut.mutate()}
              disabled={flattenMut.isPending}
              className={`${BTN_GHOST} text-ink hover:bg-inset`}
            >
              Flatten
            </button>
            <button
              onClick={() => retireMut.mutate()}
              disabled={retireMut.isPending}
              className={`${BTN_GHOST} text-loss hover:bg-loss/5`}
            >
              Retire
            </button>
          </div>
        )}

        {/* paused → Retire */}
        {dep?.status === 'paused' && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">Paused</span>
            <button
              onClick={() => retireMut.mutate()}
              disabled={retireMut.isPending}
              className={`${BTN_GHOST} text-loss hover:bg-loss/5`}
            >
              Retire
            </button>
          </div>
        )}
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
