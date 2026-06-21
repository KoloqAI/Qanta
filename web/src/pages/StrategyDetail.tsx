import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { ConfidenceBar } from '../components/ConfidenceBar'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useState } from 'react'

interface StrategyData {
  id: string
  name: string
  ticker: string
  version: number
  state: string
  thesis: string
  confidence: number
  confidence_lo: number
  confidence_hi: number
  sharpe: number
  pbo: number
  dsr: number
  max_dd: number
  n_trades: number
  win_rate: number
  net_edge: number
  equity_curve: { date: string; equity: number }[]
  red_team: string[]
  regime_description: string
}

export function StrategyDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'overview' | 'validation' | 'live'>('overview')
  const [reason, setReason] = useState('')

  const { data, isLoading } = useQuery<StrategyData>({
    queryKey: ['strategy', id],
    queryFn: () => apiFetch(`/api/strategies/${id}`),
  })

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 w-64 bg-surface animate-pulse rounded" />
        <div className="h-96 bg-surface animate-pulse rounded-lg" />
      </div>
    )
  }

  const s = data ?? {
    id: '', name: 'Strategy', ticker: '', version: 1, state: 'draft', thesis: '', confidence: 0,
    confidence_lo: 0, confidence_hi: 0, sharpe: 0, pbo: 0, dsr: 0, max_dd: 0, n_trades: 0,
    win_rate: 0, net_edge: 0, equity_curve: [], red_team: [], regime_description: '',
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl text-ink">{s.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="font-mono text-sm text-muted">{s.ticker}</span>
            <span className="text-xs text-faint">v{s.version}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              s.state === 'validated' ? 'bg-gain/10 text-gain' : s.state === 'live' ? 'bg-indigo/10 text-indigo' : 'bg-surface text-muted'
            }`}>{s.state}</span>
          </div>
        </div>
        <button onClick={() => navigate(-1)} className="text-sm text-muted hover:text-ink">&larr; Back</button>
      </div>

      <div className="flex gap-1 border-b border-hairline">
        {(['overview', 'validation', 'live'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize ${tab === t ? 'border-b-2 border-indigo text-ink' : 'text-muted hover:text-ink'}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="space-y-4">
          <div className="rounded-lg border border-hairline bg-surface p-4">
            <h3 className="text-sm text-muted mb-1">Thesis</h3>
            <p className="text-sm text-ink">{s.thesis}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-lg border border-hairline bg-surface p-3">
              <p className="text-xs text-muted">Sharpe</p>
              <p className="font-mono text-lg">{s.sharpe.toFixed(2)}</p>
            </div>
            <div className="rounded-lg border border-hairline bg-surface p-3">
              <p className="text-xs text-muted">Max DD</p>
              <p className="font-mono text-lg">{(s.max_dd * 100).toFixed(1)}%</p>
            </div>
            <div className="rounded-lg border border-hairline bg-surface p-3">
              <p className="text-xs text-muted">Trades</p>
              <p className="font-mono text-lg">{s.n_trades}</p>
            </div>
            <div className="rounded-lg border border-hairline bg-surface p-3">
              <p className="text-xs text-muted">Win Rate</p>
              <p className="font-mono text-lg">{(s.win_rate * 100).toFixed(0)}%</p>
            </div>
          </div>

          {s.equity_curve.length > 0 && (
            <div className="rounded-lg border border-hairline bg-surface p-4">
              <h3 className="text-sm text-muted mb-3">Backtest Equity Curve</h3>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={s.equity_curve}>
                  <defs>
                    <linearGradient id="sdGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-indigo)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--color-indigo)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="var(--color-faint)" />
                  <YAxis tick={{ fontSize: 10 }} stroke="var(--color-faint)" />
                  <Tooltip contentStyle={{ background: 'var(--color-surface)', border: '1px solid var(--color-hairline)', borderRadius: 8, fontSize: 12 }} />
                  <Area type="monotone" dataKey="equity" stroke="var(--color-indigo)" fill="url(#sdGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {tab === 'validation' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <h3 className="font-display text-sm text-muted">Evidence</h3>
            <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
              <ConfidenceBar C={s.confidence} C_lo={s.confidence_lo} C_hi={s.confidence_hi} threshold={0.5} />
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex justify-between"><span className="text-muted">DSR</span>
                  <span className={s.dsr >= 0.95 ? 'text-gain' : 'text-loss'}>{s.dsr.toFixed(3)}</span>
                </div>
                <div className="flex justify-between"><span className="text-muted">PBO</span>
                  <span className={s.pbo <= 0.2 ? 'text-gain' : 'text-loss'}>{s.pbo.toFixed(3)}</span>
                </div>
                <div className="flex justify-between"><span className="text-muted">Net Edge</span>
                  <span className="font-mono">{(s.net_edge * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between"><span className="text-muted">Trades</span>
                  <span className="font-mono">{s.n_trades}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="font-display text-sm text-muted">Counter-Evidence</h3>
            <div className="rounded-lg border border-loss/20 bg-loss/5 p-4">
              {s.red_team.length === 0 ? (
                <p className="text-sm text-muted">No concerns flagged</p>
              ) : (
                <ul className="space-y-2">
                  {s.red_team.map((concern, i) => (
                    <li key={i} className="text-sm text-loss flex items-start gap-2">
                      <span className="mt-0.5">&#9888;</span>{concern}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {s.state === 'validated' && (
            <div className="lg:col-span-2 rounded-lg border border-hairline bg-surface p-4">
              <h3 className="font-display text-sm text-muted mb-3">Decision</h3>
              <textarea value={reason} onChange={e => setReason(e.target.value)}
                placeholder="Reason for decision..."
                className="w-full px-3 py-2 bg-inset border border-hairline rounded-lg text-sm mb-3 resize-none h-20" />
              <div className="flex gap-2 justify-end">
                <button className="px-4 py-2 border border-hairline rounded-lg text-sm text-loss hover:bg-loss/5">Reject</button>
                <button className="px-4 py-2 bg-indigo text-white rounded-lg text-sm hover:bg-indigo/90">Approve &amp; Deploy</button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'live' && (
        <div className="rounded-lg border border-hairline bg-surface p-8 text-center">
          <p className="text-muted">Live monitoring data will appear when this strategy is deployed</p>
        </div>
      )}
    </div>
  )
}
