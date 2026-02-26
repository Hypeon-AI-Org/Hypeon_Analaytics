import React, { useState, useEffect } from 'react'
import { fetchFunnel } from '../api'
import ErrorBanner from '../components/ErrorBanner'

export default function FunnelPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchFunnel()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  if (loading && !data) {
    return <div className="animate-pulse rounded-xl bg-pink-100/50 h-64" />
  }

  if (error) {
    return <ErrorBanner message={error} onRetry={load} />
  }

  const clicks = data?.clicks ?? 0
  const sessions = data?.sessions ?? 0
  const purchases = data?.purchases ?? 0
  const drops = data?.drop_percentages ?? []
  const maxVal = Math.max(clicks, sessions, purchases, 1)

  const stages = [
    { name: 'Clicks', value: clicks, drop: drops[0] },
    { name: 'Sessions', value: sessions, drop: drops[1] },
    { name: 'Purchases', value: purchases },
  ]

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-600">Funnel from cache (last 30d). Drop % between stages.</p>
      <div className="glass-card p-6 max-w-2xl">
        <div className="space-y-4">
          {stages.map((stage, i) => (
            <div key={i}>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium text-slate-700">{stage.name}</span>
                <span className="text-slate-500">
                  {stage.value}
                  {stage.drop != null && <span className="text-brand-600 ml-1">({Number(stage.drop).toFixed(1)}% drop)</span>}
                </span>
              </div>
              <div className="h-8 bg-pink-100/40 rounded-lg overflow-hidden">
                <div
                  className="h-full bg-brand-500 rounded-lg transition-all duration-300"
                  style={{ width: `${(Number(stage.value) / maxVal) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
