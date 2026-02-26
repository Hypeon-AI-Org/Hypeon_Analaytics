import React, { useState, useEffect } from 'react'
import { fetchCampaignPerformance } from '../api'
import CampaignTable from '../components/CampaignTable'
import ErrorBanner from '../components/ErrorBanner'

export default function CampaignPage() {
  const [data, setData] = useState({ items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchCampaignPerformance()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  if (error) {
    return <ErrorBanner message={error} onRetry={load} />
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">Campaign performance from cache. Status: Scaling (ROAS &gt; 3), Stable (1–3), Wasting (low ROAS).</p>
      <CampaignTable items={data.items || []} loading={loading} />
    </div>
  )
}
