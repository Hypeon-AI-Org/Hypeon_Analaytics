import React, { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid, AreaChart, Area,
} from 'recharts'
import { fetchGoogleAnalyticsAnalysis } from '../api'
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

export default function GoogleAnalyticsPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [params, setParams] = useState({ days: 30 })

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchGoogleAnalyticsAnalysis(params)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [params])

  useEffect(() => { load() }, [load])

  const onDateChange = (range) => setParams(range)

  if (loading && !data) {
    return (
      <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-24" />)}
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
  const devices = data?.by_device || []
  const funnel = data?.conversion_funnel || []

  const kpis = [
    { label: 'Sessions', value: fmt(o.sessions) },
    { label: 'Conversions', value: fmt(o.conversions) },
    { label: 'Revenue', value: fmtCurrency(o.revenue) },
    { label: 'Conversion Rate', value: fmtPct(o.conversion_rate) },
    { label: 'Revenue / Session', value: fmtCurrency(o.revenue_per_session) },
  ]

  const totalDeviceSessions = devices.reduce((s, d) => s + (d.sessions || 0), 0)
  const funnelMax = funnel.length > 0 ? Math.max(...funnel.map((f) => Number(f.value) || 0), 1) : 1

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
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
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
        <p className="text-xs text-slate-500 mb-4">Sessions, revenue and conversions over time</p>
        {ts.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={ts}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Area yAxisId="left" type="monotone" dataKey="sessions" stroke={CHART_COLORS[0]} fill={CHART_COLORS[0]} fillOpacity={0.2} strokeWidth={2} name="Sessions" />
              <Area yAxisId="right" type="monotone" dataKey="revenue" stroke={CHART_COLORS[1]} fill={CHART_COLORS[1]} fillOpacity={0.2} strokeWidth={2} name="Revenue" />
              <Line yAxisId="left" type="monotone" dataKey="conversions" stroke={CHART_COLORS[2]} strokeWidth={2} dot={false} name="Conversions" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-slate-400 text-sm">No timeseries data available.</p>
        )}
      </div>

      {/* Device Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-6 rounded-xl">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-1">Sessions & Conversions by Device</h3>
          <p className="text-xs text-slate-500 mb-4">Breakdown by device type</p>
          {devices.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={devices}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="device" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="sessions" fill={CHART_COLORS[0]} name="Sessions" radius={[4, 4, 0, 0]} />
                <Bar dataKey="conversions" fill={CHART_COLORS[1]} name="Conversions" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-400 text-sm">No device data.</p>
          )}
        </div>
        <div className="glass-card p-6 rounded-xl">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-1">Session Share by Device</h3>
          <p className="text-xs text-slate-500 mb-4">Percentage of total sessions</p>
          {devices.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={devices}
                  dataKey="sessions"
                  nameKey="device"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={({ device, sessions }) => `${device}: ${totalDeviceSessions ? ((sessions / totalDeviceSessions) * 100).toFixed(0) + '%' : ''}`}
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

      {/* Device Detail Table */}
      <div className="glass-card overflow-hidden rounded-xl">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50/50">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Device Performance</h3>
          <p className="text-xs text-slate-500 mt-0.5">Sessions, conversions and revenue by device</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {['Device', 'Sessions', 'Conversions', 'Revenue', 'Conv. Rate'].map((col) => (
                  <th key={col} className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {devices.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm text-slate-800 font-medium">{row.device}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.sessions)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmt(row.conversions)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtCurrency(row.revenue)}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{fmtPct(row.conversion_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Conversion Funnel */}
      <div className="glass-card p-6 rounded-xl">
        <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider mb-1">Conversion Funnel</h3>
        <p className="text-xs text-slate-500 mb-4">Funnel stages and drop rates</p>
        {funnel.length > 0 ? (
          <div className="space-y-3 max-w-2xl">
            {funnel.map((stage, i) => (
              <div key={i}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-slate-700">{stage.stage}</span>
                  <span className="text-slate-500">
                    {stage.stage === 'Revenue' ? fmtCurrency(stage.value) : fmt(stage.value)}
                    {stage.drop_pct != null && (
                      <span className="text-blue-600 ml-2">({Number(stage.drop_pct).toFixed(1)}% drop)</span>
                    )}
                  </span>
                </div>
                <div className="h-8 bg-slate-100 rounded-lg overflow-hidden">
                  <div
                    className="h-full rounded-lg transition-all duration-300"
                    style={{
                      width: `${(Number(stage.value) / funnelMax) * 100}%`,
                      backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-400 text-sm">No funnel data available.</p>
        )}
      </div>
    </div>
  )
}
