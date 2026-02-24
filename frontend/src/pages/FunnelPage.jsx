import React, { useState, useEffect } from 'react'
import { fetchFunnel } from '../api'

export default function FunnelPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchFunnel()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading && !data) {
    return <div className="animate-pulse rounded-lg bg-slate-100 h-64" />
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3" role="alert">
        {error}
      </div>
    )
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
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm max-w-2xl">
        <div className="space-y-4">
          {stages.map((stage, i) => (
            <div key={i}>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-medium text-slate-700">{stage.name}</span>
                <span className="text-slate-500">
                  {stage.value}
                  {stage.drop != null && <span className="text-amber-600 ml-1">({Number(stage.drop).toFixed(1)}% drop)</span>}
                </span>
              </div>
              <div className="h-8 bg-slate-100 rounded overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded transition-all"
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
