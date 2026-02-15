import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { api } from '../api'

const defaultEnd = new Date()
const defaultStart = new Date(defaultEnd)
defaultStart.setDate(defaultStart.getDate() - 30)

export default function Report() {
  const [report, setReport] = useState<Awaited<ReturnType<typeof api.reportAttributionMmm>> | null>(null)
  const [start, setStart] = useState(defaultStart.toISOString().slice(0, 10))
  const [end, setEnd] = useState(defaultEnd.toISOString().slice(0, 10))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    api
      .reportAttributionMmm({ start_date: start, end_date: end })
      .then(setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [start, end])

  const chartData = report?.channels.map((ch) => ({
    channel: ch,
    attribution: (report.attribution_share[ch] ?? 0) * 100,
    mmm: (report.mmm_share[ch] ?? 0) * 100,
  })) ?? []

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="font-display text-2xl font-semibold text-surface-900 mb-1">Attribution vs MMM</h1>
      <p className="text-surface-500 text-sm mb-6">Compare MTA attribution share vs MMM contribution share; instability when they disagree.</p>

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
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-surface-500">Loading…</p>
      ) : report ? (
        <>
          <div className="flex flex-wrap gap-4 mb-6">
            <div className="px-4 py-2 rounded-lg bg-surface-100 text-surface-800 text-sm">
              Disagreement score: <strong>{report.disagreement_score.toFixed(3)}</strong>
            </div>
            {report.instability_flagged && (
              <div className="px-4 py-2 rounded-lg bg-amber-100 text-amber-800 text-sm font-medium">
                Instability flagged
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm mb-6">
            <h2 className="font-display font-semibold text-surface-900 mb-4">Share by channel (%)</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <XAxis dataKey="channel" fontSize={12} />
                  <YAxis fontSize={11} tickFormatter={(v) => `${v}%`} />
                  <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, '']} />
                  <Legend />
                  <Bar dataKey="attribution" name="Attribution share" fill="#0ea5e9" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="mmm" name="MMM share" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200 bg-surface-50">
                  <th className="text-left py-2 px-4 font-medium text-surface-600">Channel</th>
                  <th className="text-right py-2 px-4 font-medium text-surface-600">Attribution %</th>
                  <th className="text-right py-2 px-4 font-medium text-surface-600">MMM %</th>
                </tr>
              </thead>
              <tbody>
                {report.channels.map((ch) => (
                  <tr key={ch} className="border-b border-surface-100">
                    <td className="py-2 px-4 capitalize">{ch}</td>
                    <td className="py-2 px-4 text-right">{((report.attribution_share[ch] ?? 0) * 100).toFixed(1)}%</td>
                    <td className="py-2 px-4 text-right">{((report.mmm_share[ch] ?? 0) * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}
