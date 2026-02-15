import { useEffect, useState } from 'react'
import { api } from '../api'

export default function MMMOptimizer() {
  const [mmmStatus, setMmmStatus] = useState<Awaited<ReturnType<typeof api.mmmStatus>> | null>(null)
  const [mmmResults, setMmmResults] = useState<Awaited<ReturnType<typeof api.mmmResults>> | null>(null)
  const [totalBudget, setTotalBudget] = useState('1000')
  const [budgetResult, setBudgetResult] = useState<Awaited<ReturnType<typeof api.optimizerBudget>> | null>(null)
  const [simMeta, setSimMeta] = useState('0.2')
  const [simGoogle, setSimGoogle] = useState('-0.1')
  const [simResult, setSimResult] = useState<Awaited<ReturnType<typeof api.simulate>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.mmmStatus(), api.mmmResults()])
      .then(([status, results]) => {
        setMmmStatus(status)
        setMmmResults(results)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const fetchBudget = () => {
    const n = parseFloat(totalBudget)
    if (Number.isNaN(n) || n < 0) return
    setError(null)
    api.optimizerBudget(n).then(setBudgetResult).catch((e) => setError(e.message))
  }

  const runSimulate = () => {
    const meta = parseFloat(simMeta)
    const google = parseFloat(simGoogle)
    setError(null)
    api
      .simulate({
        meta_spend_change: Number.isNaN(meta) ? undefined : meta,
        google_spend_change: Number.isNaN(google) ? undefined : google,
      })
      .then(setSimResult)
      .catch((e) => setError(e.message))
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="font-display text-2xl font-semibold text-surface-900 mb-1">Optimizer & simulator</h1>
      <p className="text-surface-500 text-sm mb-6">Budget allocation and what-if spend changes (based on MMM)</p>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-surface-500">Loading…</p>
      ) : (
        <div className="space-y-8">
          <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
            <h2 className="font-display font-semibold text-surface-900 mb-2">MMM status</h2>
            <p className="text-sm text-surface-600">
              {mmmStatus?.status === 'completed'
                ? `Last run: ${mmmStatus.last_run_id} at ${mmmStatus.last_run_at ? new Date(mmmStatus.last_run_at).toLocaleString() : '—'}`
                : 'No MMM runs yet. Trigger a pipeline run from Overview or API.'}
            </p>
            {mmmResults && mmmResults.results.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-4">
                {mmmResults.results.map((r) => (
                  <span key={r.channel} className="text-sm">
                    <span className="font-medium text-surface-700">{r.channel}</span>: coef {r.coefficient.toFixed(4)}
                    {r.goodness_of_fit_r2 != null && ` · R² ${r.goodness_of_fit_r2.toFixed(3)}`}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
            <h2 className="font-display font-semibold text-surface-900 mb-3">Budget optimizer</h2>
            <p className="text-sm text-surface-600 mb-4">Get recommended allocation across channels for a total budget.</p>
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-surface-500">Total budget ($)</span>
                <input
                  type="number"
                  value={totalBudget}
                  onChange={(e) => setTotalBudget(e.target.value)}
                  className="rounded-lg border border-surface-200 px-3 py-2 w-32"
                />
              </label>
              <button
                type="button"
                onClick={fetchBudget}
                className="rounded-lg bg-brand-600 text-white px-4 py-2 text-sm font-medium hover:bg-brand-700"
              >
                Get recommendation
              </button>
            </div>
            {budgetResult && (
              <div className="mt-4 p-4 bg-surface-50 rounded-lg text-sm">
                <p className="font-medium text-surface-800 mb-2">Recommended allocation</p>
                <ul className="space-y-1">
                  {Object.entries(budgetResult.recommended_allocation).map(([ch, v]) => (
                    <li key={ch}>{ch}: ${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}</li>
                  ))}
                </ul>
                <p className="mt-2 text-surface-600">
                  Predicted revenue at this allocation: ${budgetResult.predicted_revenue_at_recommended.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </p>
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
            <h2 className="font-display font-semibold text-surface-900 mb-3">Simulator</h2>
            <p className="text-sm text-surface-600 mb-4">Apply % change to Meta and Google spend; see projected revenue delta.</p>
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-surface-500">Meta spend change (e.g. 0.2 = +20%)</span>
                <input
                  type="text"
                  value={simMeta}
                  onChange={(e) => setSimMeta(e.target.value)}
                  className="rounded-lg border border-surface-200 px-3 py-2 w-40"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-surface-500">Google spend change (e.g. -0.1 = -10%)</span>
                <input
                  type="text"
                  value={simGoogle}
                  onChange={(e) => setSimGoogle(e.target.value)}
                  className="rounded-lg border border-surface-200 px-3 py-2 w-40"
                />
              </label>
              <button
                type="button"
                onClick={runSimulate}
                className="rounded-lg bg-brand-600 text-white px-4 py-2 text-sm font-medium hover:bg-brand-700"
              >
                Simulate
              </button>
            </div>
            {simResult && (
              <div className="mt-4 p-4 bg-surface-50 rounded-lg text-sm">
                <p className="font-medium text-surface-800">Projected revenue delta: ${simResult.projected_revenue_delta.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
                <p className="text-surface-600 mt-1">Current spend: {JSON.stringify(simResult.current_spend)} → New: {JSON.stringify(simResult.new_spend)}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
