import React, { useState, useRef } from 'react'
import { copilotStreamV1 } from '../api'
import DynamicDashboardRenderer from './DynamicDashboardRenderer'

export default function CopilotPanel({ open, onClose, initialQuery = 'What should I do today?', explainInsightId = null }) {
  const [query, setQuery] = useState(initialQuery)
  const [phase, setPhase] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const streamRef = useRef(null)

  const send = () => {
    const q = query.trim()
    if (!q) return
    setPhase('loading')
    setResult(null)
    setError(null)
    streamRef.current = copilotStreamV1({ query: q, insight_id: explainInsightId || undefined }, (ev) => {
      if (ev.phase === 'loading') setPhase('loading')
      if (ev.phase === 'done' && ev.data) {
        setResult(ev.data)
        setPhase('done')
      }
      if (ev.phase === 'error') {
        setError(ev.error || 'Error')
        setPhase('error')
      }
    })
    streamRef.current.promise.catch((err) => {
      setError(err.message)
      setPhase('error')
    })
  }

  if (!open) return null

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white border-l border-slate-200 shadow-xl flex flex-col z-50">
      <div className="flex items-center justify-between p-4 border-b border-slate-200">
        <h2 className="text-lg font-semibold text-slate-800">Copilot</h2>
        <button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-700">
          Close
        </button>
      </div>
      <div className="p-4 border-b border-slate-100">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask anything..."
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="button"
          onClick={send}
          disabled={phase === 'loading'}
          className="mt-2 w-full py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {phase === 'loading' ? '…' : 'Send'}
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {phase === 'loading' && <p className="text-sm text-slate-500">Building context…</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {result && (
          <>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase">Summary</p>
              <p className="text-slate-700 mt-1">{result.summary}</p>
            </div>
            {result.top_drivers?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase">Top drivers</p>
                <ul className="mt-1 list-disc list-inside text-slate-700 text-sm">
                  {result.top_drivers.map((d, i) => (
                    <li key={i}>{d}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.recommended_actions?.length > 0 && (
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase">Recommended actions</p>
                <ul className="mt-1 space-y-1 text-sm text-slate-700">
                  {result.recommended_actions.map((a, i) => (
                    <li key={i}>• {a.summary || a.action}</li>
                  ))}
                </ul>
              </div>
            )}
            {result.confidence != null && (
              <p className="text-xs text-slate-500">Confidence: {Number(result.confidence * 100).toFixed(0)}%</p>
            )}
            {result.layout && <DynamicDashboardRenderer layout={result.layout} />}
          </>
        )}
      </div>
    </div>
  )
}
