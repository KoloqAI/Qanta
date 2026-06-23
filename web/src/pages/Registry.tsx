import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../lib/api'
import { useMemo } from 'react'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { StrategyPanel } from '../components/registry/StrategyPanel'
import { ArchetypePanel } from '../components/registry/ArchetypePanel'
import { cn } from '../lib/cn'

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
  exclusion_reason?: string
}

type Tab = 'instantiated' | 'library'

/* ---------- Helpers ---------- */

function statusChip(status: string) {
  const cls =
    status === 'has-live'
      ? 'bg-gain/20 text-gain font-medium'
      : status === 'has-survivors'
        ? 'bg-gain/10 text-gain'
        : status === 'explored'
          ? 'bg-indigo/10 text-indigo'
          : status === 'excluded'
            ? 'bg-loss/10 text-loss'
            : status === 'live'
              ? 'bg-gain/10 text-gain'
              : status === 'validated'
                ? 'bg-indigo/10 text-indigo'
                : 'bg-surface text-muted'
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${cls}`}>{status}</span>
  )
}

/* ---------- Component ---------- */

export function RegistryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const isDesktop = useMediaQuery('(min-width: 1024px)')

  /* URL-driven state */
  const activeTab = (searchParams.get('tab') as Tab) || 'instantiated'
  const selectedId = searchParams.get('sel')
  const filter = searchParams.get('q') ?? ''
  const familyFilter = searchParams.get('family') ?? ''
  const horizonFilter = searchParams.get('horizon') ?? ''

  const updateParams = (
    updates: Record<string, string | null>,
    replace = true,
  ) => {
    setSearchParams(
      prev => {
        for (const [k, v] of Object.entries(updates)) {
          if (v) prev.set(k, v)
          else prev.delete(k)
        }
        return prev
      },
      { replace },
    )
  }

  const setActiveTab = (tab: Tab) =>
    updateParams({ tab, sel: null, q: null, family: null, horizon: null })
  const setSelectedId = (id: string | null) => updateParams({ sel: id })
  const setFilter = (q: string) => updateParams({ q: q || null })
  const setFamilyFilter = (f: string) => updateParams({ family: f || null })
  const setHorizonFilter = (h: string) => updateParams({ horizon: h || null })

  /* ---- Queries ---- */

  const { data: registryData, isLoading: registryLoading } = useQuery<
    Strategy[]
  >({
    queryKey: ['registry'],
    queryFn: async () => apiFetch('/api/strategies'),
  })

  const { data: libraryData, isLoading: libraryLoading } = useQuery<
    LibraryArchetype[]
  >({
    queryKey: ['library'],
    queryFn: async () => apiFetch('/api/library'),
    enabled: activeTab === 'library',
  })

  /* ---- Derived ---- */

  const strategies = (registryData ?? []).filter(
    s =>
      !filter ||
      s.name.toLowerCase().includes(filter.toLowerCase()) ||
      s.ticker.toLowerCase().includes(filter.toLowerCase()),
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

  const filteredLibrary = libraryItems.filter(
    a =>
      (!familyFilter || a.family === familyFilter) &&
      (!horizonFilter || a.horizon === horizonFilter),
  )

  const groupedByFamily = useMemo(() => {
    const groups: Record<string, LibraryArchetype[]> = {}
    for (const a of filteredLibrary) {
      ;(groups[a.family] ??= []).push(a)
    }
    return groups
  }, [filteredLibrary])

  const hasSelection = !!selectedId

  /* ---- Detail panel ---- */

  const detailContent = hasSelection ? (
    activeTab === 'instantiated' ? (
      <StrategyPanel
        strategyId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    ) : (
      <ArchetypePanel
        archetypeId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    )
  ) : (
    <div className="flex-1 flex items-center justify-center p-8">
      <p className="text-sm text-muted">
        {activeTab === 'instantiated'
          ? 'Select a strategy to see details and actions'
          : 'Select an archetype to see details and actions'}
      </p>
    </div>
  )

  /* ---- Render ---- */

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header + tabs */}
      <div className="shrink-0 px-6 pt-6 space-y-4">
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

        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab('instantiated')}
            className={cn(
              'px-4 py-1.5 rounded-lg text-sm transition focus-visible:ring-2 focus-visible:ring-indigo',
              activeTab === 'instantiated'
                ? 'bg-indigo/10 text-indigo font-medium'
                : 'text-muted hover:text-ink',
            )}
          >
            Instantiated
          </button>
          <button
            onClick={() => setActiveTab('library')}
            className={cn(
              'px-4 py-1.5 rounded-lg text-sm transition focus-visible:ring-2 focus-visible:ring-indigo',
              activeTab === 'library'
                ? 'bg-indigo/10 text-indigo font-medium'
                : 'text-muted hover:text-ink',
            )}
          >
            Library
          </button>
        </div>

        {activeTab === 'library' && (
          <div className="flex gap-3">
            <select
              value={familyFilter}
              onChange={e => setFamilyFilter(e.target.value)}
              className="px-3 py-1.5 bg-inset border border-hairline rounded-lg text-sm focus:outline-none focus:border-indigo"
            >
              <option value="">All families</option>
              {families.map(f => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
            <select
              value={horizonFilter}
              onChange={e => setHorizonFilter(e.target.value)}
              className="px-3 py-1.5 bg-inset border border-hairline rounded-lg text-sm focus:outline-none focus:border-indigo"
            >
              <option value="">All horizons</option>
              {horizons.map(h => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Master-detail area */}
      <div className="flex flex-1 min-h-0 mt-4">
        {/* Left: list column */}
        <div
          className={cn(
            'overflow-y-auto',
            isDesktop
              ? 'w-1/2 border-r border-hairline'
              : hasSelection
                ? 'hidden'
                : 'w-full',
          )}
        >
          {/* ===== Instantiated tab ===== */}
          {activeTab === 'instantiated' && (
            <div className="px-4 pb-4">
              {registryLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-14 bg-surface animate-pulse rounded-lg"
                    />
                  ))}
                </div>
              ) : strategies.length === 0 ? (
                <div className="rounded-lg border border-hairline bg-surface p-12 text-center">
                  <p className="text-muted text-sm">No strategies found</p>
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
                        <tr
                          key={s.id}
                          onClick={() => setSelectedId(s.id)}
                          className={cn(
                            'border-t border-hairline cursor-pointer transition',
                            selectedId === s.id
                              ? 'bg-indigo/5'
                              : 'hover:bg-surface/50',
                          )}
                        >
                          <td className="px-4 py-3 text-ink font-medium">
                            {s.name}
                          </td>
                          <td className="px-4 py-3 font-mono text-muted">
                            {s.ticker}
                          </td>
                          <td className="px-4 py-3">{statusChip(s.status)}</td>
                          <td className="px-4 py-3 text-right font-mono">
                            {s.sharpe.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ===== Library tab ===== */}
          {activeTab === 'library' && (
            <div className="px-4 pb-4">
              {libraryLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-24 bg-surface animate-pulse rounded-lg"
                    />
                  ))}
                </div>
              ) : filteredLibrary.length === 0 ? (
                <div className="rounded-lg border border-hairline bg-surface p-12 text-center">
                  <p className="text-muted text-sm">No archetypes found</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {Object.entries(groupedByFamily).map(
                    ([family, archetypes]) => (
                      <div key={family}>
                        <h2 className="font-display text-xs text-muted mb-2 px-1">
                          {family}
                        </h2>
                        <div className="space-y-2">
                          {archetypes.map(a => (
                            <div
                              key={a.id}
                              onClick={() => setSelectedId(a.id)}
                              className={cn(
                                'rounded-lg border cursor-pointer p-3 transition',
                                selectedId === a.id
                                  ? 'border-indigo bg-indigo/5'
                                  : 'border-hairline bg-surface hover:border-indigo/40',
                              )}
                            >
                              <div className="flex items-start justify-between gap-2 mb-1">
                                <span className="text-ink font-medium text-sm">
                                  {a.name}
                                </span>
                                {statusChip(a.status)}
                              </div>
                              <p className="text-muted text-xs truncate">
                                {a.thesis}
                              </p>
                              {a.status === 'excluded' &&
                                a.exclusion_reason && (
                                  <p
                                    className="text-loss text-[10px] mt-1 truncate"
                                    title={a.exclusion_reason}
                                  >
                                    {a.exclusion_reason}
                                  </p>
                                )}
                              <div className="mt-1.5">
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-inset text-faint">
                                  {a.horizon}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ),
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: detail panel — desktop docked */}
        {isDesktop && (
          <div className="w-1/2 flex flex-col min-h-0 bg-paper">
            {detailContent}
          </div>
        )}

        {/* Right: detail panel — mobile slide-over */}
        {!isDesktop && hasSelection && (
          <div className="fixed inset-0 z-40">
            <div
              className="absolute inset-0 bg-ink/20 motion-safe:animate-[fadeIn_150ms_ease-out]"
              onClick={() => setSelectedId(null)}
              aria-hidden="true"
            />
            <div className="absolute inset-y-0 right-0 w-full sm:max-w-md bg-paper border-l border-hairline flex flex-col motion-safe:animate-[slideInRight_200ms_ease-out]">
              {detailContent}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
