import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { User, Sparkles } from 'lucide-react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { UserOrgProvider, useUserOrg } from './contexts/UserOrgContext'
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
import Login from './pages/Login'
import Signup from './pages/Signup'
import ForgotPassword from './pages/ForgotPassword'

const PAGE_TITLES = {
  '/campaigns': 'Campaigns',
  '/google-ads': 'Google Ads Analysis',
  '/google-analytics': 'Google Analytics',
  '/funnel': 'Funnel',
  '/actions': 'Action Center',
  '/insights': 'Insights',
  '/copilot': 'Copilot',
  '/dashboard': 'Dashboard',
  '/': 'Copilot',
}

function AnalyticsCopilotSwitch() {
  const location = useLocation()
  const navigate = useNavigate()
  const isCopilot = location.pathname === '/copilot'

  return (
    <div
      role="tablist"
      aria-label="Analytics or Copilot view"
      className="inline-flex rounded-lg border border-slate-200/80 bg-slate-50/80 p-0.5"
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
  const { user, signOut, isConfigured } = useAuth()
  const { clientIds, adChannels, selectedClientId, setSelectedClientId, error: orgError, refetch } = useUserOrg()
  const path = location.pathname || '/copilot'
  const title = path === '/dashboard' ? 'Dashboard Overview' : (PAGE_TITLES[path] || PAGE_TITLES['/copilot'])
  const showClientSelector = clientIds.length > 1

  return (
    <>
      {orgError && (
        <div className="flex-shrink-0 px-6 py-2 bg-slate-100 border-b border-slate-200 text-slate-800 text-sm flex items-center justify-between gap-2">
          <span>{orgError}</span>
          <button type="button" onClick={() => refetch()} className="text-slate-700 font-medium hover:underline">Retry</button>
        </div>
      )}
    <header className="flex-shrink-0 border-b border-slate-200/60 bg-white px-6 py-3 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-bold text-slate-800">{title}</h2>
        {showClientSelector && (
          <select
            value={selectedClientId ?? ''}
            onChange={(e) => {
              const v = e.target.value
              if (v !== '') setSelectedClientId(parseInt(v, 10))
            }}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 bg-white focus:ring-2 focus:ring-slate-400 focus:border-slate-500"
            aria-label="Select dataset / client"
          >
            {adChannels.map((ch) => (
              <option key={ch.client_id} value={ch.client_id}>
                {ch.description || `Client ${ch.client_id}`}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="flex items-center gap-3">
        <AnalyticsCopilotSwitch />
        {isConfigured && user && (
          <button
            type="button"
            onClick={() => signOut()}
            className="text-sm text-slate-600 hover:text-slate-800 font-medium"
          >
            Sign out
          </button>
        )}
        <button type="button" aria-label="Profile" className="p-1.5 rounded-full bg-slate-200 text-slate-600 hover:bg-slate-300 transition-colors">
          <User size={20} strokeWidth={2} />
        </button>
      </div>
    </header>
    </>
  )
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <p className="text-slate-600">Loading…</p>
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}

function MainContent({ openCopilotForInsight }) {
  const location = useLocation()
  const path = location.pathname || '/copilot'
  const isCopilot = path === '/copilot'

  return (
    <>
      {!isCopilot && <PageHeader />}
      <div className={`flex-1 flex flex-col min-h-0 ${isCopilot ? 'overflow-hidden' : 'overflow-auto'}`}>
        <Routes>
          <Route path="/" element={<Navigate to="/copilot" replace />} />
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
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <UserOrgProvider>
                  <Layout>
                    <MainContent openCopilotForInsight={openCopilotForInsight} />
                  </Layout>
                  <CopilotPanel
                  open={copilotOpen}
                  onClose={() => setCopilotOpen(false)}
                  initialQuery={copilotQuery}
                    explainInsightId={explainInsightId}
                  />
                </UserOrgProvider>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
