import React from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'

const NAV = [
  { id: 'dashboard', path: '/dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'campaigns', path: '/campaigns', label: 'Campaigns', icon: '📈' },
  { id: 'funnel', path: '/funnel', label: 'Funnel', icon: '🔻' },
  { id: 'actions', path: '/actions', label: 'Actions', icon: '⚡' },
  { id: 'insights', path: '/insights', label: 'Insights', icon: '💡' },
  { id: 'copilot', path: '/copilot', label: 'Copilot', icon: '🤖' },
]

export default function Layout({ copilotOpen, onOpenCopilot, onCloseCopilot, explainInsightId, children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const path = location.pathname || '/dashboard'

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="w-56 flex-shrink-0 bg-slate-900 text-white flex flex-col">
        <div className="p-4 border-b border-slate-700">
          <h1 className="text-lg font-semibold tracking-tight text-white">HypeOn</h1>
          <p className="text-xs text-slate-400 mt-0.5">Analytics V1</p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5" aria-label="Main">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                path.startsWith(item.path)
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <span className="text-base" aria-hidden>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-slate-700 text-xs text-slate-500">
          Enterprise
        </div>
      </aside>
      <main className="flex-1 flex flex-col min-w-0">
        {children || <Outlet />}
      </main>
    </div>
  )
}
