import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { ConfidenceBar } from '../components/ConfidenceBar'
import { useNavigate } from 'react-router-dom'

interface PendingStrategy {
  id: string
  name: string
  ticker: string
  thesis: string
  confidence: number
  confidence_lo: number
  confidence_hi: number
  sharpe: number
  pbo: number
  dsr: number
  n_trades: number
}

export function ReviewQueuePage() {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery<PendingStrategy[]>({
    queryKey: ['review-queue'],
    queryFn: () => apiFetch('/api/strategies?status=pending_review'),
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-surface animate-pulse rounded" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-28 bg-surface animate-pulse rounded-lg" />
        ))}
      </div>
    )
  }

  const queue = data ?? []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl text-ink">Review Queue</h1>
        {queue.length > 0 && (
          <span className="px-2 py-1 bg-indigo/10 text-indigo text-sm rounded-lg">{queue.length} pending</span>
        )}
      </div>

      {queue.length === 0 ? (
        <div className="rounded-lg border border-hairline bg-surface p-12 text-center">
          <p className="text-muted">No strategies pending review</p>
          <p className="text-sm text-faint mt-1">Validated strategies will appear here for your approval</p>
        </div>
      ) : (
        <div className="space-y-3">
          {queue.map(s => (
            <button key={s.id} onClick={() => navigate(`/strategy/${s.id}`)}
              className="w-full text-left rounded-lg border border-hairline bg-surface p-4 hover:border-indigo transition">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-display text-sm text-ink">{s.name}</span>
                  <span className="ml-2 font-mono text-xs text-muted">{s.ticker}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted">
                  <span>DSR: {s.dsr.toFixed(2)}</span>
                  <span>PBO: {s.pbo.toFixed(2)}</span>
                  <span>{s.n_trades} trades</span>
                </div>
              </div>
              <p className="text-sm text-muted mb-2 line-clamp-1">{s.thesis}</p>
              <ConfidenceBar C={s.confidence} C_lo={s.confidence_lo} C_hi={s.confidence_hi} threshold={0.5} />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
