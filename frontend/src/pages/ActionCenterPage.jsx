import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchActions, applyRecommendation } from '../api'
import ErrorBanner from '../components/ErrorBanner'

const ACTION_LABEL = {
  increase_budget: 'Scale Campaign',
  reduce_budget: 'Reduce Spend',
  investigate: 'Conversion Issue',
}

export default function ActionCenterPage({ onExplain }) {
  const navigate = useNavigate()
  const [data, setData] = useState({ items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [applying, setApplying] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchActions()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
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
    return <ErrorBanner message={error} onRetry={load} />
  }

  const items = data.items || []

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">Top actions from insights. Approve applies the recommendation; Ignore dismisses.</p>
      {loading && items.length === 0 ? (
        <div className="animate-pulse rounded-xl bg-pink-100/50 h-48" />
      ) : items.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <p className="text-slate-600 font-medium">No recommended actions right now</p>
          <p className="mt-1 text-sm text-slate-500">When we have new insights, they will appear here. You can also check Insights for the full list.</p>
          <button
            type="button"
            onClick={() => navigate('/insights')}
            className="mt-4 rounded-xl border border-brand-200 bg-white px-4 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50 transition-colors"
          >
            View Insights
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {items.map((action) => (
            <div
              key={action.insight_id}
              className="glass-card p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
            >
              <div className="flex-1">
                <span className="inline-flex rounded-lg px-2 py-0.5 text-xs font-medium bg-brand-100 text-brand-800">
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
                  className="px-3 py-2 text-sm font-medium rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                >
                  {applying === action.insight_id ? 'Applying…' : 'Approve'}
                </button>
                <button
                  type="button"
                  disabled={applying === action.insight_id}
                  onClick={() => handleIgnore(action.insight_id)}
                  className="px-3 py-2 text-sm font-medium rounded-xl border border-pink-200 text-slate-700 hover:bg-pink-50 disabled:opacity-50 transition-colors"
                >
                  Ignore
                </button>
                {typeof onExplain === 'function' && (
                  <button
                    type="button"
                    onClick={() => onExplain(action.insight_id)}
                    className="px-3 py-2 text-sm font-medium rounded-xl border border-brand-200 text-brand-700 hover:bg-brand-50 transition-colors"
                  >
                    Explain
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
