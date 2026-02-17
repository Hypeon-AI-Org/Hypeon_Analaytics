import { useEffect, useState } from 'react'
import { api, apiV1, type EnrichedDecision } from '../api'

function formatDate(s: string) {
  return new Date(s).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

export default function Decisions() {
  const [decisions, setDecisions] = useState<EnrichedDecision[]>([])
  const [total, setTotal] = useState(0)
  const [status, setStatus] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    apiV1
      .decisions(status || undefined)
      .then((r) => {
        setDecisions(r.decisions)
        setTotal(r.total)
      })
      .catch(() => {
        api.decisions(status || undefined).then((r) => {
          setDecisions(
            r.decisions.map((d) => ({
              decision_id: d.decision_id,
              channel: d.entity_id,
              recommended_action: d.decision_type.replace('_', ' '),
              budget_change_pct: d.projected_impact != null ? d.projected_impact * 100 : undefined,
              reasoning: {},
              risk_flags: [],
              confidence_score: d.confidence_score,
              run_id: undefined,
              created_at: d.created_at,
              decision_type: d.decision_type,
              explanation_text: d.explanation_text,
              status: d.status,
            }))
          )
          setTotal(r.total)
        })
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [status])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="font-display text-2xl font-semibold text-surface-900 mb-1">Decisions</h1>
      <p className="text-surface-500 text-sm mb-6">Recommendations with confidence and risk flags (MTA + MMM + alignment)</p>

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
        <div className="space-y-4">
          <p className="text-sm text-surface-600">{total} decisions</p>
          {decisions.map((d) => (
            <div
              key={d.decision_id}
              className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-medium text-surface-900">{d.channel}</span>
                  <span className="mx-2 text-surface-400">·</span>
                  <span className="text-surface-700">{d.recommended_action}</span>
                  {d.budget_change_pct != null && (
                    <span className="ml-2 text-sm text-surface-600">
                      {d.budget_change_pct > 0 ? '+' : ''}{d.budget_change_pct}% budget
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-20 h-2 bg-surface-100 rounded overflow-hidden" title={`${(d.confidence_score * 100).toFixed(0)}%`}>
                    <div
                      className="h-full bg-brand-500 rounded"
                      style={{ width: `${d.confidence_score * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-surface-700">{(d.confidence_score * 100).toFixed(0)}%</span>
                </div>
              </div>
              {d.risk_flags && d.risk_flags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {d.risk_flags.map((f) => (
                    <span
                      key={f}
                      className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}
              {d.explanation_text && (
                <p className="mt-2 text-sm text-surface-600">{d.explanation_text}</p>
              )}
              <button
                type="button"
                onClick={() => setExpandedId(expandedId === d.decision_id ? null : d.decision_id)}
                className="mt-2 text-sm text-brand-600 hover:underline"
              >
                {expandedId === d.decision_id ? 'Hide reasoning' : 'Show reasoning'}
              </button>
              {expandedId === d.decision_id && d.reasoning && (
                <div className="mt-2 p-3 bg-surface-50 rounded text-sm">
                  {d.reasoning.mta_support != null && <p>MTA support: {(d.reasoning.mta_support * 100).toFixed(0)}%</p>}
                  {d.reasoning.mmm_support != null && <p>MMM support: {(d.reasoning.mmm_support * 100).toFixed(0)}%</p>}
                  {d.reasoning.alignment_score != null && <p>Alignment: {(d.reasoning.alignment_score * 100).toFixed(0)}%</p>}
                </div>
              )}
              {(d.run_id || d.model_versions) && (
                <div className="mt-2 text-xs text-surface-500">
                  {d.run_id && <span>Run: {d.run_id}</span>}
                  {d.model_versions && (
                    <span className="ml-2">
                      MTA {d.model_versions.mta_version} · MMM {d.model_versions.mmm_version}
                    </span>
                  )}
                </div>
              )}
              {d.created_at && (
                <p className="mt-1 text-xs text-surface-400">{formatDate(d.created_at)}</p>
              )}
            </div>
          ))}
          {decisions.length === 0 && (
            <p className="p-6 text-surface-500 text-center">No decisions yet. Run the pipeline to generate recommendations.</p>
          )}
        </div>
      )}
    </div>
  )
}
