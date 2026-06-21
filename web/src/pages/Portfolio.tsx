import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { StatCard } from '../components/StatCard'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

interface PortfolioData {
  equity: number
  day_pnl: number
  period_return: number
  sharpe: number
  max_dd: number
  win_rate: number
  equity_curve: { date: string; equity: number }[]
  deployments: { id: string; name: string; status: string; pnl: number }[]
  allocation: { strategy: string; pct: number }[]
}

export function PortfolioPage() {
  const { data, isLoading } = useQuery<PortfolioData>({
    queryKey: ['portfolio'],
    queryFn: () => apiFetch('/api/portfolio'),
    refetchInterval: 30000,
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-surface animate-pulse rounded" />
        <div className="grid grid-cols-3 gap-4 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 bg-surface animate-pulse rounded-lg" />
          ))}
        </div>
        <div className="h-64 bg-surface animate-pulse rounded-lg" />
      </div>
    )
  }

  const portfolio = data ?? {
    equity: 100000, day_pnl: 0, period_return: 0, sharpe: 0,
    max_dd: 0, win_rate: 0, equity_curve: [], deployments: [], allocation: [],
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="font-display text-xl text-ink">Portfolio</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total Equity" value={`$${portfolio.equity.toLocaleString()}`} />
        <StatCard
          label="Day P&L"
          value={`${portfolio.day_pnl >= 0 ? '+' : ''}$${portfolio.day_pnl.toLocaleString()}`}
          className={portfolio.day_pnl >= 0 ? 'text-gain' : 'text-loss'}
        />
        <StatCard label="Period Return" value={`${(portfolio.period_return * 100).toFixed(1)}%`} />
        <StatCard label="Sharpe" value={portfolio.sharpe.toFixed(2)} />
        <StatCard label="Max DD" value={`${(portfolio.max_dd * 100).toFixed(1)}%`} />
        <StatCard label="Win Rate" value={`${(portfolio.win_rate * 100).toFixed(0)}%`} />
      </div>

      {portfolio.equity_curve.length > 0 && (
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Equity Curve</h2>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={portfolio.equity_curve}>
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-indigo)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--color-indigo)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--color-faint)" />
              <YAxis tick={{ fontSize: 11 }} stroke="var(--color-faint)" />
              <Tooltip
                contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-hairline)', borderRadius: 8 }}
              />
              <Area type="monotone" dataKey="equity" stroke="var(--color-indigo)" fill="url(#eqGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Active Deployments</h2>
          {portfolio.deployments.length === 0 ? (
            <p className="text-sm text-faint">No active deployments</p>
          ) : (
            <div className="space-y-2">
              {portfolio.deployments.map(d => (
                <div key={d.id} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                  <div>
                    <span className="text-sm text-ink font-medium">{d.name}</span>
                    <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${d.status === 'live' ? 'bg-gain/10 text-gain' : 'bg-amber/10 text-amber'}`}>
                      {d.status}
                    </span>
                  </div>
                  <span className={`font-mono text-sm ${d.pnl >= 0 ? 'text-gain' : 'text-loss'}`}>
                    {d.pnl >= 0 ? '+' : ''}${d.pnl.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Allocation</h2>
          {portfolio.allocation.length === 0 ? (
            <p className="text-sm text-faint">No allocations configured</p>
          ) : (
            <div className="space-y-2">
              {portfolio.allocation.map(a => (
                <div key={a.strategy} className="flex items-center justify-between py-1">
                  <span className="text-sm text-ink">{a.strategy}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-inset rounded-full overflow-hidden">
                      <div className="h-full bg-indigo rounded-full" style={{ width: `${a.pct}%` }} />
                    </div>
                    <span className="font-mono text-xs text-muted w-10 text-right">{a.pct}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
