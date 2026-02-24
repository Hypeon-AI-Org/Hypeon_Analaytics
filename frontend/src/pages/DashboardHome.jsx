import React, { useState, useEffect } from 'react'
import { fetchBusinessOverview, queryCopilot } from '../api'
import DynamicDashboardRenderer from '../components/DynamicDashboardRenderer'
import DashboardRendererErrorBoundary from '../components/DashboardRendererErrorBoundary'

function Skeleton({ className = '' }) {
  return <div className={`animate-pulse bg-slate-200 rounded ${className}`} />
}

export default function DashboardHome() {
  const [overview, setOverview] = useState(null)
  const [copilotSummary, setCopilotSummary] = useState(null)
  const [copilotLayout, setCopilotLayout] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchBusinessOverview()
      .then((data) => {
        setOverview(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  const askCopilot = () => {
    setCopilotSummary(null)
    setCopilotLayout(null)
    queryCopilot({ query: 'How am I performing?' })
      .then((res) => {
        setCopilotSummary(res.summary)
        if (res.layout) setCopilotLayout(res.layout)
      })
      .catch(() => {})
  }

  if (loading && !overview) {
    return (
      <div className="space-y-6">
        <div className="flex gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 flex-1" />
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
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3" role="alert">
        {error}
      </div>
    )
  }

  const rev = overview?.total_revenue ?? 0
  const sp = overview?.total_spend ?? 0
  const roas = overview?.blended_roas ?? 0
  const cr = overview?.conversion_rate ?? 0
  const revTrend = overview?.revenue_trend_7d ?? 0
  const spTrend = overview?.spend_trend_7d ?? 0

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Total Revenue</p>
          <p className="text-2xl font-semibold text-slate-800">{rev}</p>
          <p className={`text-xs mt-1 ${revTrend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{revTrend >= 0 ? '↑' : '↓'} 7d</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Total Spend</p>
          <p className="text-2xl font-semibold text-slate-800">{sp}</p>
          <p className={`text-xs mt-1 ${spTrend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{spTrend >= 0 ? '↑' : '↓'} 7d</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Blended ROAS</p>
          <p className="text-2xl font-semibold text-slate-800">{typeof roas === 'number' ? roas.toFixed(2) : roas}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-medium text-slate-500">Conversion Rate</p>
          <p className="text-2xl font-semibold text-slate-800">{typeof cr === 'number' ? (cr * 100).toFixed(2) + '%' : cr}</p>
        </div>
      </div>

      {copilotLayout && (
        <DashboardRendererErrorBoundary>
          <DynamicDashboardRenderer layout={copilotLayout} />
        </DashboardRendererErrorBoundary>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-slate-700">Copilot summary</h3>
          <button
            type="button"
            onClick={askCopilot}
            className="text-sm text-indigo-600 hover:text-indigo-800"
          >
            Ask Copilot: How am I performing?
          </button>
        </div>
        {copilotSummary && <p className="mt-2 text-slate-600">{copilotSummary}</p>}
      </div>
    </div>
  )
}
