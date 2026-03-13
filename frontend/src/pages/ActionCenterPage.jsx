import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { fetchActions, applyRecommendation } from '../api'
import ErrorBanner from '../components/ErrorBanner'
import PageReportHeader from '../components/PageReportHeader'

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
    return (
      <div className="flex-1 overflow-auto px-6 py-6">
        <ErrorBanner message={error} onRetry={load} />
      </div>
    )
  }

  const items = data.items || []

  return (
    <div className="flex-1 overflow-auto px-6 py-6 space-y-6 bg-slate-50/70">
      <PageReportHeader days={30} onExport={() => {}} />
      <p className="text-sm text-slate-600">Recommended actions from your insights. Approve to apply or ignore to dismiss.</p>
      {loading && items.length === 0 ? (
        <div className="animate-pulse rounded-xl bg-slate-200 h-48" />
      ) : items.length === 0 ? (
        <div className="glass-card p-10 text-center max-w-lg mx-auto">
          <Zap className="mx-auto text-slate-300" size={40} strokeWidth={1.5} />
          <p className="mt-3 text-slate-700 font-medium">No recommended actions right now</p>
          <p className="mt-1 text-sm text-slate-500">When we have new insights, they’ll appear here. Check Insights or ask Copilot for analysis.</p>
          <div className="mt-6 flex flex-wrap gap-3 justify-center">
            <button
              type="button"
              onClick={() => navigate('/insights')}
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              View Insights
            </button>
            <button
              type="button"
              onClick={() => navigate('/copilot')}
              className="rounded-lg bg-slate-800 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 transition-colors"
            >
              Open Copilot
            </button>
          </div>
        </div>
      ) : (
        <div className="grid gap-4">
          {items.map((action) => (
            <div
              key={action.insight_id}
              className="glass-card p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
            >
              <div className="flex-1">
                <span className="inline-flex rounded-lg px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-800">
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
                  className="px-3 py-2 text-sm font-medium rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
                >
                  Ignore
                </button>
                {typeof onExplain === 'function' && (
                  <button
                    type="button"
                    onClick={() => onExplain(action.insight_id)}
                    className="px-3 py-2 text-sm font-medium rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
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
