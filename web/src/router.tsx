import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './lib/auth'
import { LoginPage } from './pages/Login'
import { AppShell } from './components/AppShell'
import { PortfolioPage } from './pages/Portfolio'
import { AssistantPage } from './pages/Assistant'
import { MonitorPage } from './pages/Monitor'
import { PerformancePage } from './pages/Performance'
import { ReviewQueuePage } from './pages/ReviewQueue'
import { RegistryPage } from './pages/Registry'
import { BacktestSandboxPage } from './pages/BacktestSandbox'
import { EvolutionPage } from './pages/Evolution'
import { SettingsPage } from './pages/Settings'
import { StrategyDetailPage } from './pages/StrategyDetail'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen bg-paper" />
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/portfolio" replace />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/monitor" element={<MonitorPage />} />
        <Route path="/performance" element={<PerformancePage />} />
        <Route path="/review" element={<ReviewQueuePage />} />
        <Route path="/registry" element={<RegistryPage />} />
        <Route path="/backtest" element={<BacktestSandboxPage />} />
        <Route path="/evolution" element={<EvolutionPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/strategy/:id" element={<StrategyDetailPage />} />
        <Route path="/strategies/:id" element={<StrategyDetailPage />} />
      </Route>
    </Routes>
  )
}
