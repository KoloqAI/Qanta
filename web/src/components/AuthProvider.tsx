import { useState, useEffect, useCallback, type ReactNode } from 'react'
import { AuthContext, type User } from '../lib/auth'
import { apiFetch } from '../lib/api'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<User>('/api/auth/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<{ user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setUser(res.user)
  }, [])

  const logout = useCallback(async () => {
    await apiFetch('/api/auth/logout', { method: 'POST' })
    setUser(null)
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<User>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setUser(res)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  )
}
