import React, { useState, useEffect, useMemo } from 'react'
import { Search, Filter as FilterIcon } from 'lucide-react'
import { fetchCampaignPerformance } from '../api'
import CampaignTable from '../components/CampaignTable'
import ErrorBanner from '../components/ErrorBanner'
import PageReportHeader from '../components/PageReportHeader'

export default function CampaignPage() {
  const [data, setData] = useState({ items: [] })
  const [campaignFilter, setCampaignFilter] = useState('')
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

  const filteredItems = useMemo(() => {
    const list = data?.items ?? []
    if (!campaignFilter.trim()) return list
    const q = campaignFilter.trim().toLowerCase()
    return list.filter((c) => (c.campaign || '').toLowerCase().includes(q))
  }, [data?.items, campaignFilter])

  if (error) {
    return (
      <div className="flex-1 overflow-auto px-6 py-6">
        <ErrorBanner message={error} onRetry={load} />
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
      <PageReportHeader days={30} onExport={() => {}} />
      <p className="text-sm text-slate-600">
        Campaign performance from cache. Status: Scaling (ROAS &gt; 3), Stable (1–3), Wasting (low ROAS).
      </p>
      <div>
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">Campaign Performance</h3>
        <div className="flex items-center gap-2 mb-3">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} strokeWidth={2} />
            <input
              type="text"
              placeholder="Filter campaigns..."
              value={campaignFilter}
              onChange={(e) => setCampaignFilter(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-slate-800 placeholder-slate-400 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
          <button type="button" aria-label="Filter" className="p-2 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50">
            <FilterIcon size={18} strokeWidth={2} />
          </button>
        </div>
        <CampaignTable items={filteredItems} loading={loading} />
      </div>
    </div>
  )
}
