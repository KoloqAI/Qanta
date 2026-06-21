import { useState } from 'react'
import { useAuth } from '../lib/auth'
import { apiFetch } from '../lib/api'
import { useTheme } from '../hooks/useTheme'

const TABS = [
  { id: 'account', label: 'Account' },
  { id: 'connections', label: 'Connections' },
  { id: 'models', label: 'Models & Routing' },
  { id: 'risk', label: 'Risk & Guardrails' },
  { id: 'validation', label: 'Validation' },
  { id: 'tools', label: 'Tools & Modules' },
  { id: 'appearance', label: 'Appearance' },
] as const

type TabId = (typeof TABS)[number]['id']

export function SettingsPage() {
  const [tab, setTab] = useState<TabId>('account')
  const { user } = useAuth()
  const { theme, setTheme } = useTheme()
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [message, setMessage] = useState('')

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await apiFetch('/auth/change-password', {
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
                <div className="flex items-center justify-between">
                  <div><p className="text-sm text-ink">IBKR (Broker)</p><p className="text-xs text-muted">Interactive Brokers connection</p></div>
                  <span className="text-xs px-2 py-0.5 rounded bg-surface text-muted">Not connected</span>
                </div>
                <div className="flex items-center justify-between">
                  <div><p className="text-sm text-ink">Market Data</p><p className="text-xs text-muted">Historical + live data feed</p></div>
                  <span className="text-xs px-2 py-0.5 rounded bg-gain/10 text-gain">Sample data active</span>
                </div>
              </div>
            </div>
          )}

          {tab === 'models' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Models &amp; Routing</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {['Local (Ollama)', 'Mid (Bedrock/Vertex)', 'Frontier (Claude/GPT-4)'].map((tier, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <span className="text-sm text-ink">{tier}</span>
                    <span className="text-xs text-muted">Configure in models.yaml</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'risk' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Risk &amp; Guardrails</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {[
                  { label: 'Per-Trade Stop', value: '5.0%' },
                  { label: 'Max Position', value: '10.0%' },
                  { label: 'Daily Drawdown Kill', value: '5.0%' },
                  { label: 'PDT Equity Min', value: '$25,000' },
                ].map(g => (
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
                {[
                  { label: 'DSR Threshold', value: '> 0.95' },
                  { label: 'PBO Threshold', value: '< 0.20' },
                  { label: 'Min Trades', value: '>= 100' },
                  { label: 'Cost-Adjusted Edge', value: '>= 50%' },
                ].map(t => (
                  <div key={t.label} className="flex items-center justify-between py-2 border-b border-hairline last:border-0">
                    <span className="text-sm text-ink">{t.label}</span>
                    <span className="font-mono text-sm text-muted">{t.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === 'tools' && (
            <div className="space-y-4">
              <h2 className="font-display text-sm text-muted">Tools &amp; Modules</h2>
              <div className="rounded-lg border border-hairline bg-surface p-4 space-y-3">
                {[
                  { name: 'News Module', enabled: false },
                  { name: 'Universe Scan', enabled: true },
                  { name: 'Technical Analysis', enabled: true },
                  { name: 'Backtest', enabled: true },
                ].map(t => (
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
