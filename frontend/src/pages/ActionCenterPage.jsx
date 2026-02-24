import React, { useState, useEffect } from 'react'
import { fetchActions } from '../api'
import { applyRecommendation } from '../api'

const ACTION_LABEL = {
  increase_budget: 'Scale Campaign',
  reduce_budget: 'Reduce Spend',
  investigate: 'Conversion Issue',
}

export default function ActionCenterPage({ onExplain }) {
  const [data, setData] = useState({ items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [applying, setApplying] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchActions()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const handleApprove = (insightId) => {
    setApplying(insightId)
    applyRecommendation(insightId, 'applied')
      .then(() => {
        setData((d) => ({ ...d, items: (d.items || []).filter((i) => i.insight_id !== insightId) }))
      })
      .finally(() => setApplying(null))
  }

  const handleIgnore = (insightId) => {
    setApplying(insightId)
    applyRecommendation(insightId, 'rejected')
      .then(() => {
        setData((d) => ({ ...d, items: (d.items || []).filter((i) => i.insight_id !== insightId) }))
      })
      .finally(() => setApplying(null))
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3" role="alert">
        {error}
      </div>
    )
  }

  const items = data.items || []

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">Top actions from insights. Approve applies the recommendation; Ignore dismisses.</p>
      {loading && items.length === 0 ? (
        <div className="animate-pulse rounded-lg bg-slate-100 h-48" />
      ) : (
        <div className="grid gap-4">
          {items.map((action) => (
            <div
              key={action.insight_id}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
            >
              <div className="flex-1">
                <span className="inline-flex rounded px-2 py-0.5 text-xs font-medium bg-indigo-100 text-indigo-800">
                  {ACTION_LABEL[action.action] || action.action}
                </span>
                <p className="mt-2 text-sm text-slate-700">{action.summary}</p>
                {action.confidence != null && (
                  <p className="text-xs text-slate-500 mt-1">Confidence: {Number(action.confidence * 100).toFixed(0)}%</p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={applying === action.insight_id}
                  onClick={() => handleApprove(action.insight_id)}
                  className="px-3 py-1.5 text-sm font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  type="button"
                  disabled={applying === action.insight_id}
                  onClick={() => handleIgnore(action.insight_id)}
                  className="px-3 py-1.5 text-sm font-medium rounded border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Ignore
                </button>
                {typeof onExplain === 'function' && (
                  <button
                    type="button"
                    onClick={() => onExplain(action.insight_id)}
                    className="px-3 py-1.5 text-sm font-medium rounded border border-indigo-300 text-indigo-700 hover:bg-indigo-50"
                  >
                    Explain
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {!loading && items.length === 0 && (
        <p className="text-slate-500 text-center py-8">No actions right now. Cache may need a refresh.</p>
      )}
    </div>
  )
}
