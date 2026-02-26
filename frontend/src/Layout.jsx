import React from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Megaphone,
  Target,
  BarChart3,
  Filter,
  Zap,
  Lightbulb,
} from 'lucide-react'

const MAIN_NAV = [
  { id: 'dashboard', path: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { id: 'campaigns', path: '/campaigns', label: 'Campaigns', Icon: Megaphone },
]

const SOURCES_NAV = [
  { id: 'google-ads', path: '/google-ads', label: 'Google Ads', Icon: Target },
  { id: 'google-analytics', path: '/google-analytics', label: 'Google Analytics', Icon: BarChart3 },
  { id: 'funnel', path: '/funnel', label: 'Funnel', Icon: Filter },
]

const SYSTEM_NAV = [
  { id: 'actions', path: '/actions', label: 'Actions', Icon: Zap },
  { id: 'insights', path: '/insights', label: 'Insights', Icon: Lightbulb },
]

function NavSection({ items, path, navigate }) {
  return (
    <>
      {items.map((item) => {
        const active = path.startsWith(item.path)
        const Icon = item.Icon
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => navigate(item.path)}
            aria-current={active ? 'page' : undefined}
            className={`w-full flex items-center gap-3 rounded-none pl-3 pr-3 py-2.5 text-sm font-medium transition-colors border-l-2 ${
              active
                ? 'border-accent bg-white/5 text-white'
                : 'border-transparent text-slate-400 hover:bg-white/5 hover:text-slate-200'
            }`}
          >
            <Icon
              className={`flex-shrink-0 ${active ? 'text-accent' : 'text-slate-400'}`}
              size={20}
              strokeWidth={2}
              aria-hidden
            />
            {item.label}
          </button>
        )
      })}
    </>
  )
}

export default function Layout({ children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const path = location.pathname || '/dashboard'

  const showAnalyticsSidebar = path !== '/copilot'

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {showAnalyticsSidebar && (
        <aside className="w-60 flex-shrink-0 flex flex-col h-full bg-gradient-to-b from-slate-900 to-slate-800 text-white shadow-glass border-r border-white/10 overflow-hidden">
          <div className="p-4 border-b border-white/10 flex-shrink-0">
            <div className="flex items-center gap-2">
              <div>
                <h1 className="text-lg font-semibold tracking-tight">
                  <span className="text-white">HypeOn</span>{' '}
                  <span className="text-accent">Analytics</span>
                </h1>
              </div>
            </div>
          </div>
          <nav className="flex-1 min-h-0 py-2 space-y-0.5 overflow-y-auto scrollbar-sidebar" aria-label="Main">
            <NavSection items={MAIN_NAV} path={path} navigate={navigate} />
            <div className="pt-3 pb-1">
              <p className="px-3 py-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">Sources</p>
              <div className="space-y-0.5 mt-1">
                <NavSection items={SOURCES_NAV} path={path} navigate={navigate} />
              </div>
            </div>
            <div className="pt-2 pb-1">
              <p className="px-3 py-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">System</p>
              <div className="space-y-0.5 mt-1">
                <NavSection items={SYSTEM_NAV} path={path} navigate={navigate} />
              </div>
            </div>
          </nav>
          <div className="p-3 border-t border-white/10 text-xs text-slate-500 flex-shrink-0">
            Enterprise
          </div>
        </aside>
      )}
      <main className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
        {children || <Outlet />}
      </main>
    </div>
  )
}
