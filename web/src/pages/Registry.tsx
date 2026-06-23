import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { useNavigate } from 'react-router-dom'
import { useMemo, useState } from 'react'

/* ---------- Types ---------- */

interface Strategy {
  id: string
  name: string
  ticker: string
  status: string
  domain: string
  sharpe: number
  created_at: string
}

interface LibraryArchetype {
  id: string
  name: string
  family: string
  horizon: string
  thesis: string
  status: string
  source: string
}

interface ArchetypeDetail extends LibraryArchetype {
  param_grid: Record<string, unknown>
  scan_logic: string
  exploration_funnel: {
    scanned: number
    passed_backtest: number
    passed_validation: number
    live: number
  }
}

type Tab = 'instantiated' | 'library'

/* ---------- Helpers ---------- */

function statusBadge(status: string) {
  const cls =
    status === 'has-live'      ? 'bg-gain/20 text-gain font-medium' :
    status === 'has-survivors' ? 'bg-gain/10 text-gain' :
    status === 'explored'      ? 'bg-indigo/10 text-indigo' :
                                 'bg-surface text-muted'
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${cls}`}>
      {status}
    </span>
  )
}

/* ---------- Component ---------- */

export function RegistryPage() {
  const navigate = useNavigate()

  /* Shared state */
  const [activeTab, setActiveTab] = useState<Tab>('instantiated')

  /* Instantiated tab state */
  const [filter, setFilter] = useState('')

  /* Library tab state */
  const [familyFilter, setFamilyFilter] = useState('')
  const [horizonFilter, setHorizonFilter] = useState('')
  const [selectedArchetype, setSelectedArchetype] = useState<string | null>(null)

  /* ---- Queries ---- */

  const { data: registryData, isLoading: registryLoading } = useQuery<Strategy[]>({
    queryKey: ['registry'],
    queryFn: () => apiFetch('/api/strategies'),
  })

  const { data: libraryData, isLoading: libraryLoading } = useQuery<LibraryArchetype[]>({
    queryKey: ['library'],
    queryFn: () => apiFetch('/api/library'),
    enabled: activeTab === 'library',
  })

  const { data: archetypeDetail, isLoading: detailLoading } = useQuery<ArchetypeDetail>({
    queryKey: ['library', selectedArchetype],
    queryFn: () => apiFetch(`/api/library/${selectedArchetype}`),
    enabled: !!selectedArchetype,
  })

  /* ---- Derived data ---- */

  const strategies = (registryData ?? []).filter(s =>
    !filter || s.name.toLowerCase().includes(filter.toLowerCase()) || s.ticker.toLowerCase().includes(filter.toLowerCase())
  )

  const libraryItems = libraryData ?? []

  const families = useMemo(
    () => Array.from(new Set(libraryItems.map(a => a.family))).sort(),
    [libraryItems],
  )
  const horizons = useMemo(
    () => Array.from(new Set(libraryItems.map(a => a.horizon))).sort(),
    [libraryItems],
  )

  const filteredLibrary = libraryItems.filter(a =>
    (!familyFilter || a.family === familyFilter) &&
    (!horizonFilter || a.horizon === horizonFilter)
  )

  const groupedByFamily = useMemo(() => {
    const groups: Record<string, LibraryArchetype[]> = {}
    for (const a of filteredLibrary) {
      ;(groups[a.family] ??= []).push(a)
    }
    return groups
  }, [filteredLibrary])

  /* ---- Render ---- */

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl text-ink">Strategy Registry</h1>

        {activeTab === 'instantiated' && (
          <input
            type="text"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Search..."
            className="px-3 py-1.5 bg-inset border border-hairline rounded-lg text-sm w-48 focus:outline-none focus:border-indigo"
          />
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1">
        <button
          onClick={() => setActiveTab('instantiated')}
          className={`px-4 py-1.5 rounded-lg text-sm transition ${
            activeTab === 'instantiated'
              ? 'bg-indigo/10 text-indigo font-medium'
              : 'text-muted hover:text-ink'
          }`}
        >
          Instantiated
        </button>
        <button
          onClick={() => setActiveTab('library')}
          className={`px-4 py-1.5 rounded-lg text-sm transition ${
            activeTab === 'library'
              ? 'bg-indigo/10 text-indigo font-medium'
              : 'text-muted hover:text-ink'
          }`}
        >
          Library
        </button>
      </div>

      {/* ================= Instantiated Tab ================= */}
      {activeTab === 'instantiated' && (
        <>
          {registryLoading ? (
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
        </>
      )}

      {/* ================= Library Tab ================= */}
      {activeTab === 'library' && (
        <>
          {/* Filters */}
          <div className="flex gap-3">
            <select
              value={familyFilter}
              onChange={e => setFamilyFilter(e.target.value)}
              className="px-3 py-1.5 bg-inset border border-hairline rounded-lg text-sm focus:outline-none focus:border-indigo"
            >
              <option value="">All families</option>
              {families.map(f => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>

            <select
              value={horizonFilter}
              onChange={e => setHorizonFilter(e.target.value)}
              className="px-3 py-1.5 bg-inset border border-hairline rounded-lg text-sm focus:outline-none focus:border-indigo"
            >
              <option value="">All horizons</option>
              {horizons.map(h => (
                <option key={h} value={h}>{h}</option>
              ))}
            </select>
          </div>

          {/* Library content */}
          {libraryLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-32 bg-surface animate-pulse rounded-lg" />
              ))}
            </div>
          ) : filteredLibrary.length === 0 ? (
            <div className="rounded-lg border border-hairline bg-surface p-12 text-center">
              <p className="text-muted">No archetypes found</p>
            </div>
          ) : (
            <div className="space-y-8">
              {Object.entries(groupedByFamily).map(([family, archetypes]) => (
                <div key={family}>
                  <h2 className="font-display text-sm text-muted mb-3">{family}</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {archetypes.map(a => (
                      <div
                        key={a.id}
                        onClick={() => setSelectedArchetype(a.id)}
                        className={`rounded-lg border cursor-pointer p-4 transition ${
                          selectedArchetype === a.id
                            ? 'border-indigo bg-indigo/5'
                            : 'border-hairline bg-surface hover:border-indigo/40'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <span className="text-ink font-medium text-sm">{a.name}</span>
                          {statusBadge(a.status)}
                        </div>
                        <p className="text-muted text-xs truncate">{a.thesis}</p>
                        <div className="mt-2">
                          <span className="text-xs px-1.5 py-0.5 rounded bg-inset text-faint">
                            {a.horizon}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Detail panel */}
          {selectedArchetype && (
            <div className="rounded-lg border border-hairline bg-surface p-6 space-y-5">
              {detailLoading ? (
                <div className="space-y-3">
                  <div className="h-5 w-48 bg-inset animate-pulse rounded" />
                  <div className="h-4 w-full bg-inset animate-pulse rounded" />
                  <div className="h-4 w-2/3 bg-inset animate-pulse rounded" />
                </div>
              ) : !archetypeDetail ? (
                <p className="text-muted">Failed to load archetype detail</p>
              ) : (
                <>
                  {/* Name + badges */}
                  <div className="flex items-center gap-3">
                    <h2 className="font-display text-lg text-ink">{archetypeDetail.name}</h2>
                    {statusBadge(archetypeDetail.status)}
                    <span className="text-xs px-1.5 py-0.5 rounded bg-inset text-faint">
                      {archetypeDetail.horizon}
                    </span>
                  </div>

                  {/* Thesis */}
                  <div>
                    <h3 className="text-xs text-muted mb-1">Thesis</h3>
                    <p className="text-sm text-ink">{archetypeDetail.thesis}</p>
                  </div>

                  {/* Param grid */}
                  <div>
                    <h3 className="text-xs text-muted mb-1">Param Grid</h3>
                    <div className="bg-inset rounded-lg p-3 overflow-x-auto">
                      <table className="text-xs w-full">
                        <tbody>
                          {Object.entries(archetypeDetail.param_grid).map(([key, val]) => (
                            <tr key={key} className="border-b border-hairline last:border-0">
                              <td className="py-1 pr-4 text-muted font-mono">{key}</td>
                              <td className="py-1 text-ink font-mono">
                                {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Scan logic */}
                  <div>
                    <h3 className="text-xs text-muted mb-1">Scan Logic</h3>
                    <pre className="bg-inset rounded-lg p-3 text-xs font-mono text-ink overflow-x-auto whitespace-pre-wrap">
                      {archetypeDetail.scan_logic}
                    </pre>
                  </div>

                  {/* Exploration funnel */}
                  <div>
                    <h3 className="text-xs text-muted mb-2">Exploration Funnel</h3>
                    <div className="grid grid-cols-4 gap-3">
                      {([
                        ['Scanned', archetypeDetail.exploration_funnel.scanned],
                        ['Passed Backtest', archetypeDetail.exploration_funnel.passed_backtest],
                        ['Passed Validation', archetypeDetail.exploration_funnel.passed_validation],
                        ['Live', archetypeDetail.exploration_funnel.live],
                      ] as const).map(([label, count]) => (
                        <div key={label} className="bg-inset rounded-lg p-3 text-center">
                          <div className="text-lg font-mono text-ink">{count}</div>
                          <div className="text-xs text-muted">{label}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3 pt-2">
                    <button className="px-4 py-2 rounded-lg bg-indigo text-white text-sm font-medium hover:bg-indigo/90 transition">
                      Run scan
                    </button>
                    <button className="px-4 py-2 rounded-lg border border-indigo text-indigo text-sm font-medium hover:bg-indigo/5 transition">
                      Explore
                    </button>
                    <button className="px-4 py-2 rounded-lg border border-hairline text-ink text-sm hover:bg-inset transition">
                      Author from this
                    </button>
                    <button className="px-4 py-2 rounded-lg border border-hairline text-ink text-sm hover:bg-inset transition">
                      Open in Sandbox
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
