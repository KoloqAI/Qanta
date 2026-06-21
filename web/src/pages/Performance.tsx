import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ScatterChart, Scatter } from 'recharts'

interface PerformanceData {
  total_return: number
  sharpe: number
  win_rate: number
  history: { date: string; cumulative_return: number }[]
  strategies: { name: string; status: string; return: number; sharpe: number }[]
  calibration: { claimed: number; realized: number }[]
}

export function PerformancePage() {
  const { data, isLoading } = useQuery<PerformanceData>({
    queryKey: ['performance'],
    queryFn: () => apiFetch('/api/performance'),
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-48 bg-surface animate-pulse rounded" />
        <div className="h-64 bg-surface animate-pulse rounded-lg" />
      </div>
    )
  }

  const perf = data ?? { total_return: 0, sharpe: 0, win_rate: 0, history: [], strategies: [], calibration: [] }

  return (
    <div className="p-6 space-y-6">
      <h1 className="font-display text-xl text-ink">Performance &amp; History</h1>

      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <p className="text-xs text-muted">Total Return</p>
          <p className={`font-mono text-lg ${perf.total_return >= 0 ? 'text-gain' : 'text-loss'}`}>
            {(perf.total_return * 100).toFixed(1)}%
          </p>
        </div>
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <p className="text-xs text-muted">Sharpe</p>
          <p className="font-mono text-lg text-ink">{perf.sharpe.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <p className="text-xs text-muted">Win Rate</p>
          <p className="font-mono text-lg text-ink">{(perf.win_rate * 100).toFixed(0)}%</p>
        </div>
      </div>

      {perf.history.length > 0 && (
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Cumulative Return</h2>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={perf.history}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--color-faint)" />
              <YAxis tick={{ fontSize: 11 }} stroke="var(--color-faint)" tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
              <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-hairline)', borderRadius: 8 }} />
              <Line type="monotone" dataKey="cumulative_return" stroke="var(--color-indigo)" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Strategy Track Record</h2>
          {perf.strategies.length === 0 ? (
            <p className="text-sm text-faint">No strategies deployed yet</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted text-xs border-b border-hairline">
                  <th className="text-left py-2">Strategy</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-right py-2">Return</th>
                  <th className="text-right py-2">Sharpe</th>
                </tr>
              </thead>
              <tbody>
                {perf.strategies.map(s => (
                  <tr key={s.name} className="border-b border-hairline last:border-0">
                    <td className="py-2 text-ink">{s.name}</td>
                    <td className="py-2"><span className="text-xs px-1.5 py-0.5 rounded bg-surface">{s.status}</span></td>
                    <td className={`py-2 text-right font-mono ${s.return >= 0 ? 'text-gain' : 'text-loss'}`}>
                      {(s.return * 100).toFixed(1)}%
                    </td>
                    <td className="py-2 text-right font-mono">{s.sharpe.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-lg border border-hairline bg-surface p-4">
          <h2 className="font-display text-sm text-muted mb-3">Confidence Calibration</h2>
          {perf.calibration.length === 0 ? (
            <p className="text-sm text-faint">No calibration data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <ScatterChart>
                <XAxis dataKey="claimed" domain={[0, 1]} tick={{ fontSize: 11 }} label={{ value: 'Claimed', position: 'bottom', fontSize: 11 }} />
                <YAxis dataKey="realized" domain={[0, 1]} tick={{ fontSize: 11 }} label={{ value: 'Realized', angle: -90, position: 'left', fontSize: 11 }} />
                <Scatter data={perf.calibration} fill="var(--color-indigo)" />
              </ScatterChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}
