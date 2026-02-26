import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { User, Sparkles } from 'lucide-react'
import Layout from './Layout'
import DashboardOverview from './pages/DashboardOverview'
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

function AnalyticsCopilotSwitch() {
  const location = useLocation()
  const navigate = useNavigate()
  const isCopilot = location.pathname === '/copilot'

  return (
    <div
      role="tablist"
      aria-label="Analytics or Copilot view"
      className="inline-flex rounded-lg border border-slate-200 bg-slate-100/80 p-0.5"
    >
      <button
        type="button"
        role="tab"
        aria-selected={!isCopilot}
        onClick={() => navigate('/dashboard')}
        className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          !isCopilot
            ? 'bg-white text-slate-800 shadow-sm border border-slate-200/80'
            : 'text-slate-600 hover:text-slate-800'
        }`}
      >
        Analytics
      </button>
        <button
        type="button"
        role="tab"
        aria-selected={isCopilot}
        onClick={() => navigate('/copilot')}
        className={`inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
          isCopilot
            ? 'bg-white text-slate-800 shadow-sm border border-slate-200/80'
            : 'text-slate-600 hover:text-slate-800'
        }`}
      >
        <Sparkles size={14} strokeWidth={2} aria-hidden />
        Copilot
      </button>
    </div>
  )
}

function PageHeader() {
  const location = useLocation()
  const path = location.pathname || '/dashboard'
  const title = path === '/dashboard' ? 'Dashboard Overview' : (PAGE_TITLES[path] || PAGE_TITLES['/dashboard'])

  return (
    <header className="flex-shrink-0 border-b border-slate-200 bg-white px-6 py-4 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-bold text-slate-800">{title}</h2>
      </div>
      <div className="flex items-center gap-3">
        <AnalyticsCopilotSwitch />
        <button type="button" aria-label="Profile" className="p-1.5 rounded-full bg-slate-200 text-slate-600 hover:bg-slate-300 transition-colors">
          <User size={20} strokeWidth={2} />
        </button>
      </div>
    </header>
  )
}

function MainContent({ openCopilotForInsight }) {
  const location = useLocation()
  const path = location.pathname || '/dashboard'
  const isCopilot = path === '/copilot'

  return (
    <>
      {!isCopilot && <PageHeader />}
      <div className={`flex-1 flex flex-col min-h-0 ${isCopilot ? 'overflow-hidden' : 'overflow-auto'}`}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardOverview />} />
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
      <Layout>
        <MainContent openCopilotForInsight={openCopilotForInsight} />
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
