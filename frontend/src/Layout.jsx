import React, { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { fetchCopilotSessions } from './api'

const NAV = [
  { id: 'dashboard', path: '/dashboard', label: 'Dashboard', symbol: '≡' },
  { id: 'campaigns', path: '/campaigns', label: 'Campaigns', symbol: '▣' },
  { id: 'google-ads', path: '/google-ads', label: 'Google Ads', symbol: '◉' },
  { id: 'google-analytics', path: '/google-analytics', label: 'Google Analytics', symbol: '◐' },
  { id: 'funnel', path: '/funnel', label: 'Funnel', symbol: '▽' },
  { id: 'actions', path: '/actions', label: 'Actions', symbol: '◇' },
  { id: 'insights', path: '/insights', label: 'Insights', symbol: '◆' },
]

function formatSessionDate(ts) {
  if (ts == null) return ''
  const d = new Date(ts * 1000)
  const now = new Date()
  const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return d.toLocaleDateString()
}

export default function Layout({ copilotOpen, onOpenCopilot, onCloseCopilot, explainInsightId, children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const path = location.pathname || '/dashboard'
  const isCopilotPage = path === '/copilot'
  const [sessions, setSessions] = useState([])

  useEffect(() => {
    fetchCopilotSessions()
      .then((r) => setSessions(r.sessions || []))
      .catch(() => setSessions([]))
  }, [path])

  const recentSessions = sessions.slice(0, 8)

  return (
    <div className="flex min-h-screen bg-gradient-app">
      <aside className="w-60 flex-shrink-0 bg-gradient-sidebar text-white flex flex-col shadow-glass border-r border-white/10">
        <div className="p-4 border-b border-white/10">
          <h1 className="text-lg font-semibold tracking-tight text-white">HypeOn</h1>
          <p className="text-xs text-pink-200 mt-0.5">Analytics</p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto" aria-label="Main">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => navigate(item.path)}
              aria-current={path.startsWith(item.path) ? 'page' : undefined}
              className={`w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                path.startsWith(item.path)
                  ? 'bg-white/20 text-white'
                  : 'text-pink-100 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span className="text-base opacity-90" aria-hidden>{item.symbol}</span>
              {item.label}
            </button>
          ))}

          <div className="pt-3 mt-3 border-t border-white/10">
            <div className="flex items-center gap-2 px-3 py-1.5">
              <span className="text-base opacity-90" aria-hidden>◎</span>
              <span className="text-sm font-semibold text-white">Copilot</span>
            </div>
            <button
              type="button"
              onClick={() => navigate('/copilot')}
              aria-current={isCopilotPage ? 'page' : undefined}
              className={`w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isCopilotPage ? 'bg-white/20 text-white' : 'text-pink-100 hover:bg-white/10 hover:text-white'
              }`}
            >
              <span className="text-base" aria-hidden>+</span>
              New chat
            </button>
            {recentSessions.length > 0 && (
              <ul className="mt-1 space-y-0.5 max-h-48 overflow-y-auto">
                {recentSessions.map((s) => (
                  <li key={s.session_id}>
                    <button
                      type="button"
                      onClick={() => navigate('/copilot', { state: { sessionId: s.session_id } })}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs text-pink-100 hover:bg-white/10 hover:text-white truncate block"
                    >
                      <span className="block truncate">{s.title || 'New chat'}</span>
                      <span className="text-pink-200/80">{formatSessionDate(s.updated_at)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </nav>
        <div className="p-3 border-t border-white/10 text-xs text-pink-200/80">
          Enterprise
        </div>
      </aside>
      <main className="flex-1 flex flex-col min-w-0">
        {children || <Outlet />}
      </main>
    </div>
  )
}
