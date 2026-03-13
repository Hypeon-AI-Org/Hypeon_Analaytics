import React, { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Database,
  Megaphone,
  Target,
  BarChart3,
  Filter,
  Zap,
  Lightbulb,
} from 'lucide-react'

const MAIN_NAV = [
  { id: 'dashboard', path: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { id: 'explore', path: '/explore', label: 'Explore', Icon: Database },
  { id: 'campaigns', path: '/campaigns', label: 'Campaigns', Icon: Megaphone },
]

const SOURCES_NAV = [
  { id: 'google-ads', path: '/google-ads', label: 'Google Ads', Icon: Target },
  { id: 'google-analytics', path: '/google-analytics', label: 'Google Analytics', Icon: BarChart3 },
  { id: 'funnel', path: '/funnel', label: 'Funnel', Icon: Filter },
]

const INSIGHTS_NAV = [
  { id: 'actions', path: '/actions', label: 'Actions', Icon: Zap },
  { id: 'insights', path: '/insights', label: 'Insights', Icon: Lightbulb },
]

function NavSection({ items, path, navigate, sidebarOpen, sectionLabel }) {
  return (
    <div className="space-y-0.5">
      {sectionLabel && sidebarOpen && (
        <p className="px-3 py-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
          {sectionLabel}
        </p>
      )}
      {items.map((item) => {
        const active = path.startsWith(item.path)
        const Icon = item.Icon
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => navigate(item.path)}
            aria-current={active ? 'page' : undefined}
            title={item.label}
            className={`w-full flex items-center gap-3 rounded-lg pl-3 pr-3 py-2.5 text-sm font-medium transition-all border-l-2 ${
              active
                ? 'border-orange-400 bg-white/10 text-white'
                : 'border-transparent text-slate-400 hover:bg-white/5 hover:text-slate-200'
            } ${!sidebarOpen ? 'justify-center px-2' : ''}`}
          >
            <Icon
              className={`flex-shrink-0 ${active ? 'text-white' : 'text-slate-400'}`}
              size={20}
              strokeWidth={2}
              aria-hidden
            />
            {sidebarOpen && <span className="truncate">{item.label}</span>}
          </button>
        )
      })}
    </div>
  )
}

export default function Layout({ children }) {
  const navigate = useNavigate()
  const location = useLocation()
  const path = location.pathname || '/copilot'
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const showAnalyticsSidebar = path !== '/copilot'

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {showAnalyticsSidebar && (
        <aside
          className={`flex-shrink-0 flex flex-col h-full bg-slate-900 text-white overflow-hidden transition-all duration-200 ${
            sidebarOpen ? 'w-60' : 'w-16'
          }`}
        >
          <div className="p-3 flex-shrink-0 flex items-center justify-between gap-2 min-h-[52px]">
            {sidebarOpen ? (
              <h1 className="text-lg font-bold tracking-tight truncate">
                <span className="text-white">HypeOn</span>{' '}
                <span className="text-slate-300">Analytics</span>
              </h1>
            ) : (
              <span className="text-white font-bold text-sm">H</span>
            )}
            <button
              type="button"
              onClick={() => setSidebarOpen((o) => !o)}
              className="p-1.5 rounded-lg text-slate-400 hover:bg-white/10 hover:text-white transition-colors shrink-0"
              aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`w-4 h-4 transition-transform ${sidebarOpen ? '' : 'rotate-180'}`}>
                <path d="M15 19l-7-7 7-7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <nav className="flex-1 min-h-0 py-3 space-y-4 overflow-y-auto scrollbar-sidebar" aria-label="Main">
            <NavSection items={MAIN_NAV} path={path} navigate={navigate} sidebarOpen={sidebarOpen} sectionLabel="Overview" />
            <NavSection items={SOURCES_NAV} path={path} navigate={navigate} sidebarOpen={sidebarOpen} sectionLabel="Sources" />
            <NavSection items={INSIGHTS_NAV} path={path} navigate={navigate} sidebarOpen={sidebarOpen} sectionLabel="Insights" />
          </nav>
          {sidebarOpen && (
            <div className="p-3 text-xs text-slate-500 flex-shrink-0">
              Enterprise
            </div>
          )}
        </aside>
      )}
      <main className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden">
        {children || <Outlet />}
      </main>
    </div>
  )
}
