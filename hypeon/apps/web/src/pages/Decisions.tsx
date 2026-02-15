import { useEffect, useState } from 'react'
import { api, DecisionRow } from '../api'

function formatDate(s: string) {
  return new Date(s).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

export default function Decisions() {
  const [decisions, setDecisions] = useState<DecisionRow[]>([])
  const [total, setTotal] = useState(0)
  const [status, setStatus] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    api
      .decisions(status || undefined)
      .then((r) => {
        setDecisions(r.decisions)
        setTotal(r.total)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [status])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="font-display text-2xl font-semibold text-surface-900 mb-1">Decisions</h1>
      <p className="text-surface-500 text-sm mb-6">Recommendations from the rules engine (MMM + thresholds)</p>

      <div className="flex flex-wrap gap-4 mb-6">
        <label className="flex items-center gap-2">
          <span className="text-sm text-surface-600">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-lg border border-surface-200 px-3 py-1.5 text-sm"
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-surface-500">Loading…</p>
      ) : (
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-sm">
          <div className="p-4 border-b border-surface-200 flex items-center justify-between">
            <h2 className="font-display font-semibold text-surface-900">{total} decisions</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200 bg-surface-50">
                  <th className="text-left py-2 px-4 font-medium text-surface-600">Created</th>
                  <th className="text-left py-2 px-4 font-medium text-surface-600">Entity</th>
                  <th className="text-left py-2 px-4 font-medium text-surface-600">Type</th>
                  <th className="text-left py-2 px-4 font-medium text-surface-600">Reason</th>
                  <th className="text-left py-2 px-4 font-medium text-surface-600">Explanation</th>
                  <th className="text-right py-2 px-4 font-medium text-surface-600">Confidence</th>
                  <th className="text-left py-2 px-4 font-medium text-surface-600">Status</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d) => (
                  <tr key={d.decision_id} className="border-b border-surface-100 hover:bg-surface-50">
                    <td className="py-2 px-4 whitespace-nowrap">{formatDate(d.created_at)}</td>
                    <td className="py-2 px-4">{d.entity_type} / {d.entity_id}</td>
                    <td className="py-2 px-4">{d.decision_type}</td>
                    <td className="py-2 px-4">{d.reason_code}</td>
                    <td className="py-2 px-4 max-w-xs truncate" title={d.explanation_text ?? ''}>{d.explanation_text ?? '—'}</td>
                    <td className="py-2 px-4 text-right">{(d.confidence_score * 100).toFixed(0)}%</td>
                    <td className="py-2 px-4">
                      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                        d.status === 'pending' ? 'bg-amber-100 text-amber-800' :
                        d.status === 'approved' ? 'bg-green-100 text-green-800' : 'bg-surface-100 text-surface-600'
                      }`}>
                        {d.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {decisions.length === 0 && (
            <p className="p-6 text-surface-500 text-center">No decisions yet. Run the pipeline to generate recommendations.</p>
          )}
        </div>
      )}
    </div>
  )
}
