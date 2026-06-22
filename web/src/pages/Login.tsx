import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { apiFetch } from '../lib/api'

export function LoginPage() {
  const { login, register, user } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isSetup, setIsSetup] = useState(true)

  useEffect(() => {
    if (user) navigate('/portfolio', { replace: true })
  }, [user, navigate])

  useEffect(() => {
    apiFetch<{ configured: boolean }>('/api/auth/setup-status')
      .then(r => setIsSetup(r.configured))
      .catch(() => {})
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isSetup) {
        await login(email, password)
      } else {
        await register(email, password)
      }
      navigate('/portfolio', { replace: true })
    } catch {
      setError(isSetup ? 'Invalid credentials' : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="font-display text-2xl text-ink">Quanta</h1>
          <p className="text-sm text-muted mt-1">
            {isSetup ? 'Sign in to continue' : 'Create your account'}
          </p>
        </div>
        <form onSubmit={handleSubmit} className="bg-surface border border-hairline rounded-lg p-6 space-y-4">
          {error && (
            <div className="text-sm text-loss bg-[var(--color-loss)]/10 border border-loss/20 rounded px-3 py-2">
              {error}
            </div>
          )}
          <div>
            <label htmlFor="email" className="block text-xs text-muted mb-1">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-inset border border-hairline rounded px-3 py-2 text-sm text-ink placeholder:text-faint focus:outline-none focus:ring-1 focus:ring-indigo"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-xs text-muted mb-1">Password</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-inset border border-hairline rounded px-3 py-2 text-sm text-ink placeholder:text-faint focus:outline-none focus:ring-1 focus:ring-indigo"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[var(--color-indigo)] text-white rounded py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading ? 'Please wait...' : isSetup ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  )
}
