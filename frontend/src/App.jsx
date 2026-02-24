import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './Layout'
import DashboardHome from './pages/DashboardHome'
import CampaignPage from './pages/CampaignPage'
import FunnelPage from './pages/FunnelPage'
import ActionCenterPage from './pages/ActionCenterPage'
import InsightsList from './InsightsList'
import CopilotChat from './CopilotChat'
import CopilotPanel from './components/CopilotPanel'

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
        <header className="flex-shrink-0 border-b border-slate-200 bg-white px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">
            {window.location.pathname === '/campaigns' && 'Campaigns'}
            {window.location.pathname === '/funnel' && 'Funnel'}
            {window.location.pathname === '/actions' && 'Action Center'}
            {window.location.pathname === '/insights' && 'Insights'}
            {window.location.pathname === '/copilot' && 'Copilot'}
            {(!window.location.pathname || window.location.pathname === '/' || window.location.pathname === '/dashboard') && 'Dashboard'}
          </h2>
          <button
            type="button"
            onClick={() => openCopilot('What should I do today?')}
            className="text-sm text-indigo-600 hover:text-indigo-800"
          >
            Open Copilot
          </button>
        </header>
        <div className="flex-1 overflow-auto px-6 py-6">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardHome />} />
            <Route path="/campaigns" element={<CampaignPage />} />
            <Route path="/funnel" element={<FunnelPage />} />
            <Route path="/actions" element={<ActionCenterPage onExplain={openCopilotForInsight} />} />
            <Route path="/insights" element={<InsightsList />} />
            <Route path="/copilot" element={<CopilotChat />} />
          </Routes>
        </div>
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
