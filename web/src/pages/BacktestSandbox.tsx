import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { apiFetch, apiMutate } from '../lib/api'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

type SourceType = 'dsl' | 'archetype' | 'strategy'
type ModeType = 'backtest' | 'full_gauntlet'
type Timeframe = '1d' | '1h' | '15m'

interface LibraryItem {
  id: string
  name: string
}

interface StrategyItem {
  id: string
  name: string
}

interface Trade {
  date: string
  ticker: string
  side: string
  qty: number
  price: number
  pnl: number
}

interface BacktestResult {
  equity_curve: { date: string; equity: number }[]
  trades: Trade[]
  metrics: {
    sharpe: number
    max_dd: number
    net_edge: number
    win_rate: number
    n_trades: number
  }
  gauntlet?: {
    dsr: number
    pbo: number
    passed: boolean
  }
}

export function BacktestSandboxPage() {
  const location = useLocation()
  const navState = location.state as { preselectedArchetypeId?: string } | null

  const [source, setSource] = useState<SourceType>(navState?.preselectedArchetypeId ? 'archetype' : 'dsl')
  const [dslSpec, setDslSpec] = useState('')
  const [archetypeId, setArchetypeId] = useState(navState?.preselectedArchetypeId ?? '')
  const [strategyId, setStrategyId] = useState('')
  const [tickers, setTickers] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [timeframe, setTimeframe] = useState<Timeframe>('1d')
  const [mode, setMode] = useState<ModeType>('backtest')

  const libraryQuery = useQuery<LibraryItem[]>({
    queryKey: ['library'],
    queryFn: () => apiFetch('/api/library'),
    enabled: source === 'archetype',
  })

  const strategiesQuery = useQuery<StrategyItem[]>({
    queryKey: ['strategies-list'],
    queryFn: () => apiFetch('/api/strategies'),
    enabled: source === 'strategy',
  })

  const mutation = useMutation<BacktestResult, Error, void>({
    mutationFn: () => {
      const common = {
        tickers: tickers.split(',').map(t => t.trim()).filter(Boolean),
        start_date: startDate,
        end_date: endDate,
        timeframe,
        mode,
      }

      if (source === 'dsl') {
        return apiMutate('/api/backtest', { source: 'dsl', spec: dslSpec, ...common })
      } else if (source === 'archetype') {
        return apiMutate('/api/backtest', { source: 'archetype', archetype_id: archetypeId, ...common })
      } else {
        return apiMutate('/api/backtest', { source: 'strategy', strategy_id: strategyId, ...common })
      }
    },
  })

  const inputClass =
    'w-full bg-inset border border-hairline rounded px-3 py-2 text-sm text-ink placeholder:text-faint focus:outline-none focus:ring-1 focus:ring-indigo'

  const result = mutation.data

  return (
    <div className="p-6 space-y-6">
      <h1 className="font-display text-xl text-ink">Backtest Sandbox</h1>

      {/* Info banner */}
      <div className="rounded-lg border border-hairline bg-indigo/5 px-4 py-2.5 text-sm text-muted">
        Sandbox results can promote to Research/Registry but never to live.
      </div>

      {/* Source selector */}
      <div className="rounded-lg border border-hairline bg-surface p-4 space-y-4">
        <h2 className="font-display text-sm text-muted">Source</h2>

        <div className="flex gap-6">
          {([
            ['dsl', 'DSL Spec'],
            ['archetype', 'Library Archetype'],
            ['strategy', 'Registry Strategy'],
          ] as [SourceType, string][]).map(([value, label]) => (
            <label key={value} className="flex items-center gap-2 text-sm text-ink cursor-pointer">
              <input
                type="radio"
                name="source"
                value={value}
                checked={source === value}
                onChange={() => setSource(value)}
                className="accent-[var(--color-indigo)]"
              />
              {label}
            </label>
          ))}
        </div>

        {source === 'dsl' && (
          <textarea
            value={dslSpec}
            onChange={e => setDslSpec(e.target.value)}
            placeholder="Enter DSL specification..."
            rows={6}
            className={inputClass}
          />
        )}

        {source === 'archetype' && (
          <select
            value={archetypeId}
            onChange={e => setArchetypeId(e.target.value)}
            className={inputClass}
          >
            <option value="">
              {libraryQuery.isLoading ? 'Loading...' : 'Select archetype'}
            </option>
            {(libraryQuery.data ?? []).map(item => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        )}

        {source === 'strategy' && (
          <select
            value={strategyId}
            onChange={e => setStrategyId(e.target.value)}
            className={inputClass}
          >
            <option value="">
              {strategiesQuery.isLoading ? 'Loading...' : 'Select strategy'}
            </option>
            {(strategiesQuery.data ?? []).map(item => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Inputs section */}
      <div className="rounded-lg border border-hairline bg-surface p-4 space-y-4">
        <h2 className="font-display text-sm text-muted">Inputs</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-muted mb-1">Ticker(s)</label>
            <input
              type="text"
              value={tickers}
              onChange={e => setTickers(e.target.value)}
              placeholder="AAPL, MSFT, GOOG"
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Timeframe</label>
            <select
              value={timeframe}
              onChange={e => setTimeframe(e.target.value as Timeframe)}
              className={inputClass}
            >
              <option value="1d">1d</option>
              <option value="1h">1h</option>
              <option value="15m">15m</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs text-muted mb-1">Mode</label>
          <div className="inline-flex rounded border border-hairline overflow-hidden">
            <button
              type="button"
              onClick={() => setMode('backtest')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                mode === 'backtest'
                  ? 'bg-[var(--color-indigo)] text-white'
                  : 'bg-surface text-muted hover:text-ink'
              }`}
            >
              Backtest Only
            </button>
            <button
              type="button"
              onClick={() => setMode('full_gauntlet')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                mode === 'full_gauntlet'
                  ? 'bg-[var(--color-indigo)] text-white'
                  : 'bg-surface text-muted hover:text-ink'
              }`}
            >
              Full Gauntlet
            </button>
          </div>
        </div>
      </div>

      {/* Run button */}
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="bg-[var(--color-indigo)] text-white rounded px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {mutation.isPending ? 'Running...' : 'Run Backtest'}
      </button>

      {/* Loading skeleton */}
      {mutation.isPending && (
        <div className="space-y-4">
          <div className="h-64 bg-surface animate-pulse rounded-lg" />
          <div className="grid grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-20 bg-surface animate-pulse rounded-lg" />
            ))}
          </div>
          <div className="h-48 bg-surface animate-pulse rounded-lg" />
        </div>
      )}

      {/* Error state */}
      {mutation.isError && (
        <div className="rounded-lg border border-loss/30 bg-loss/5 px-4 py-3 text-sm text-loss">
          {mutation.error.message}
        </div>
      )}

      {/* Results area */}
      {result && (
        <div className="space-y-6">
          {/* Equity curve */}
          <div className="rounded-lg border border-hairline bg-surface p-4">
            <h2 className="font-display text-sm text-muted mb-3">Equity Curve</h2>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={result.equity_curve}>
                <defs>
                  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-indigo)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--color-indigo)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--color-faint)" />
                <YAxis tick={{ fontSize: 11 }} stroke="var(--color-faint)" />
                <Tooltip
                  contentStyle={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-hairline)',
                    borderRadius: 8,
                  }}
                />
                <Area type="monotone" dataKey="equity" stroke="var(--color-indigo)" fill="url(#eqGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Metrics cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="rounded-lg border border-hairline bg-surface p-4">
              <p className="text-xs text-muted">Sharpe</p>
              <p className="font-mono text-lg text-ink">{result.metrics.sharpe.toFixed(2)}</p>
            </div>
            <div className="rounded-lg border border-hairline bg-surface p-4">
              <p className="text-xs text-muted">Max DD</p>
              <p className="font-mono text-lg text-loss">
                {(result.metrics.max_dd * 100).toFixed(1)}%
              </p>
            </div>
            <div className="rounded-lg border border-hairline bg-surface p-4">
              <p className="text-xs text-muted">Net Edge</p>
              <p className="font-mono text-lg text-ink">{result.metrics.net_edge.toFixed(2)}</p>
            </div>
            <div className="rounded-lg border border-hairline bg-surface p-4">
              <p className="text-xs text-muted">Win Rate</p>
              <p className="font-mono text-lg text-ink">
                {(result.metrics.win_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div className="rounded-lg border border-hairline bg-surface p-4">
              <p className="text-xs text-muted">N Trades</p>
              <p className="font-mono text-lg text-ink">{result.metrics.n_trades}</p>
            </div>
          </div>

          {/* Gauntlet results */}
          {mode === 'full_gauntlet' && result.gauntlet && (
            <div className="grid grid-cols-3 gap-4">
              <div className="rounded-lg border border-hairline bg-surface p-4">
                <p className="text-xs text-muted">DSR</p>
                <p className="font-mono text-lg text-ink">{result.gauntlet.dsr.toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-hairline bg-surface p-4">
                <p className="text-xs text-muted">PBO</p>
                <p className="font-mono text-lg text-ink">{result.gauntlet.pbo.toFixed(2)}</p>
              </div>
              <div className="rounded-lg border border-hairline bg-surface p-4">
                <p className="text-xs text-muted">Result</p>
                <span
                  className={`inline-block mt-1 text-sm font-medium px-2 py-0.5 rounded ${
                    result.gauntlet.passed
                      ? 'bg-gain/10 text-gain'
                      : 'bg-loss/10 text-loss'
                  }`}
                >
                  {result.gauntlet.passed ? 'Passed' : 'Failed'}
                </span>
              </div>
            </div>
          )}

          {/* Trade list table */}
          <div className="rounded-lg border border-hairline bg-surface p-4">
            <h2 className="font-display text-sm text-muted mb-3">Trades</h2>
            {result.trades.length === 0 ? (
              <p className="text-sm text-faint">No trades generated</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted text-xs border-b border-hairline">
                      <th className="text-left py-2 pr-4">Date</th>
                      <th className="text-left py-2 pr-4">Ticker</th>
                      <th className="text-left py-2 pr-4">Side</th>
                      <th className="text-right py-2 pr-4">Qty</th>
                      <th className="text-right py-2 pr-4">Price</th>
                      <th className="text-right py-2">PnL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((trade, i) => (
                      <tr key={i} className="border-b border-hairline last:border-0">
                        <td className="py-2 pr-4 font-mono text-ink">{trade.date}</td>
                        <td className="py-2 pr-4 font-mono text-ink">{trade.ticker}</td>
                        <td className="py-2 pr-4 text-ink">{trade.side}</td>
                        <td className="py-2 pr-4 text-right font-mono text-ink">{trade.qty}</td>
                        <td className="py-2 pr-4 text-right font-mono text-ink">
                          {trade.price.toFixed(2)}
                        </td>
                        <td
                          className={`py-2 text-right font-mono ${
                            trade.pnl >= 0 ? 'text-gain' : 'text-loss'
                          }`}
                        >
                          {trade.pnl >= 0 ? '+' : ''}
                          {trade.pnl.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
