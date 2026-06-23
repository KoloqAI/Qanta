import { useState } from 'react'
import { useAuth } from '../lib/auth'
import { apiFetch } from '../lib/api'
import { useTheme } from '../hooks/useTheme'
import { useQuery } from '@tanstack/react-query'

const TABS = [
  { id: 'connections', label: 'Connections' },
  { id: 'models', label: 'Models & Routing' },
  { id: 'risk', label: 'Risk & Guardrails' },
  { id: 'validation', label: 'Validation' },
  { id: 'portfolio', label: 'Portfolio & Allocation' },
  { id: 'tools', label: 'Tools & Modules' },
  { id: 'workflows', label: 'Workflows' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'appearance', label: 'Appearance' },
  { id: 'account', label: 'Account' },
] as const

type TabId = (typeof TABS)[number]['id']

interface Connection {
  name: string
  description: string
  status: string
}

interface ModelTier {
  tier: string
  provider: string
  model: string
  status: string
}

interface Guardrail {
  label: string
  value: string
}

interface ValidationThreshold {
  label: string
  value: string
}

interface ToolModule {
  name: string
  enabled: boolean
}

interface PortfolioSetting {
  label: string
  value: string
}

interface NotificationChannel {
  channel: string
  enabled: boolean
}

interface NotificationConfig {
  channels: NotificationChannel[]
  severity_routing: Record<string, string[]>
  quiet_hours: { enabled: boolean; start: string; end: string }
}

export function SettingsPage() {
  const [tab, setTab] = useState<TabId>('connections')
  const { user } = useAuth()
  const { theme, setTheme } = useTheme()
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [message, setMessage] = useState('')

  const { data: connections } = useQuery<Connection[]>({
    queryKey: ['settings', 'connections'],
    queryFn: async () => {
      const d = await apiFetch('/api/settings/connections')
      return [
        {
          name: 'IBKR (Broker)',
          description: `${d.broker?.host ?? 'localhost'}:${d.broker?.port ?? 4002}`,
          status: d.broker?.connected ? 'Connected' : 'Not connected',
        },
        {
          name: 'Market Data',
          description: `Provider: ${d.data?.provider ?? 'sample'}`,
          status: d.data?.status === 'ok' ? 'Active' : (d.data?.status ?? 'Unknown'),
        },
        {
          name: 'Redis',
          description: d.redis?.url ?? 'Not configured',
          status: d.redis?.url ? 'Configured' : 'Not configured',
        },
        {
          name: 'Database',
          description: d.database?.url ?? 'Not configured',
          status: d.database?.url ? 'Configured' : 'Not configured',
        },
      ]
    },
    enabled: tab === 'connections',
  })

  const { data: models } = useQuery<ModelTier[]>({
    queryKey: ['settings', 'models'],
    queryFn: async () => {
      const d = await apiFetch('/api/settings/models')
      const tiers: Record<string, { primary?: string; fallback?: string }> = d.tiers ?? {}
      return Object.entries(tiers).map(([tierName, cfg]) => ({
        tier: tierName.charAt(0).toUpperCase() + tierName.slice(1),
        provider: cfg.primary?.split('/')[0] ?? '',
        model: cfg.primary ?? '',
        status: cfg.primary ? 'Configured' : 'Not configured',
      }))
    },
    enabled: tab === 'models',
  })

  const { data: risk } = useQuery<Guardrail[]>({
    queryKey: ['settings', 'risk'],
    queryFn: async () => {
      const d = await apiFetch('/api/settings/risk')
      const g = d.guardrails ?? {}
      return [
        { label: 'Per-Trade Stop', value: g.per_trade_stop_pct != null ? `${g.per_trade_stop_pct}%` : 'N/A' },
        { label: 'Max Position', value: g.max_position_pct != null ? `${g.max_position_pct}%` : 'N/A' },
        { label: 'Max Gross Exposure', value: g.max_gross_exposure_pct != null ? `${g.max_gross_exposure_pct}%` : 'N/A' },
        { label: 'Daily Drawdown Kill', value: g.daily_drawdown_kill_pct != null ? `${g.daily_drawdown_kill_pct}%` : 'N/A' },
        { label: 'PDT Equity Min', value: g.pdt_equity_minimum != null ? `$${Number(g.pdt_equity_minimum).toLocaleString()}` : 'N/A' },
        { label: 'Kill Switch', value: d.kill_switch_active ? 'ACTIVE' : 'Inactive' },
      ]
    },
    enabled: tab === 'risk',
  })

  const { data: validation } = useQuery<ValidationThreshold[]>({
    queryKey: ['settings', 'validation'],
    queryFn: async () => {
      const d = await apiFetch('/api/settings/validation')
      const t = d.thresholds ?? {}
      return [
        { label: 'DSR Threshold', value: t.deflated_sharpe_min != null ? `> ${t.deflated_sharpe_min}` : 'N/A' },
        { label: 'PBO Threshold', value: t.pbo_max != null ? `< ${t.pbo_max}` : 'N/A' },
        { label: 'Min Trades', value: t.min_trades != null ? `>= ${t.min_trades}` : 'N/A' },
        { label: 'Cost-Adjusted Edge', value: t.cost_adjusted_edge_ratio != null ? `>= ${Math.round(t.cost_adjusted_edge_ratio * 100)}%` : 'N/A' },
        { label: 'Peer Hit Rate', value: t.peer_hit_rate_min != null ? `>= ${Math.round(t.peer_hit_rate_min * 100)}%` : 'N/A' },
        { label: 'Degradation Slope', value: t.deg_slope_min != null ? `>= ${t.deg_slope_min}` : 'N/A' },
      ]
    },
    enabled: tab === 'validation',
  })

  const { data: tools } = useQuery<ToolModule[]>({
    queryKey: ['settings', 'tools'],
    queryFn: async () => {
      const d = await apiFetch('/api/settings/tools')
      return (d.tools ?? []).map((t: { name: string }) => ({
        name: t.name,
        enabled: true,
      }))
    },
    enabled: tab === 'tools',
  })

  const { data: portfolio } = useQuery<PortfolioSetting[]>({
    queryKey: ['settings', 'portfolio'],
    queryFn: async () => {
      const d = await apiFetch('/api/settings/portfolio')
      const a = d.allocation ?? {}
      const c = d.caps ?? {}
      return [
        { label: 'Allocation Method', value: a.method ?? 'N/A' },
        { label: 'Cash Buffer', value: a.cash_buffer_pct != null ? `${a.cash_buffer_pct}%` : 'N/A' },
        { label: 'Max Strategies', value: a.max_strategies != null ? String(a.max_strategies) : 'N/A' },
        { label: 'Per-Symbol Cap', value: c.per_symbol_pct != null ? `${c.per_symbol_pct}%` : 'N/A' },
        { label: 'Per-Sector Cap', value: c.per_sector_pct != null ? `${c.per_sector_pct}%` : 'N/A' },
        { label: 'Max Gross Exposure', value: c.max_gross_exposure_pct != null ? `${c.max_gross_exposure_pct}%` : 'N/A' },
      ]
    },
    enabled: tab === 'portfolio',
  })

  const { data: workflows } = useQuery<unknown[]>({
    queryKey: ['settings', 'workflows'],
    queryFn: () => apiFetch('/api/settings/workflows'),
    enabled: tab === 'workflows',
  })

  const { data: notifications } = useQuery<NotificationConfig>({
    queryKey: ['settings', 'notifications'],
    queryFn: async () => {
      const d = await apiFetch('/api/settings/notifications')
      return {
        channels: (d.channels ?? []).map((ch: { type: string; enabled: boolean }) => ({
          channel: ch.type,
          enabled: ch.enabled,
        })),
        severity_routing: d.severity_routing ?? {},
        quiet_hours: d.quiet_hours ?? { enabled: false, start: '22:00', end: '07:00' },
      }
    },
    enabled: tab === 'notifications',
  })

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await apiFetch('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      })
      setMessage('Password changed successfully')
      setOldPassword('')
      setNewPassword('')
    } catch {
      setMessage('Failed to change password')
    }
  }

  return (
    <div className="p-6">
      <h1 className="font-display text-xl text-ink mb-6">Settings</h1>

      <div className="flex gap-6">
        <nav className="w-48 shrink-0">
          <div className="space-y-1">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={`w-full text-left px-3 py-2 text-sm rounded-lg transition ${
                  tab === t.id ? 'bg-indigo/10 text-indigo font-medium' : 'text-muted hover:text-ink hover:bg-surface'
                }`}>
                {t.label}
              </button>
            ))}
          </div>
        </nav>

        <div className="flex-1 max-w-2xl">
          {tab === 'account' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Account</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                <div>
                  <label className="text-xs text-muted">Email</label>
                  <p className="text-sm text-ink font-mono mt-1">{user?.email ?? 'Not set'}</p>
                </div>
              </div>
              <form onSubmit={handleChangePassword} className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                <p className="text-sm text-ink font-medium">Change password</p>
                {message && <p className="text-xs text-muted">{message}</p>}
                <input
                  type="password"
                  placeholder="Current password"
                  value={oldPassword}
                  onChange={e => setOldPassword(e.target.value)}
                  className="w-full bg-inset border border-hairline rounded px-3 py-2 text-sm text-ink placeholder:text-faint focus:outline-none focus:ring-1 focus:ring-indigo"
                />
                <input
                  type="password"
                  placeholder="New password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  className="w-full bg-inset border border-hairline rounded px-3 py-2 text-sm text-ink placeholder:text-faint focus:outline-none focus:ring-1 focus:ring-indigo"
                />
                <button
                  type="submit"
                  className="bg-[var(--color-indigo)] text-white rounded px-4 py-2 text-sm font-medium hover:opacity-90 transition-opacity"
                >
                  Update password
                </button>
              </form>
            </div>
          )}

          {tab === 'connections' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Connections</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-4">
                {(connections ?? [
                  { name: 'IBKR (Broker)', description: 'Interactive Brokers connection', status: 'Not connected' },
                  { name: 'Market Data', description: 'Historical + live data feed', status: 'Sample data active' },
                ]).map(c => (
                  <div key={c.name} className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-ink">{c.name}</p>
                      <p className="text-xs text-muted">{c.description}</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      c.status.toLowerCase().includes('active') || c.status.toLowerCase().includes('connected')
                        ? 'bg-gain/10 text-gain'
                        : 'bg-surface text-muted'
                    }`}>
                      {c.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'models' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Models &amp; Routing</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {(models ?? [
                  { tier: 'Local (Ollama)', provider: '', model: '', status: 'Configure in models.yaml' },
                  { tier: 'Mid (Bedrock/Vertex)', provider: '', model: '', status: 'Configure in models.yaml' },
                  { tier: 'Frontier (Claude/GPT-4)', provider: '', model: '', status: 'Configure in models.yaml' },
                ]).map((m, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <div>
                      <span className="text-sm text-ink">{m.tier}</span>
                      {m.model && <span className="ml-2 text-xs text-muted font-mono">{m.model}</span>}
                    </div>
                    <span className="text-xs text-muted">{m.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'risk' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Risk &amp; Guardrails</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {(risk ?? [
                  { label: 'Per-Trade Stop', value: '5.0%' },
                  { label: 'Max Position', value: '10.0%' },
                  { label: 'Daily Drawdown Kill', value: '5.0%' },
                  { label: 'PDT Equity Min', value: '$25,000' },
                ]).map(g => (
                  <div key={g.label} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <span className="text-sm text-ink">{g.label}</span>
                    <span className="font-mono text-sm text-muted">{g.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'validation' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Validation Thresholds</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {(validation ?? [
                  { label: 'DSR Threshold', value: '> 0.95' },
                  { label: 'PBO Threshold', value: '< 0.20' },
                  { label: 'Min Trades', value: '>= 100' },
                  { label: 'Cost-Adjusted Edge', value: '>= 50%' },
                ]).map(t => (
                  <div key={t.label} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <span className="text-sm text-ink">{t.label}</span>
                    <span className="font-mono text-sm text-muted">{t.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'portfolio' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Portfolio &amp; Allocation</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {(portfolio ?? [
                  { label: 'Allocation Method', value: 'N/A' },
                  { label: 'Cash Buffer', value: 'N/A' },
                  { label: 'Max Strategies', value: 'N/A' },
                  { label: 'Per-Symbol Cap', value: 'N/A' },
                  { label: 'Per-Sector Cap', value: 'N/A' },
                  { label: 'Max Gross Exposure', value: 'N/A' },
                ]).map(p => (
                  <div key={p.label} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <span className="text-sm text-ink">{p.label}</span>
                    <span className="font-mono text-sm text-muted">{p.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'tools' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Tools &amp; Modules</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {(tools ?? [
                  { name: 'News Module', enabled: false },
                  { name: 'Universe Scan', enabled: true },
                  { name: 'Technical Analysis', enabled: true },
                  { name: 'Backtest', enabled: true },
                ]).map(t => (
                  <div key={t.name} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <span className="text-sm text-ink">{t.name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${t.enabled ? 'bg-gain/10 text-gain' : 'bg-surface text-muted'}`}>
                      {t.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'workflows' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Workflows</h2>
              {(workflows ?? []).length === 0 ? (
                <div className="rounded-lg border border-hairline bg-surface p-12 text-center">
                  <p className="text-muted">No workflows configured</p>
                </div>
              ) : (
                <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                  {(workflows ?? []).map((_, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                      <span className="text-sm text-ink">Workflow {i + 1}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'notifications' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Notifications</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-4">
                <p className="text-sm text-ink font-medium">Channels</p>
                {(notifications?.channels ?? [
                  { channel: 'email', enabled: false },
                  { channel: 'telegram', enabled: false },
                  { channel: 'sms', enabled: false },
                ]).map(ch => (
                  <div key={ch.channel} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <span className="text-sm text-ink capitalize">{ch.channel}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${ch.enabled ? 'bg-gain/10 text-gain' : 'bg-surface text-muted'}`}>
                      {ch.enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                ))}
              </div>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                <p className="text-sm text-ink font-medium">Severity Routing</p>
                {Object.entries(notifications?.severity_routing ?? {}).length === 0 ? (
                  <p className="text-sm text-faint">No routing rules configured</p>
                ) : (
                  Object.entries(notifications?.severity_routing ?? {}).map(([severity, channels]) => (
                    <div key={severity} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                      <span className="text-sm text-ink capitalize">{severity}</span>
                      <span className="text-xs text-muted font-mono">{(channels as string[]).join(', ')}</span>
                    </div>
                  ))
                )}
              </div>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                <p className="text-sm text-ink font-medium">Quiet Hours</p>
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-ink">Status</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    notifications?.quiet_hours?.enabled ? 'bg-gain/10 text-gain' : 'bg-surface text-muted'
                  }`}>
                    {notifications?.quiet_hours?.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
                {notifications?.quiet_hours?.enabled && (
                  <div className="flex items-center justify-between py-2 border-t border-hairline">
                    <span className="text-sm text-ink">Window</span>
                    <span className="text-sm text-muted font-mono">
                      {notifications.quiet_hours.start} - {notifications.quiet_hours.end}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === 'appearance' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Appearance</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4">
                <p className="text-sm text-ink mb-3">Theme</p>
                <div className="flex gap-2">
                  {(['system', 'light', 'dark'] as const).map(t => (
                    <button key={t} onClick={() => setTheme(t)}
                      className={`px-4 py-2 text-sm rounded-lg capitalize ${
                        theme === t ? 'bg-indigo text-white' : 'border border-hairline text-muted hover:text-ink'
                      }`}>
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
