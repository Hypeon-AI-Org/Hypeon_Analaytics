import React, { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid, AreaChart, Area,
} from 'recharts'
import { fetchGoogleAnalyticsAnalysis } from '../api'
import DateRangePicker from '../components/DateRangePicker'
import ErrorBanner from '../components/ErrorBanner'

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ef4444']

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
      <div className="space-y-6">
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
      <div className="space-y-4">
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
    <div className="space-y-8">
      {/* Date range */}
      <DateRangePicker onChange={onDateChange} initialDays={30} />

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {kpis.map((k) => (
          <div key={k.label} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{k.label}</p>
            <p className="mt-1 text-xl font-semibold text-slate-800">{k.value}</p>
          </div>
        ))}
      </div>

      {/* Daily Trends */}
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">Daily Trends</h3>
        {ts.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={ts}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Area yAxisId="left" type="monotone" dataKey="sessions" stroke="#6366f1" fill="#6366f1" fillOpacity={0.1} strokeWidth={2} name="Sessions" />
              <Area yAxisId="right" type="monotone" dataKey="revenue" stroke="#10b981" fill="#10b981" fillOpacity={0.1} strokeWidth={2} name="Revenue" />
              <Line yAxisId="left" type="monotone" dataKey="conversions" stroke="#f59e0b" strokeWidth={2} dot={false} name="Conversions" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-slate-400 text-sm">No timeseries data available.</p>
        )}
      </div>

      {/* Device Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Sessions & Conversions by Device</h3>
          {devices.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={devices}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="device" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="sessions" fill="#6366f1" name="Sessions" />
                <Bar dataKey="conversions" fill="#10b981" name="Conversions" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-400 text-sm">No device data.</p>
          )}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Session Share by Device</h3>
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
                  {devices.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
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
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700">Device Performance</h3>
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
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-700 mb-4">Conversion Funnel</h3>
        {funnel.length > 0 ? (
          <div className="space-y-3 max-w-2xl">
            {funnel.map((stage, i) => (
              <div key={i}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-slate-700">{stage.stage}</span>
                  <span className="text-slate-500">
                    {stage.stage === 'Revenue' ? fmtCurrency(stage.value) : fmt(stage.value)}
                    {stage.drop_pct != null && (
                      <span className="text-amber-600 ml-2">({Number(stage.drop_pct).toFixed(1)}% drop)</span>
                    )}
                  </span>
                </div>
                <div className="h-8 bg-slate-100 rounded overflow-hidden">
                  <div
                    className="h-full rounded transition-all"
                    style={{
                      width: `${(Number(stage.value) / funnelMax) * 100}%`,
                      backgroundColor: COLORS[i % COLORS.length],
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
