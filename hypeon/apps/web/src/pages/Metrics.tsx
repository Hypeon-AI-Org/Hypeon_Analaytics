import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts'
import { api, UnifiedMetricRow } from '../api'

const defaultEnd = new Date()
const defaultStart = new Date(defaultEnd)
defaultStart.setDate(defaultStart.getDate() - 400) // include sample data (e.g. Jan 2025)

function formatDate(s: string) {
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function Metrics() {
  const [metrics, setMetrics] = useState<UnifiedMetricRow[]>([])
  const [start, setStart] = useState(defaultStart.toISOString().slice(0, 10))
  const [end, setEnd] = useState(defaultEnd.toISOString().slice(0, 10))
  const [channel, setChannel] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    api
      .metrics({ start_date: start, end_date: end, channel: channel || undefined })
      .then((r) => setMetrics(r.metrics))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [start, end, channel])

  const byDate = metrics.reduce<Record<string, Record<string, UnifiedMetricRow>>>((acc, r) => {
    if (!acc[r.date]) acc[r.date] = {}
    acc[r.date][r.channel] = r
    return acc
  }, {})
  const chartData = Object.entries(byDate)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, ch]) => ({
      date,
      metaSpend: ch.meta?.spend ?? 0,
      googleSpend: ch.google?.spend ?? 0,
      metaRevenue: ch.meta?.attributed_revenue ?? 0,
      googleRevenue: ch.google?.attributed_revenue ?? 0,
    }))

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="font-display text-2xl font-semibold text-surface-900 mb-1">Metrics</h1>
      <p className="text-surface-500 text-sm mb-6">Unified daily spend, revenue, and ROAS by channel</p>

      <div className="flex flex-wrap gap-4 mb-6">
        <label className="flex items-center gap-2">
          <span className="text-sm text-surface-600">From</span>
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="rounded-lg border border-surface-200 px-3 py-1.5 text-sm"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-surface-600">To</span>
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="rounded-lg border border-surface-200 px-3 py-1.5 text-sm"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-surface-600">Channel</span>
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            className="rounded-lg border border-surface-200 px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            <option value="meta">Meta</option>
            <option value="google">Google</option>
          </select>
        </label>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-surface-500">Loading…</p>
      ) : (
        <>
          <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm mb-6">
            <h2 className="font-display font-semibold text-surface-900 mb-4">Spend & revenue over time</h2>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tickFormatter={formatDate} fontSize={11} />
                  <YAxis fontSize={11} tickFormatter={(v) => `$${v}`} />
                  <Tooltip formatter={(v: number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} labelFormatter={formatDate} />
                  <Legend />
                  <Line type="monotone" dataKey="metaSpend" name="Meta spend" stroke="#0ea5e9" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="googleSpend" name="Google spend" stroke="#8b5cf6" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="metaRevenue" name="Meta revenue" stroke="#10b981" dot={false} strokeWidth={2} strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="googleRevenue" name="Google revenue" stroke="#f59e0b" dot={false} strokeWidth={2} strokeDasharray="4 4" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-sm">
            <h2 className="font-display font-semibold text-surface-900 p-4 pb-2">Table</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200 bg-surface-50">
                    <th className="text-left py-2 px-4 font-medium text-surface-600">Date</th>
                    <th className="text-left py-2 px-4 font-medium text-surface-600">Channel</th>
                    <th className="text-right py-2 px-4 font-medium text-surface-600">Spend</th>
                    <th className="text-right py-2 px-4 font-medium text-surface-600">Revenue</th>
                    <th className="text-right py-2 px-4 font-medium text-surface-600">ROAS</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.slice(0, 100).map((r) => (
                    <tr key={`${r.date}-${r.channel}`} className="border-b border-surface-100 hover:bg-surface-50">
                      <td className="py-2 px-4">{formatDate(r.date)}</td>
                      <td className="py-2 px-4 capitalize">{r.channel}</td>
                      <td className="py-2 px-4 text-right">${r.spend.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                      <td className="py-2 px-4 text-right">${r.attributed_revenue.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                      <td className="py-2 px-4 text-right">{r.roas != null ? r.roas.toFixed(2) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {metrics.length > 100 && (
              <p className="p-3 text-surface-500 text-sm">Showing first 100 rows</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
