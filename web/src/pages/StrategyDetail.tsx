import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch, apiMutate } from '../lib/api'
import { ConfidenceBar } from '../components/ConfidenceBar'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useState } from 'react'
import { useToast } from '../hooks/useToast'

/* ---------- Types ---------- */

interface DeploymentInfo {
  id: string
  mode: 'paper' | 'live'
  status: string
  capital_budget: number | null
}

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
  deployment: DeploymentInfo | null
}

/* ---------- Component ---------- */

export function StrategyDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [tab, setTab] = useState<'overview' | 'validation' | 'live'>('overview')
  const [reason, setReason] = useState('')
  const [showDeployModal, setShowDeployModal] = useState(false)
  const [deployCapital, setDeployCapital] = useState('')
  const [deployGuardrails, setDeployGuardrails] = useState('')

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['strategy', id] })
    queryClient.invalidateQueries({ queryKey: ['registry'] })
  }

  /* ---- Query ---- */

  const { data, isLoading } = useQuery<StrategyData>({
    queryKey: ['strategy', id],
    queryFn: () => apiFetch(`/api/strategies/${id}`),
  })

  /* ---- Mutations ---- */

  const validateMutation = useMutation({
    mutationFn: () => apiMutate<{ job_id: string; passed?: boolean }>(`/api/strategies/${id}/validate`),
    onSuccess: (res) => {
      invalidateAll()
      toast(res.passed ? 'Validation passed' : 'Validation completed — did not pass', res.passed ? 'success' : 'info')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const approveMutation = useMutation({
    mutationFn: () => apiMutate(`/api/strategies/${id}/approve`, { approved: true, reason }),
    onSuccess: () => {
      invalidateAll()
      toast('Strategy approved', 'success')
      setShowDeployModal(true)
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const rejectMutation = useMutation({
    mutationFn: () => apiMutate(`/api/strategies/${id}/approve`, { approved: false, reason }),
    onSuccess: () => {
      invalidateAll()
      toast('Strategy rejected', 'info')
      navigate(-1)
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const deployMutation = useMutation({
    mutationFn: () => {
      let guardrails: Record<string, unknown> | undefined
      if (deployGuardrails.trim()) {
        try { guardrails = JSON.parse(deployGuardrails) } catch { /* use undefined */ }
      }
      return apiMutate('/api/deployments', {
        strategy_version_id: id,
        mode: 'paper',
        guardrails,
        capital_budget: deployCapital ? Number(deployCapital) : null,
      })
    },
    onSuccess: () => {
      invalidateAll()
      setShowDeployModal(false)
      toast('Paper deployment created', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const promoteMutation = useMutation({
    mutationFn: () => apiMutate(`/api/deployments/${data?.deployment?.id}/promote`, { reason: '' }),
    onSuccess: () => {
      invalidateAll()
      toast('Promoted to live', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const pauseMutation = useMutation({
    mutationFn: () => apiMutate(`/api/deployments/${data?.deployment?.id}/pause`),
    onSuccess: () => {
      invalidateAll()
      toast('Deployment paused', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const flattenMutation = useMutation({
    mutationFn: () => apiMutate(`/api/deployments/${data?.deployment?.id}/flatten`),
    onSuccess: () => {
      invalidateAll()
      toast('Positions flattened', 'success')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  const retireMutation = useMutation({
    mutationFn: () => apiMutate(`/api/deployments/${data?.deployment?.id}/retire`),
    onSuccess: () => {
      invalidateAll()
      toast('Deployment retired', 'info')
    },
    onError: (e: Error) => toast(e.message, 'error'),
  })

  /* ---- Handlers (risk_increasing require confirm) ---- */

  const handleValidate = () => validateMutation.mutate()

  const handleApprove = () => {
    if (!window.confirm('Risk-increasing: approve this strategy and open deployment config?')) return
    approveMutation.mutate()
  }

  const handleReject = () => rejectMutation.mutate()

  const handleDeploy = () => {
    if (!window.confirm('Risk-increasing: create a paper deployment for this strategy?')) return
    deployMutation.mutate()
  }

  const handlePromote = () => {
    if (!window.confirm('Risk-increasing: promote this deployment to live trading?')) return
    promoteMutation.mutate()
  }

  const handlePause = () => pauseMutation.mutate()
  const handleFlatten = () => flattenMutation.mutate()
  const handleRetire = () => retireMutation.mutate()

  /* ---- Loading ---- */

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
    deployment: null,
  }

  const dep = s.deployment
  const isDeployed = !!dep && (dep.mode === 'paper' || dep.mode === 'live')

  const btnPrimary = 'px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50'
  const btnGhost = 'px-4 py-2 border border-hairline rounded-lg text-sm transition disabled:opacity-50'

  /* ---- Render ---- */

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl text-ink">{s.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className="font-mono text-sm text-muted">{s.ticker}</span>
            <span className="text-xs text-faint">v{s.version}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              s.state === 'validated' ? 'bg-gain/10 text-gain' :
              s.state === 'approved' ? 'bg-indigo/10 text-indigo' :
              s.state === 'live' ? 'bg-indigo/10 text-indigo' :
              s.state === 'rejected' ? 'bg-loss/10 text-loss' :
              'bg-surface text-muted'
            }`}>{s.state}</span>
            {dep && (
              <span className={`text-xs px-1.5 py-0.5 rounded ${
                dep.mode === 'live' ? 'bg-gain/10 text-gain' : 'bg-indigo/10 text-indigo'
              }`}>{dep.mode} — {dep.status}</span>
            )}
          </div>
        </div>
        <button onClick={() => navigate(-1)} className="text-sm text-muted hover:text-ink">&larr; Back</button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-hairline">
        {(['overview', 'validation', 'live'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize ${tab === t ? 'border-b-2 border-indigo text-ink' : 'text-muted hover:text-ink'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* ===== Overview tab ===== */}
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

      {/* ===== Validation tab ===== */}
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
        </div>
      )}

      {/* ===== Live tab ===== */}
      {tab === 'live' && (
        <div className="rounded-lg border border-hairline bg-surface p-8 text-center">
          <p className="text-muted">Live monitoring data will appear when this strategy is deployed</p>
        </div>
      )}

      {/* ===== Action bar — state-driven ===== */}
      <div className="rounded-lg border border-hairline bg-surface p-4">
        <h3 className="font-display text-sm text-muted mb-3">Actions</h3>

        {/* draft / backtested → Validate */}
        {(s.state === 'draft' || s.state === 'backtested') && (
          <button
            onClick={handleValidate}
            disabled={validateMutation.isPending}
            className={`${btnPrimary} bg-indigo text-white hover:bg-indigo/90`}
          >
            {validateMutation.isPending ? 'Running gauntlet...' : 'Run Validation'}
          </button>
        )}

        {/* validated → Approve + Reject */}
        {s.state === 'validated' && (
          <div className="space-y-3">
            <textarea
              value={reason}
              onChange={e => setReason(e.target.value)}
              placeholder="Reason for decision..."
              className="w-full px-3 py-2 bg-inset border border-hairline rounded-lg text-sm resize-none h-20"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={handleReject}
                disabled={rejectMutation.isPending}
                className={`${btnGhost} text-loss hover:bg-loss/5`}
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
              </button>
              <button
                onClick={handleApprove}
                disabled={approveMutation.isPending}
                className={`${btnPrimary} bg-indigo text-white hover:bg-indigo/90`}
              >
                {approveMutation.isPending ? 'Approving...' : 'Approve & Deploy'}
              </button>
            </div>
          </div>
        )}

        {/* approved (no deployment yet) → Deploy Config */}
        {s.state === 'approved' && !isDeployed && (
          <button
            onClick={() => setShowDeployModal(true)}
            className={`${btnPrimary} bg-indigo text-white hover:bg-indigo/90`}
          >
            Configure Paper Deployment
          </button>
        )}

        {/* paper deployment → Promote / Pause / Flatten / Retire */}
        {dep?.mode === 'paper' && dep.status === 'active' && (
          <div className="flex gap-2">
            <button
              onClick={handlePromote}
              disabled={promoteMutation.isPending}
              className={`${btnPrimary} bg-indigo text-white hover:bg-indigo/90`}
            >
              {promoteMutation.isPending ? 'Promoting...' : 'Promote to Live'}
            </button>
            <button onClick={handlePause} disabled={pauseMutation.isPending}
              className={`${btnGhost} text-ink hover:bg-inset`}>
              {pauseMutation.isPending ? 'Pausing...' : 'Pause'}
            </button>
            <button onClick={handleFlatten} disabled={flattenMutation.isPending}
              className={`${btnGhost} text-ink hover:bg-inset`}>
              {flattenMutation.isPending ? 'Flattening...' : 'Flatten'}
            </button>
            <button onClick={handleRetire} disabled={retireMutation.isPending}
              className={`${btnGhost} text-loss hover:bg-loss/5`}>
              {retireMutation.isPending ? 'Retiring...' : 'Retire'}
            </button>
          </div>
        )}

        {/* live deployment → Pause / Flatten / Retire */}
        {dep?.mode === 'live' && dep.status === 'active' && (
          <div className="flex gap-2">
            <button onClick={handlePause} disabled={pauseMutation.isPending}
              className={`${btnGhost} text-ink hover:bg-inset`}>
              {pauseMutation.isPending ? 'Pausing...' : 'Pause'}
            </button>
            <button onClick={handleFlatten} disabled={flattenMutation.isPending}
              className={`${btnGhost} text-ink hover:bg-inset`}>
              {flattenMutation.isPending ? 'Flattening...' : 'Flatten'}
            </button>
            <button onClick={handleRetire} disabled={retireMutation.isPending}
              className={`${btnGhost} text-loss hover:bg-loss/5`}>
              {retireMutation.isPending ? 'Retiring...' : 'Retire'}
            </button>
          </div>
        )}

        {/* paused deployment → resume is just unpause */}
        {dep?.status === 'paused' && (
          <div className="flex gap-2">
            <span className="text-sm text-muted self-center">Deployment paused.</span>
            <button onClick={handleRetire} disabled={retireMutation.isPending}
              className={`${btnGhost} text-loss hover:bg-loss/5`}>
              {retireMutation.isPending ? 'Retiring...' : 'Retire'}
            </button>
          </div>
        )}

        {/* rejected → info only */}
        {s.state === 'rejected' && (
          <p className="text-sm text-muted">This strategy was rejected. Reason is recorded in the audit log.</p>
        )}

        {/* retired → info only */}
        {s.state === 'retired' && (
          <p className="text-sm text-muted">This strategy has been retired.</p>
        )}
      </div>

      {/* ===== Deploy Config Modal ===== */}
      {showDeployModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-lg border border-hairline bg-paper p-6 shadow-xl space-y-4">
            <h2 className="font-display text-lg text-ink">Deploy Configuration</h2>
            <p className="text-sm text-muted">Configure paper deployment for <strong>{s.name}</strong></p>

            <div>
              <label className="block text-xs text-muted mb-1">Capital Budget ($)</label>
              <input
                type="number"
                value={deployCapital}
                onChange={e => setDeployCapital(e.target.value)}
                placeholder="e.g. 50000"
                className="w-full bg-inset border border-hairline rounded px-3 py-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-indigo"
              />
            </div>

            <div>
              <label className="block text-xs text-muted mb-1">Guardrails (JSON, optional)</label>
              <textarea
                value={deployGuardrails}
                onChange={e => setDeployGuardrails(e.target.value)}
                placeholder='{"per_trade_stop_pct": 3.0, "max_position_pct": 5.0}'
                rows={3}
                className="w-full bg-inset border border-hairline rounded px-3 py-2 text-sm text-ink font-mono resize-none focus:outline-none focus:ring-1 focus:ring-indigo"
              />
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <button
                onClick={() => setShowDeployModal(false)}
                className={`${btnGhost} text-muted hover:text-ink`}
              >
                Cancel
              </button>
              <button
                onClick={handleDeploy}
                disabled={deployMutation.isPending}
                className={`${btnPrimary} bg-indigo text-white hover:bg-indigo/90`}
              >
                {deployMutation.isPending ? 'Deploying...' : 'Deploy to Paper'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
