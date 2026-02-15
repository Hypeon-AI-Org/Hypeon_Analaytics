import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts'
import { api } from '../api'

const defaultEnd = new Date()
// Start from 2025-01-01 so sample data (Jan 2025) and all pipeline runs are included
const defaultStart = new Date('2025-01-01')

function formatDate(s: string) {
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' })
}

export default function Dashboard() {
  const [startDate, setStartDate] = useState(defaultStart.toISOString().slice(0, 10))
  const [endDate, setEndDate] = useState(defaultEnd.toISOString().slice(0, 10))
  const [metrics, setMetrics] = useState<Awaited<ReturnType<typeof api.metrics>> | null>(null)
  const [decisions, setDecisions] = useState<Awaited<ReturnType<typeof api.decisions>> | null>(null)
  const [mmm, setMmm] = useState<Awaited<ReturnType<typeof api.mmmStatus>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<string | null>(null)

  const fetchData = () => {
    setError(null)
    Promise.all([
      api.metrics({ start_date: startDate, end_date: endDate }),
      api.decisions(),
      api.mmmStatus(),
    ])
      .then(([m, d, mm]) => {
        setMetrics(m)
        setDecisions(d)
        setMmm(mm)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setLoading(true)
    fetchData()
  }, [startDate, endDate])

  const handleRunPipeline = () => {
    setRunStatus('Running pipeline…')
    api.runPipeline()
      .then((r) => {
        setRunStatus('Pipeline started. Refreshing in 20s…')
        setTimeout(() => {
          setRunStatus('Refreshing…')
          fetchData()
          setRunStatus(`Done: ${r.run_id}`)
          setTimeout(() => setRunStatus(null), 4000)
        }, 20000)
      })
      .catch((e) => {
        setRunStatus(`Failed: ${e.message}`)
        setTimeout(() => setRunStatus(null), 8000)
      })
  }

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[40vh]">
        <p className="text-surface-500">Loading dashboard…</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4">
          Could not load data. Is the API running at {import.meta.env.VITE_API_URL || '/api'}? {error}
        </div>
      </div>
    )
  }

  const allMetrics = metrics?.metrics || []
  const byDate = allMetrics.reduce<Record<string, { date: string; meta: number; google: number; revenue: number }>>((acc, r) => {
    if (!acc[r.date]) acc[r.date] = { date: r.date, meta: 0, google: 0, revenue: 0 }
    if (r.channel === 'meta') acc[r.date].meta += r.spend
    if (r.channel === 'google') acc[r.date].google += r.spend
    acc[r.date].revenue += r.attributed_revenue
    return acc
  }, {})
  const sortedByDate = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  const chartData = sortedByDate.slice(-21) // last 21 days for chart only

  // KPIs from full range, not just chart
  const totalSpend = allMetrics.reduce((s, r) => s + r.spend, 0)
  const totalRev = allMetrics.reduce((s, r) => s + r.attributed_revenue, 0)
  const roas = totalSpend ? (totalRev / totalSpend).toFixed(2) : '—'

  const rangeLabel = metrics?.start_date && metrics?.end_date
    ? `${metrics.start_date} to ${metrics.end_date}`
    : 'Summary'

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-2xl font-semibold text-surface-900 mb-1">Overview</h1>
          <p className="text-surface-500 text-sm">{rangeLabel}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-surface-500">From</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded-lg border border-surface-200 px-2 py-1.5 text-sm"
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-surface-500">To</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="rounded-lg border border-surface-200 px-2 py-1.5 text-sm"
            />
          </label>
          <button
            type="button"
            onClick={handleRunPipeline}
            disabled={!!runStatus && runStatus.startsWith('Running')}
            className="rounded-lg bg-surface-800 text-white px-4 py-2 text-sm font-medium hover:bg-surface-700 disabled:opacity-70"
          >
            {runStatus?.startsWith('Running') ? 'Running…' : 'Run pipeline'}
          </button>
          {runStatus && !runStatus.startsWith('Running') && (
            <span className="text-sm text-surface-600">{runStatus}</span>
          )}
        </div>
      </div>

      {allMetrics.length === 0 && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-800">
          No metrics in this date range. Click <strong>Run pipeline</strong> above to ingest data and compute metrics (uses sample data in <code>data/raw/</code>). Set dates that include your data range (e.g. 2025-01-01 to 2025-03-31 for the 90-day sample).
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide">Total spend</p>
          <p className="text-2xl font-display font-semibold text-surface-900 mt-1">
            ${totalSpend.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide">Attributed revenue</p>
          <p className="text-2xl font-display font-semibold text-surface-900 mt-1">
            ${totalRev.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide">ROAS</p>
          <p className="text-2xl font-display font-semibold text-surface-900 mt-1">{roas}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm mb-8">
        <h2 className="font-display font-semibold text-surface-900 mb-4">Spend & revenue by day</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tickFormatter={(v) => formatDate(v)} fontSize={11} />
              <YAxis fontSize={11} tickFormatter={(v) => `$${v}`} />
              <Tooltip formatter={(v: number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} labelFormatter={formatDate} />
              <Legend />
              <Bar dataKey="meta" name="Meta spend" fill="#0ea5e9" radius={[2, 2, 0, 0]} />
              <Bar dataKey="google" name="Google spend" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
              <Bar dataKey="revenue" name="Revenue" fill="#10b981" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display font-semibold text-surface-900">Decisions</h2>
            <Link to="/decisions" className="text-sm text-brand-600 hover:underline">View all</Link>
          </div>
          <p className="text-surface-600 text-sm">
            {decisions?.total ?? 0} total ({decisions?.decisions.filter((d) => d.status === 'pending').length ?? 0} pending)
          </p>
          {mmm && (
            <p className="text-xs text-surface-500 mt-2">
              MMM: {mmm.status === 'completed' ? mmm.last_run_id : mmm.status}
            </p>
          )}
        </div>
        <div className="bg-brand-50 rounded-xl border border-brand-100 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display font-semibold text-brand-900">Ask in plain language</h2>
            <Link to="/copilot" className="text-sm text-brand-600 hover:underline font-medium">Open Copilot</Link>
          </div>
          <p className="text-brand-800 text-sm">
            Get answers like &ldquo;How are we doing?&rdquo; or &ldquo;Where should we spend?&rdquo; without opening spreadsheets.
          </p>
        </div>
      </div>
    </div>
  )
}
