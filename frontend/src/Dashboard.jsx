import React, { useState, useEffect } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { fetchInsights } from './api'

const STATUS_COLORS = { new: '#6366f1', reviewed: '#8b5cf6', applied: '#22c55e', rejected: '#ef4444' }
const TYPE_COLORS = ['#0ea5e9', '#f59e0b', '#10b981', '#ec4899', '#8b5cf6']
const ADS_TYPES = new Set(['waste_zero_revenue', 'roas_decline', 'scale_opportunity'])
const GA4_TYPES = new Set(['funnel_leak'])

function aggregate(items) {
  const byStatus = {}
  const byType = {}
  items.forEach((i) => {
    const s = i.status || 'new'
    byStatus[s] = (byStatus[s] || 0) + 1
    const t = i.insight_type || 'other'
    byType[t] = (byType[t] || 0) + 1
  })
  return {
    statusData: Object.entries(byStatus).map(([name, count]) => ({ name, count })),
    typeData: Object.entries(byType).map(([name, value]) => ({ name, value })),
  }
}

function Skeleton({ className = '' }) {
  return <div className={`animate-pulse bg-slate-200 rounded ${className}`} />
}

export default function Dashboard() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tab, setTab] = useState('overview')

  useEffect(() => {
    setLoading(true)
    fetchInsights({ limit: 500 })
      .then((data) => {
        setItems(data.items || [])
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) {
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
      <div>
        <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3" role="alert">
          {error}
        </div>
      </div>
    )
  }

  const adsItems = items.filter((i) => ADS_TYPES.has(i.insight_type))
  const ga4Items = items.filter((i) => GA4_TYPES.has(i.insight_type))
  const overviewAgg = aggregate(items)
  const adsAgg = aggregate(adsItems)
  const ga4Agg = aggregate(ga4Items)

  const tabs = [
    { id: 'overview', label: 'Overview', data: overviewAgg, items, title: 'All insights' },
    { id: 'ads', label: 'Google Ads', data: adsAgg, items: adsItems, title: 'Google Ads performance' },
    { id: 'ga4', label: 'GA4', data: ga4Agg, items: ga4Items, title: 'GA4 & funnel' },
  ]
  const current = tabs.find((t) => t.id === tab) || tabs[0]
  const { statusData, typeData } = current.data
  const total = current.items.length
  const newCount = current.items.filter((i) => (i.status || 'new') === 'new').length
  const appliedCount = current.items.filter((i) => i.status === 'applied').length

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-slate-800">BI Dashboard</h2>
        <div className="flex rounded-lg border border-slate-200 bg-white p-0.5">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                tab === t.id ? 'bg-slate-800 text-white shadow' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <p className="text-sm text-slate-500">{current.title}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total insights</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{total}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">New</p>
          <p className="text-2xl font-bold text-indigo-600 mt-1">{newCount}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Applied</p>
          <p className="text-2xl font-bold text-emerald-600 mt-1">{appliedCount}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Types</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{typeData.length}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">By status</h3>
          <div className="h-64">
            {statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="name" width={70} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-400 text-sm flex items-center h-full">No data for this view</p>
            )}
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">By insight type</h3>
          <div className="h-64">
            {typeData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={typeData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {typeData.map((_, i) => (
                      <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-slate-400 text-sm flex items-center h-full">No data for this view</p>
            )}
          </div>
        </div>
      </div>

      {current.items.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Recent analysis</h3>
          <ul className="space-y-2">
            {current.items.slice(0, 5).map((i) => (
              <li key={i.insight_id} className="text-sm text-slate-600 border-b border-slate-100 pb-2 last:border-0">
                <span className="font-medium text-slate-800">{i.insight_type}</span> — { (i.summary || '').slice(0, 80)}…
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
