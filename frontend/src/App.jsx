import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './Layout'
import DashboardHome from './pages/DashboardHome'
import CampaignPage from './pages/CampaignPage'
import FunnelPage from './pages/FunnelPage'
import ActionCenterPage from './pages/ActionCenterPage'
import InsightsList from './InsightsList'
import CopilotChat from './CopilotChat'
import CopilotPanel from './components/CopilotPanel'
import GoogleAdsPage from './pages/GoogleAdsPage'
import GoogleAnalyticsPage from './pages/GoogleAnalyticsPage'

const PAGE_TITLES = {
  '/campaigns': 'Campaigns',
  '/google-ads': 'Google Ads Analysis',
  '/google-analytics': 'Google Analytics',
  '/funnel': 'Funnel',
  '/actions': 'Action Center',
  '/insights': 'Insights',
  '/copilot': 'Copilot',
  '/dashboard': 'Dashboard',
  '/': 'Dashboard',
}

function AppHeader({ onOpenCopilot }) {
  const location = useLocation()
  const path = location.pathname || '/dashboard'
  const title = PAGE_TITLES[path] || PAGE_TITLES['/dashboard']

  return (
    <header className="flex-shrink-0 border-b border-pink-100/60 bg-white/70 backdrop-blur-md px-6 py-4 flex items-center justify-between">
      <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
      <button
        type="button"
        onClick={() => onOpenCopilot('What should I do today?')}
        className="flex items-center gap-2 rounded-xl border border-brand-200 bg-white/90 px-3 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50 transition-colors"
      >
        <span aria-hidden>◎</span>
        Open Copilot
      </button>
    </header>
  )
}

function MainContent({ onOpenCopilot, openCopilotForInsight }) {
  const location = useLocation()
  const path = location.pathname || '/dashboard'
  const isCopilot = path === '/copilot'

  return (
    <>
      {!isCopilot && <AppHeader onOpenCopilot={onOpenCopilot} />}
      <div className={isCopilot ? 'flex-1 flex flex-col min-h-0' : 'flex-1 overflow-auto px-6 py-6'}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardHome />} />
          <Route path="/campaigns" element={<CampaignPage />} />
          <Route path="/google-ads" element={<GoogleAdsPage />} />
          <Route path="/google-analytics" element={<GoogleAnalyticsPage />} />
          <Route path="/funnel" element={<FunnelPage />} />
          <Route path="/actions" element={<ActionCenterPage onExplain={openCopilotForInsight} />} />
          <Route path="/insights" element={<InsightsList />} />
          <Route path="/copilot" element={<CopilotChat />} />
        </Routes>
      </div>
    </>
  )
}

export default function App() {
  const [copilotOpen, setCopilotOpen] = useState(false)
  const [explainInsightId, setExplainInsightId] = useState(null)
  const [copilotQuery, setCopilotQuery] = useState('What should I do today?')

  const openCopilot = (initialQuery) => {
    setCopilotQuery(initialQuery || 'What should I do today?')
    setExplainInsightId(null)
    setCopilotOpen(true)
  }

  const openCopilotForInsight = (insightId) => {
    setCopilotQuery('Explain this recommendation')
    setExplainInsightId(insightId)
    setCopilotOpen(true)
  }

  return (
    <BrowserRouter>
      <Layout
        copilotOpen={copilotOpen}
        onOpenCopilot={openCopilot}
        onCloseCopilot={() => setCopilotOpen(false)}
        explainInsightId={explainInsightId}
      >
        <MainContent onOpenCopilot={openCopilot} openCopilotForInsight={openCopilotForInsight} />
      </Layout>
      <CopilotPanel
        open={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        initialQuery={copilotQuery}
        explainInsightId={explainInsightId}
      />
    </BrowserRouter>
  )
}
