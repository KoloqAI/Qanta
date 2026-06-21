import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { cn } from '../lib/cn'

const NAV_GROUPS = [
  {
    label: 'Work',
    items: [{ to: '/assistant', label: 'Assistant' }],
  },
  {
    label: 'Your Book',
    items: [
      { to: '/portfolio', label: 'Portfolio' },
      { to: '/monitor', label: 'Monitor' },
      { to: '/performance', label: 'Performance' },
    ],
  },
  {
    label: 'Strategies',
    items: [
      { to: '/review', label: 'Review Queue' },
      { to: '/registry', label: 'Registry' },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/evolution', label: 'Evolution' },
      { to: '/settings', label: 'Settings' },
    ],
  },
]

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      {/* Top status bar */}
      <header className="sticky top-0 z-50 flex items-center justify-between border-b border-hairline bg-surface px-4 py-2">
        <div className="flex items-center gap-4">
          <span className="font-display text-sm text-ink font-medium">Quanta</span>
          <span className="text-xs text-muted">Paper</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gain">Data OK</span>
          <span className="text-xs text-muted">Kill switch: off</span>
          <span className="text-xs text-muted">{user?.email}</span>
          <button onClick={handleLogout} className="text-xs text-muted hover:text-ink">
            Sign out
          </button>
        </div>
      </header>

      <div className="flex flex-1">
        {/* Sidebar */}
        <nav className="w-52 shrink-0 border-r border-hairline bg-surface py-4 px-3 space-y-5 overflow-y-auto">
          {NAV_GROUPS.map(group => (
            <div key={group.label}>
              <p className="text-[11px] font-medium text-faint uppercase tracking-wider px-2 mb-1">
                {group.label}
              </p>
              {group.items.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'block rounded px-2 py-1.5 text-sm transition-colors',
                      isActive
                        ? 'bg-indigo-soft text-indigo font-medium'
                        : 'text-muted hover:text-ink hover:bg-inset'
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
