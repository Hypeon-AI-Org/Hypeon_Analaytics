import React, { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid, Area, AreaChart,
} from 'recharts'
import { fetchGoogleAdsAnalysis } from '../api'
import DateRangePicker from '../components/DateRangePicker'
import ErrorBanner from '../components/ErrorBanner'
import PageReportHeader from '../components/PageReportHeader'

const CHART_COLORS = ['#2563eb', '#059669', '#0ea5e9', '#8b5cf6', '#d97706', '#dc2626', '#0891b2', '#7c3aed']

function fmt(v) {
  if (v == null) return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return v
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

function fmtCurrency(v) {
  if (v == null) return '—'
  return '$' + fmt(v)
}

function fmtPct(v) {
  if (v == null) return '—'
  return Number(v).toFixed(2) + '%'
}

function Skeleton({ className = '' }) {
  return <div className={`animate-pulse bg-slate-200 rounded ${className}`} />
}

export default function GoogleAdsPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [params, setParams] = useState({ days: 30 })
  const [campaignSort, setCampaignSort] = useState({ col: 'spend', dir: 'desc' })
  const [adGroupSort, setAdGroupSort] = useState({ col: 'spend', dir: 'desc' })

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchGoogleAdsAnalysis(params)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [params])

  useEffect(() => { load() }, [load])

  const onDateChange = (range) => setParams(range)

  const toggleSort = (current, setCurrent) => (col) => {
    if (current.col === col) setCurrent({ col, dir: current.dir === 'asc' ? 'desc' : 'asc' })
    else setCurrent({ col, dir: 'desc' })
  }

  const sortRows = (rows, { col, dir }) => {
    return [...rows].sort((a, b) => {
      const va = Number(a[col]) || 0
      const vb = Number(b[col]) || 0
      return dir === 'asc' ? va - vb : vb - va
    })
  }

  if (loading && !data) {
    return (
      <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-72" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 overflow-auto px-6 py-6 space-y-4">
        <DateRangePicker onChange={onDateChange} initialDays={params.days} />
        <ErrorBanner message={error} onRetry={load} />
      </div>
    )
  }

  const o = data?.overview || {}
  const ts = data?.daily_timeseries || []
  const campaigns = data?.by_campaign || []
  const devices = data?.by_device || []
  const adGroups = data?.by_ad_group || []

  const kpis = [
    { label: 'Spend', value: fmtCurrency(o.spend) },
    { label: 'Revenue', value: fmtCurrency(o.revenue) },
    { label: 'ROAS', value: fmt(o.roas) + 'x' },
    { label: 'Clicks', value: fmt(o.clicks) },
    { label: 'Impressions', value: fmt(o.impressions) },
    { label: 'Conversions', value: fmt(o.conversions) },
    { label: 'Avg CPC', value: fmtCurrency(o.avg_cpc) },
    { label: 'CTR', value: fmtPct(o.ctr) },
  ]

  const sortedCampaigns = sortRows(campaigns, campaignSort)
  const sortedAdGroups = sortRows(adGroups, adGroupSort)

  const totalDeviceSpend = devices.reduce((s, d) => s + (d.spend || 0), 0)

  return (
    <div className="flex-1 overflow-auto px-6 py-6 space-y-8">
      <PageReportHeader days={params.days || 30} onExport={() => {}} />
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-slate-600">Date range</span>
        <DateRangePicker onChange={onDateChange} initialDays={30} />
      </div>

      {/* KPI cards */}
      <div>
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Key metrics</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-4">
          {kpis.map((k) => (
            <div key={k.label} className="glass-card p-4 rounded-xl">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{k.label}</p>
              <p className="mt-1.5 text-lg font-bold text-slate-800 tabular-nums">{k.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Daily Trends */}
      <div className="glass-card p-6 rounded-xl">
        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-1">Daily Trends</h3>
        <p className="text-xs text-slate-500 mb-4">Spend, revenue and clicks over time</p>
        {ts.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={ts}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Area yAxisId="left" type="monotone" dataKey="spend" stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.2} strokeWidth={2} name="Spend" />
              <Area yAxisId="left" type="monotone" dataKey="revenue" stroke={CHART_COLORS[1]} fill={CHART_COLORS[1]} fillOpacity={0.2} strokeWidth={2} name="Revenue" />
              <Line yAxisId="right" type="monotone" dataKey="clicks" stroke={CHART_COLORS[2]} strokeWidth={2} dot={false} name="Clicks" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-slate-400 text-sm">No timeseries data available.</p>
        )}
      </div>

      {/* Campaign Performance Table */}
      <div className="glass-card overflow-hidden rounded-xl">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Campaign Performance</h3>
          <p className="text-xs text-slate-500 mt-0.5">Spend, revenue and conversions by campaign</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {['campaign_id', 'spend', 'revenue', 'roas', 'clicks', 'impressions', 'conversions', 'cpa', 'ctr'].map((col) => (
                  <th
                    key={col}
                    onClick={() => toggleSort(campaignSort, setCampaignSort)(col)}
                    className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase cursor-pointer hover:bg-slate-100 whitespace-nowrap"
                  >
                    {col === 'campaign_id' ? 'Campaign' : col === 'ctr' ? 'CTR %' : col === 'cpa' ? 'CPA' : col.toUpperCase()}
                    {campaignSort.col === col && (campaignSort.dir === 'asc' ? ' ↑' : ' ↓')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {sortedCampaigns.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm text-slate-800 font-medium">{row.campaign_id}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtCurrency(row.spend)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtCurrency(row.revenue)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.roas)}x</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.clicks)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.impressions)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.conversions)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtCurrency(row.cpa)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtPct(row.ctr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sortedCampaigns.length === 0 && (
          <p className="p-4 text-center text-slate-500 text-sm">No campaign data for this period.</p>
        )}
      </div>

      {/* Device Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-6 rounded-xl">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-1">Spend & Conversions by Device</h3>
          <p className="text-xs text-slate-500 mb-4">Breakdown by device type</p>
          {devices.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={devices}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="device" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="spend" fill={CHART_COLORS[0]} name="Spend" radius={[4, 4, 0, 0]} />
                <Bar dataKey="conversions" fill={CHART_COLORS[1]} name="Conversions" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-400 text-sm">No device data.</p>
          )}
        </div>
        <div className="glass-card p-6 rounded-xl">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-1">Spend Share by Device</h3>
          <p className="text-xs text-slate-500 mb-4">Percentage of total spend</p>
          {devices.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={devices}
                  dataKey="spend"
                  nameKey="device"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={({ device, spend }) => `${device}: ${totalDeviceSpend ? ((spend / totalDeviceSpend) * 100).toFixed(0) + '%' : ''}`}
                >
                  {devices.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-400 text-sm">No device data.</p>
          )}
        </div>
      </div>

      {/* Ad Group Table */}
      <div className="glass-card overflow-hidden rounded-xl">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Top Ad Groups</h3>
          <p className="text-xs text-slate-500 mt-0.5">Performance by ad group</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {['campaign_id', 'ad_group_id', 'spend', 'revenue', 'roas', 'clicks', 'impressions', 'conversions', 'ctr'].map((col) => (
                  <th
                    key={col}
                    onClick={() => toggleSort(adGroupSort, setAdGroupSort)(col)}
                    className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase cursor-pointer hover:bg-slate-100 whitespace-nowrap"
                  >
                    {col === 'campaign_id' ? 'Campaign' : col === 'ad_group_id' ? 'Ad Group' : col === 'ctr' ? 'CTR %' : col.toUpperCase()}
                    {adGroupSort.col === col && (adGroupSort.dir === 'asc' ? ' ↑' : ' ↓')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {sortedAdGroups.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm text-slate-800">{row.campaign_id}</td>
                  <td className="px-4 py-3 text-sm text-slate-800 font-medium">{row.ad_group_id}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtCurrency(row.spend)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtCurrency(row.revenue)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.roas)}x</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.clicks)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.impressions)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.conversions)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtPct(row.ctr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sortedAdGroups.length === 0 && (
          <p className="p-4 text-center text-slate-500 text-sm">No ad group data for this period.</p>
        )}
      </div>
    </div>
  )
}
