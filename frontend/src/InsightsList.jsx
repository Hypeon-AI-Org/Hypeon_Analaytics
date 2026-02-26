import React, { useState, useEffect } from 'react'
import { fetchInsights, applyRecommendation, simulateBudgetShift } from './api'
import ErrorBanner from './components/ErrorBanner'
import PageReportHeader from './components/PageReportHeader'

export default function InsightsList() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [clientId, setClientId] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [simulateModal, setSimulateModal] = useState(null)
  const [simulateResult, setSimulateResult] = useState(null)
  const [simulateLoading, setSimulateLoading] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    const params = { limit: 50 }
    if (clientId) params.client_id = parseInt(clientId, 10)
    if (statusFilter) params.status = statusFilter
    fetchInsights(params)
      .then((data) => {
        setItems(data.items || [])
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }

  useEffect(() => {
    load()
  }, [clientId, statusFilter])

  const handleApprove = (insightId) => {
    applyRecommendation(insightId, 'applied')
      .then(() => load())
      .catch((err) => setError(err.message))
  }

  const handleReject = (insightId) => {
    applyRecommendation(insightId, 'rejected')
      .then(() => load())
      .catch((err) => setError(err.message))
  }

  const openSimulate = (insight) => {
    setSimulateModal(insight)
    setSimulateResult(null)
  }

  const runSimulate = (fromCampaign, toCampaign, amount) => {
    if (!simulateModal) return
    setSimulateLoading(true)
    simulateBudgetShift({
      client_id: simulateModal.client_id,
      date: simulateModal.created_at?.slice(0, 10) || new Date().toISOString().slice(0, 10),
      from_campaign: fromCampaign,
      to_campaign: toCampaign,
      amount: parseFloat(amount) || 0,
    })
      .then((data) => {
        setSimulateResult(data)
        setSimulateLoading(false)
      })
      .catch((err) => {
        setSimulateResult({ error: err.message })
        setSimulateLoading(false)
      })
  }

  const closeSimulate = () => {
    setSimulateModal(null)
    setSimulateResult(null)
  }

  return (
    <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
      <PageReportHeader days={30} onExport={() => {}} />
      <div className="flex flex-wrap gap-4 items-center">
        <label className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Client ID</span>
          <input
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Optional"
            className="rounded-xl border border-slate-200 px-2 py-1.5 text-sm w-24 focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
            aria-label="Filter by client ID"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Status</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-slate-200 px-2 py-1.5 text-sm focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
            aria-label="Filter by status"
          >
            <option value="">All</option>
            <option value="new">New</option>
            <option value="reviewed">Reviewed</option>
            <option value="applied">Applied</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
        <button
          type="button"
          onClick={() => load()}
          className="rounded-xl bg-brand-600 text-white px-3 py-2 text-sm font-medium hover:bg-brand-700 transition-colors"
        >
          Refresh
        </button>
      </div>

      {error && <ErrorBanner message={error} onRetry={load} />}

      {loading && items.length === 0 && (
        <div className="animate-pulse rounded-xl bg-slate-100 h-48" />
      )}

      {!loading && items.length === 0 && (
        <div className="glass-card p-8 text-center">
          <p className="text-slate-600 font-medium">No insights found</p>
          <p className="mt-1 text-sm text-slate-500">Try changing filters or check back later.</p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="glass-card overflow-hidden">
          <ul className="divide-y divide-slate-200">
            {items.map((insight) => (
              <li key={insight.insight_id} className="p-4 hover:bg-slate-50 transition-colors">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-slate-800">{insight.summary || '—'}</p>
                    <div className="flex flex-wrap gap-2 mt-1">
                      <span
                        className="inline-flex items-center rounded-lg bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-800"
                        aria-label={`Confidence ${insight.confidence}`}
                      >
                        {(insight.confidence != null ? Number(insight.confidence) * 100 : 0).toFixed(0)}% confidence
                      </span>
                      <span className="text-xs text-slate-500">
                        {insight.created_at ? new Date(insight.created_at).toLocaleString() : '—'}
                      </span>
                    </div>
                    {expandedId === insight.insight_id && (
                      <div className="mt-2 text-sm text-slate-600 rounded-xl bg-slate-50 p-3 border border-slate-200">
                        <p><strong>Explanation:</strong> {insight.explanation || '—'}</p>
                        <p><strong>Recommendation:</strong> {insight.recommendation || '—'}</p>
                        <p><strong>Provenance:</strong> {(insight.detected_by || []).join(', ') || '—'}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => openSimulate(insight)}
                      className="rounded-xl bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 transition-colors"
                      aria-label="Simulate budget shift"
                    >
                      Simulate
                    </button>
                    <button
                      type="button"
                      onClick={() => handleApprove(insight.insight_id)}
                      className="rounded-xl bg-emerald-600 text-white px-3 py-2 text-sm font-medium hover:bg-emerald-700 transition-colors"
                      aria-label="Approve"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReject(insight.insight_id)}
                      className="rounded-xl bg-red-600 text-white px-3 py-2 text-sm font-medium hover:bg-red-700 transition-colors"
                      aria-label="Reject"
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      onClick={() => setExpandedId(expandedId === insight.insight_id ? null : insight.insight_id)}
                      className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                      aria-expanded={expandedId === insight.insight_id}
                    >
                      {expandedId === insight.insight_id ? 'Collapse' : 'Details'}
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {simulateModal && (
        <SimulateModal
          insight={simulateModal}
          result={simulateResult}
          loading={simulateLoading}
          onRun={runSimulate}
          onClose={closeSimulate}
        />
      )}
    </div>
  )
}

function SimulateModal({ insight, result, loading, onRun, onClose }) {
  const [fromCampaign, setFromCampaign] = useState(insight.entity_id?.split('_')[0] || '')
  const [toCampaign, setToCampaign] = useState('')
  const [amount, setAmount] = useState('100')

  const handleSubmit = (e) => {
    e.preventDefault()
    onRun(fromCampaign, toCampaign, amount)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true" aria-labelledby="simulate-title">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full mx-4 p-6 border border-slate-200">
        <h2 id="simulate-title" className="text-lg font-semibold text-slate-800 mb-4">Simulate budget shift</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="from-campaign" className="block text-sm font-medium text-slate-700">From campaign</label>
            <input
              id="from-campaign"
              type="text"
              value={fromCampaign}
              onChange={(e) => setFromCampaign(e.target.value)}
              className="mt-1 block w-full rounded-xl border border-slate-200 px-3 py-2 focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
              required
            />
          </div>
          <div>
            <label htmlFor="to-campaign" className="block text-sm font-medium text-slate-700">To campaign</label>
            <input
              id="to-campaign"
              type="text"
              value={toCampaign}
              onChange={(e) => setToCampaign(e.target.value)}
              className="mt-1 block w-full rounded-xl border border-slate-200 px-3 py-2 focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
              required
            />
          </div>
          <div>
            <label htmlFor="amount" className="block text-sm font-medium text-slate-700">Amount</label>
            <input
              id="amount"
              type="number"
              min="0"
              step="any"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="mt-1 block w-full rounded-xl border border-slate-200 px-3 py-2 focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
              required
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="rounded-xl bg-brand-600 text-white px-4 py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors">
              {loading ? 'Running…' : 'Run simulation'}
            </button>
          </div>
        </form>
        {result && (
          <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-700">
            {result.error ? (
              <p className="text-red-600">{result.error}</p>
            ) : (
              <>
                <p><strong>Expected delta:</strong> {result.expected_delta}</p>
                <p><strong>Confidence:</strong> {result.confidence}</p>
                {result.low && <p>Low: {JSON.stringify(result.low)}</p>}
                {result.median && <p>Median: {JSON.stringify(result.median)}</p>}
                {result.high && <p>High: {JSON.stringify(result.high)}</p>}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
