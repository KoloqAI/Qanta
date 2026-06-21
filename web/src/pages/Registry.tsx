import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'

interface Strategy {
  id: string
  name: string
  ticker: string
  status: string
  domain: string
  sharpe: number
  created_at: string
}

export function RegistryPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')

  const { data, isLoading } = useQuery<Strategy[]>({
    queryKey: ['registry'],
    queryFn: () => apiFetch('/api/strategies'),
  })

  const strategies = (data ?? []).filter(s =>
    !filter || s.name.toLowerCase().includes(filter.toLowerCase()) || s.ticker.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl text-ink">Strategy Registry</h1>
        <input type="text" value={filter} onChange={e => setFilter(e.target.value)}
          placeholder="Search..."
          className="px-3 py-1.5 bg-inset border border-hairline rounded-lg text-sm w-48 focus:outline-none focus:border-indigo" />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 bg-surface animate-pulse rounded-lg" />
          ))}
        </div>
      ) : strategies.length === 0 ? (
        <div className="rounded-lg border border-hairline bg-surface p-12 text-center">
          <p className="text-muted">No strategies found</p>
        </div>
      ) : (
        <div className="rounded-lg border border-hairline overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-inset text-muted text-xs">
                <th className="text-left px-4 py-2">Name</th>
                <th className="text-left px-4 py-2">Ticker</th>
                <th className="text-left px-4 py-2">Status</th>
                <th className="text-right px-4 py-2">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map(s => (
                <tr key={s.id} onClick={() => navigate(`/strategy/${s.id}`)}
                  className="border-t border-hairline cursor-pointer hover:bg-surface/50 transition">
                  <td className="px-4 py-3 text-ink font-medium">{s.name}</td>
                  <td className="px-4 py-3 font-mono text-muted">{s.ticker}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      s.status === 'live' ? 'bg-gain/10 text-gain' :
                      s.status === 'validated' ? 'bg-indigo/10 text-indigo' :
                      'bg-surface text-muted'
                    }`}>{s.status}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{s.sharpe.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
