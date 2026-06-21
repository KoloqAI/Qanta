import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { StatCard } from '../components/StatCard'

interface Deployment {
  id: string
  name: string
  mode: 'paper' | 'live'
  status: string
  pnl: number
  positions: { symbol: string; qty: number; pnl: number }[]
  guardrail_health: 'ok' | 'warning' | 'critical'
}

interface MonitorData {
  account_pnl: number
  gross_exposure: number
  kill_switch: boolean
  deployments: Deployment[]
}

export function MonitorPage() {
  const { data, isLoading } = useQuery<MonitorData>({
    queryKey: ['monitor'],
    queryFn: () => apiFetch('/api/monitor'),
    refetchInterval: 5000,
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-surface animate-pulse rounded" />
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 bg-surface animate-pulse rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  const monitor = data ?? { account_pnl: 0, gross_exposure: 0, kill_switch: false, deployments: [] }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl text-ink">Monitor</h1>
        {monitor.kill_switch && (
          <span className="px-3 py-1 bg-loss/10 text-loss text-sm font-medium rounded-lg animate-pulse">
            KILL SWITCH ACTIVE
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard
          label="Account P&L"
          value={`${monitor.account_pnl >= 0 ? '+' : ''}$${monitor.account_pnl.toLocaleString()}`}
          className={monitor.account_pnl >= 0 ? 'text-gain' : 'text-loss'}
        />
        <StatCard label="Gross Exposure" value={`$${monitor.gross_exposure.toLocaleString()}`} />
        <StatCard
          label="Kill Switch"
          value={monitor.kill_switch ? 'ACTIVE' : 'Ready'}
          className={monitor.kill_switch ? 'text-loss' : 'text-gain'}
        />
      </div>

      <div className="space-y-4">
        {monitor.deployments.length === 0 ? (
          <div className="rounded-lg border border-hairline bg-surface p-8 text-center">
            <p className="text-sm text-muted">No active deployments</p>
          </div>
        ) : (
          monitor.deployments.map(dep => (
            <div key={dep.id} className="rounded-lg border border-hairline bg-surface p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <h3 className="font-display text-sm text-ink">{dep.name}</h3>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${dep.mode === 'live' ? 'bg-gain/10 text-gain' : 'bg-amber/10 text-amber'}`}>
                    {dep.mode}
                  </span>
                  <span className={`w-2 h-2 rounded-full ${
                    dep.guardrail_health === 'ok' ? 'bg-gain' : dep.guardrail_health === 'warning' ? 'bg-amber' : 'bg-loss'
                  }`} />
                </div>
                <div className="flex gap-2">
                  <button className="text-xs px-2 py-1 border border-hairline rounded hover:bg-surface transition">Pause</button>
                  <button className="text-xs px-2 py-1 border border-hairline rounded hover:bg-surface transition text-loss">Flatten</button>
                </div>
              </div>

              <div className="flex items-center gap-6 text-sm">
                <span className={`font-mono ${dep.pnl >= 0 ? 'text-gain' : 'text-loss'}`}>
                  P&L: {dep.pnl >= 0 ? '+' : ''}${dep.pnl.toLocaleString()}
                </span>
                <span className="text-muted">{dep.positions.length} positions</span>
              </div>

              {dep.positions.length > 0 && (
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-muted border-b border-hairline">
                        <th className="text-left py-1">Symbol</th>
                        <th className="text-right py-1">Qty</th>
                        <th className="text-right py-1">P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dep.positions.map(p => (
                        <tr key={p.symbol} className="border-b border-hairline last:border-0">
                          <td className="py-1 font-mono text-ink">{p.symbol}</td>
                          <td className="py-1 text-right font-mono">{p.qty}</td>
                          <td className={`py-1 text-right font-mono ${p.pnl >= 0 ? 'text-gain' : 'text-loss'}`}>
                            {p.pnl >= 0 ? '+' : ''}${p.pnl.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
