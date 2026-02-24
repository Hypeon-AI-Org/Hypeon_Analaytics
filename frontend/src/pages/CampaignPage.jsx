import React, { useState, useEffect } from 'react'
import { fetchCampaignPerformance } from '../api'
import CampaignTable from '../components/CampaignTable'

export default function CampaignPage() {
  const [data, setData] = useState({ items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    fetchCampaignPerformance()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3" role="alert">
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">Campaign performance from cache. Status: Scaling (ROAS &gt; 3), Stable (1–3), Wasting (low ROAS).</p>
      <CampaignTable items={data.items || []} loading={loading} />
    </div>
  )
}
