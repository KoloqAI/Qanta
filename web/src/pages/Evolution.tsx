import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'

interface Digest {
  promotions: { name: string; reason: string }[]
  retirements: { name: string; reason: string }[]
  discoveries: { name: string; sharpe: number; passed: boolean }[]
  proposals: { id: string; type: string; name: string; status: string; description: string }[]
  meta_lockbox: { status: string; last_evaluated?: string }
}

export function EvolutionPage() {
  const { data, isLoading } = useQuery<Digest>({
    queryKey: ['evolution'],
    queryFn: () => apiFetch('/api/evolution/digest'),
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-surface animate-pulse rounded" />
        <div className="h-64 bg-surface animate-pulse rounded-lg" />
      </div>
    )
  }

  const digest = data ?? { promotions: [], retirements: [], discoveries: [], proposals: [], meta_lockbox: { status: 'not_evaluated' } }

  return (
    <div className="p-6 space-y-6">
      <h1 className="font-display text-xl text-ink">Evolution</h1>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Promotions</h2>
          {digest.promotions.length === 0 ? (
            <p className="text-sm text-faint">No recent promotions</p>
          ) : (
            <div className="space-y-2">
              {digest.promotions.map((p, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="text-gain">&uarr;</span>
                  <span className="text-ink">{p.name}</span>
                  <span className="text-muted text-xs">{p.reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Retirements</h2>
          {digest.retirements.length === 0 ? (
            <p className="text-sm text-faint">No recent retirements</p>
          ) : (
            <div className="space-y-2">
              {digest.retirements.map((r, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="text-loss">&darr;</span>
                  <span className="text-ink">{r.name}</span>
                  <span className="text-muted text-xs">{r.reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-hairline bg-surface p-4">
        <h2 className="font-display text-sm text-muted mb-3">Tier-3 Proposals</h2>
        {digest.proposals.length === 0 ? (
          <p className="text-sm text-faint">No capability proposals</p>
        ) : (
          <div className="space-y-3">
            {digest.proposals.map(p => (
              <div key={p.id} className="flex items-center justify-between border-b border-hairline pb-2 last:border-0">
                <div>
                  <span className="text-sm text-ink font-medium">{p.name}</span>
                  <span className="ml-2 text-xs text-muted">{p.type}</span>
                  <p className="text-xs text-muted mt-0.5">{p.description}</p>
                </div>
                {p.status === 'pending_approval' ? (
                  <div className="flex gap-1">
                    <button className="text-xs px-2 py-1 bg-gain/10 text-gain rounded hover:bg-gain/20">Approve</button>
                    <button className="text-xs px-2 py-1 bg-loss/10 text-loss rounded hover:bg-loss/20">Reject</button>
                  </div>
                ) : (
                  <span className={`text-xs px-2 py-0.5 rounded ${p.status === 'approved' ? 'bg-gain/10 text-gain' : 'bg-loss/10 text-loss'}`}>
                    {p.status}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-hairline bg-surface p-4">
        <h2 className="font-display text-sm text-muted mb-2">Meta-Lockbox</h2>
        <p className="text-sm text-ink">Status: <span className="font-mono">{digest.meta_lockbox.status}</span></p>
        {digest.meta_lockbox.last_evaluated && (
          <p className="text-xs text-muted mt-1">Last evaluated: {digest.meta_lockbox.last_evaluated}</p>
        )}
      </div>
    </div>
  )
}
