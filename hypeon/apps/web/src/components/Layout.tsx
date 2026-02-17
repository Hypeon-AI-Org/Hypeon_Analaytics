import { ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Data & Model Health', description: 'Dashboard & health' },
  { to: '/metrics', label: 'Metrics', description: 'Spend & revenue by channel' },
  { to: '/decisions', label: 'Decisions', description: 'Recommendations' },
  { to: '/report', label: 'Attribution vs MMM', description: 'Alignment report' },
  { to: '/copilot', label: 'Copilot', description: 'Ask in plain language', highlight: true },
]

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const isCopilot = location.pathname === '/copilot'

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <aside className="w-full md:w-56 lg:w-64 shrink-0 bg-white border-b md:border-b-0 md:border-r border-surface-200">
        <div className="p-4 border-b border-surface-200">
          <h1 className="font-display font-semibold text-lg text-surface-900">HypeOn</h1>
          <p className="text-xs text-surface-500 mt-0.5">Analytics</p>
        </div>
        <nav className="p-2 space-y-0.5">
          {navItems.map(({ to, label, description, highlight }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex flex-col gap-0.5 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  highlight
                    ? 'bg-brand-50 text-brand-700 hover:bg-brand-100'
                    : isActive
                    ? 'bg-surface-100 text-surface-900 font-medium'
                    : 'text-surface-600 hover:bg-surface-50 hover:text-surface-800'
                }`
              }
            >
              <span className="font-medium">{label}</span>
              <span className="text-xs opacity-80">{description}</span>
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto p-3 border-t border-surface-200 text-xs text-surface-500">
          Dashboard for specialists · Copilot for founders
        </div>
      </aside>
      <main className={`flex-1 flex flex-col min-h-0 ${isCopilot ? 'bg-surface-50 overflow-hidden' : 'bg-surface-50 overflow-auto'}`}>
        {children}
      </main>
    </div>
  )
}
