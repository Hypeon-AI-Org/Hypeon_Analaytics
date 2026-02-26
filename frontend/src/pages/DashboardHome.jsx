import React, { useState, useEffect, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Star,
  ShoppingCart,
  LineChart as LineChartIcon,
  Search,
  Filter as FilterIcon,
} from 'lucide-react'
import {
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { fetchBusinessOverview, fetchCampaignPerformance, queryCopilot } from '../api'
import DynamicDashboardRenderer from '../components/DynamicDashboardRenderer'
import DashboardRendererErrorBoundary from '../components/DashboardRendererErrorBoundary'
import ErrorBanner from '../components/ErrorBanner'
import CampaignTable from '../components/CampaignTable'
import PageReportHeader from '../components/PageReportHeader'

function Skeleton({ className = '' }) {
  return <div className={`animate-pulse bg-slate-100 rounded-xl ${className}`} />
}

// Generate mock daily trend data from totals (API doesn't return daily series). Deterministic per total/days.
function useDailyTrend(total, days = 30) {
  return useMemo(() => {
    const base = Number(total) || 0
    const avg = base / days
    const points = []
    const now = new Date()
    const seed = total * 7 + days * 13
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      const t = (i / days) * Math.PI * 2
      const variance = 0.25 * avg * Math.sin(t) + 0.1 * avg * ((seed + i) % 7 - 3) / 7
      points.push({
        date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        value: Math.max(0, avg + variance),
      })
    }
    return points
  }, [total, days])
}

export default function DashboardHome() {
  const [overview, setOverview] = useState(null)
  const [campaigns, setCampaigns] = useState({ items: [] })
  const [campaignFilter, setCampaignFilter] = useState('')
  const [copilotSummary, setCopilotSummary] = useState(null)
  const [copilotLayout, setCopilotLayout] = useState(null)
  const [loading, setLoading] = useState(true)
  const [campaignsLoading, setCampaignsLoading] = useState(true)
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

  useEffect(() => {
    setCampaignsLoading(true)
    fetchCampaignPerformance()
      .then((data) => {
        setCampaigns(data)
        setCampaignsLoading(false)
      })
      .catch(() => setCampaignsLoading(false))
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

  const rev = overview?.total_revenue ?? 0
  const sp = overview?.total_spend ?? 0
  const roas = overview?.blended_roas ?? 0
  const cr = overview?.conversion_rate ?? 0
  const revTrend = Number(overview?.revenue_trend_7d ?? 0)
  const spTrendNum = Number(overview?.spend_trend_7d ?? 0)

  const revenueDaily = useDailyTrend(rev, 30)
  const spendDaily = useDailyTrend(sp, 30)

  const filteredCampaigns = useMemo(() => {
    const list = campaigns?.items ?? []
    if (!campaignFilter.trim()) return list
    const q = campaignFilter.trim().toLowerCase()
    return list.filter((c) => (c.campaign || '').toLowerCase().includes(q))
  }, [campaigns?.items, campaignFilter])

  if (loading && !overview) {
    return (
      <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32 flex-1" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 overflow-auto px-6 py-6">
        <ErrorBanner message={error} onRetry={loadOverview} />
      </div>
    )
  }

  const revPct = (revTrend * 100).toFixed(1)
  const spPct = (spTrendNum * 100).toFixed(1)

  return (
    <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
      <PageReportHeader days={30} onExport={() => {}} />

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-5 relative">
          <div className="absolute top-4 right-4 text-slate-400">
            <LineChartIcon size={20} strokeWidth={2} />
          </div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Revenue</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">
            {typeof rev === 'number' ? `$${rev.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : rev}
          </p>
          <p className={`mt-1 flex items-center gap-1 text-xs font-medium ${revTrend >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {revTrend > 0 ? <TrendingUp size={14} /> : revTrend < 0 ? <TrendingDown size={14} /> : null}
            {revTrend > 0 ? `+${revPct}%` : revTrend < 0 ? `${revPct}%` : '0.0%'} vs. previous period
          </p>
        </div>
        <div className="glass-card p-5 relative">
          <div className="absolute top-4 right-4 text-slate-400">
            <Wallet size={20} strokeWidth={2} />
          </div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Spend</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">
            {typeof sp === 'number' ? `$${sp.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : sp}
          </p>
          <p className={`mt-1 flex items-center gap-1 text-xs font-medium ${spTrendNum >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>
            {spTrendNum > 0 ? <TrendingUp size={14} /> : spTrendNum < 0 ? <TrendingDown size={14} /> : null}
            {spTrendNum > 0 ? `+${spPct}%` : spTrendNum < 0 ? `${spPct}%` : '0.0%'} vs. previous period
          </p>
        </div>
        <div className="glass-card p-5 relative">
          <div className="absolute top-4 right-4 text-slate-400">
            <Star size={20} strokeWidth={2} />
          </div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Blended ROAS</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">{typeof roas === 'number' ? `${roas.toFixed(2)}x` : roas}</p>
          <p className="mt-1 text-xs text-slate-500">Target: 5.50x</p>
          <p className={`mt-0.5 flex items-center gap-1 text-xs font-medium text-emerald-600`}>+4.1%</p>
        </div>
        <div className="glass-card p-5 relative">
          <div className="absolute top-4 right-4 text-slate-400">
            <ShoppingCart size={20} strokeWidth={2} />
          </div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Conversion Rate</p>
          <p className="mt-1 text-2xl font-bold text-slate-800">
            {typeof cr === 'number' ? `${(cr * 100).toFixed(2)}%` : cr}
          </p>
          <p className="mt-1 text-xs text-slate-500">Average: 0.52%</p>
          <p className="mt-0.5 text-xs font-medium text-slate-500">0.0%</p>
        </div>
      </div>

      {/* Trend charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-slate-800">Revenue Trend</h3>
          <p className="text-xs text-slate-500 mt-0.5">Daily revenue performance</p>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={revenueDaily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v) => [`$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, 'Revenue']} />
                <Area type="monotone" dataKey="value" fill="#38bdf8" fillOpacity={0.2} stroke="none" />
                <Line type="monotone" dataKey="value" stroke="#0ea5e9" strokeWidth={2} dot={false} name="Revenue" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="w-3 h-3 rounded-full bg-accent" />
            <span className="text-xs text-slate-600">Revenue</span>
          </div>
        </div>
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-slate-800">Spend Trend</h3>
          <p className="text-xs text-slate-500 mt-0.5">Daily ad spend distribution</p>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={spendDaily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <Tooltip formatter={(v) => [`$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, 'Spend']} />
                <Area type="monotone" dataKey="value" fill="#64748b" fillOpacity={0.2} stroke="none" />
                <Line type="monotone" dataKey="value" stroke="#475569" strokeWidth={2} dot={false} name="Spend" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="w-3 h-3 rounded-full bg-slate-500" />
            <span className="text-xs text-slate-600">Spend</span>
          </div>
        </div>
      </div>

      {/* Campaign Performance */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">Campaign Performance</h3>
        <div className="flex items-center gap-2 mb-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} strokeWidth={2} />
            <input
              type="text"
              placeholder="Filter campaigns..."
              value={campaignFilter}
              onChange={(e) => setCampaignFilter(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-slate-800 placeholder-slate-400 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button type="button" aria-label="Filter" className="p-2 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50">
            <FilterIcon size={18} strokeWidth={2} />
          </button>
        </div>
        <CampaignTable items={filteredCampaigns} loading={campaignsLoading} />
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
