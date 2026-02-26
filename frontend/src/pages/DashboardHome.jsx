import React, { useState, useEffect } from 'react'
import { fetchBusinessOverview, queryCopilot } from '../api'
import DynamicDashboardRenderer from '../components/DynamicDashboardRenderer'
import DashboardRendererErrorBoundary from '../components/DashboardRendererErrorBoundary'
import ErrorBanner from '../components/ErrorBanner'

function Skeleton({ className = '' }) {
  return <div className={`animate-pulse bg-pink-100/50 rounded-xl ${className}`} />
}

export default function DashboardHome() {
  const [overview, setOverview] = useState(null)
  const [copilotSummary, setCopilotSummary] = useState(null)
  const [copilotLayout, setCopilotLayout] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copilotLoading, setCopilotLoading] = useState(false)
  const [copilotError, setCopilotError] = useState(null)

  const loadOverview = () => {
    setLoading(true)
    setError(null)
    fetchBusinessOverview()
      .then((data) => {
        setOverview(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }

  useEffect(() => {
    loadOverview()
  }, [])

  const askCopilot = () => {
    setCopilotSummary(null)
    setCopilotLayout(null)
    setCopilotError(null)
    setCopilotLoading(true)
    queryCopilot({ query: 'How am I performing?' })
      .then((res) => {
        setCopilotSummary(res.summary)
        if (res.layout) setCopilotLayout(res.layout)
        setCopilotLoading(false)
      })
      .catch((err) => {
        setCopilotError(err.message || 'Request failed')
        setCopilotLoading(false)
      })
  }

  if (loading && !overview) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28 flex-1" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    )
  }

  if (error) {
    return <ErrorBanner message={error} onRetry={loadOverview} />
  }

  const rev = overview?.total_revenue ?? 0
  const sp = overview?.total_spend ?? 0
  const roas = overview?.blended_roas ?? 0
  const cr = overview?.conversion_rate ?? 0
  const revTrend = overview?.revenue_trend_7d ?? 0
  const spTrend = overview?.spend_trend_7d ?? 0

  const trendUp = '↑'
  const trendDown = '↓'
  const trendFlat = '—'

  return (
    <div className="space-y-6">
      <p className="text-xs font-medium text-slate-500">Last 30 days</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Revenue</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">{typeof rev === 'number' ? rev.toLocaleString(undefined, { minimumFractionDigits: 2 }) : rev}</p>
          <p className={`text-xs mt-1 font-medium ${revTrend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {revTrend > 0 ? trendUp : revTrend < 0 ? trendDown : trendFlat} 7d
          </p>
        </div>
        <div className="glass-card p-5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Spend</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">{typeof sp === 'number' ? sp.toLocaleString(undefined, { minimumFractionDigits: 2 }) : sp}</p>
          <p className={`text-xs mt-1 font-medium ${spTrend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {spTrend > 0 ? trendUp : spTrend < 0 ? trendDown : trendFlat} 7d
          </p>
        </div>
        <div className="glass-card p-5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Blended ROAS</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">{typeof roas === 'number' ? roas.toFixed(2) : roas}</p>
        </div>
        <div className="glass-card p-5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Conversion Rate</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">{typeof cr === 'number' ? (cr * 100).toFixed(2) + '%' : cr}</p>
        </div>
      </div>

      {copilotLayout && (
        <DashboardRendererErrorBoundary>
          <DynamicDashboardRenderer layout={copilotLayout} />
        </DashboardRendererErrorBoundary>
      )}

      <div className="glass-card p-5">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Copilot summary</h3>
          <button
            type="button"
            onClick={askCopilot}
            disabled={copilotLoading}
            className="text-sm font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {copilotLoading ? 'Loading…' : 'Ask Copilot: How am I performing?'}
          </button>
        </div>
        {copilotError && (
          <ErrorBanner message={copilotError} onRetry={askCopilot} className="mt-3" />
        )}
        {copilotSummary && <p className="mt-2 text-slate-600">{copilotSummary}</p>}
        {!copilotSummary && !copilotLoading && !copilotError && (
          <p className="mt-2 text-slate-500 text-sm">Click the button above to get a short performance summary from Copilot.</p>
        )}
      </div>
    </div>
  )
}
