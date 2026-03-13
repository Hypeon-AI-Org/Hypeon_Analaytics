import React, { useState, useEffect, useMemo } from 'react'
import { Search } from 'lucide-react'
import { fetchCampaignPerformance } from '../api'
import { useUserOrg } from '../contexts/UserOrgContext'
import CampaignTable from '../components/CampaignTable'
import ErrorBanner from '../components/ErrorBanner'
import PageReportHeader from '../components/PageReportHeader'

export default function CampaignPage() {
  const { selectedClientId } = useUserOrg()
  const [data, setData] = useState({ items: [] })
  const [campaignFilter, setCampaignFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    fetchCampaignPerformance({ client_id: selectedClientId })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [selectedClientId])

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
    <div className="flex-1 overflow-auto px-6 py-6 space-y-6 bg-slate-50/70">
      <PageReportHeader days={30} onExport={() => {}} />
      <p className="text-sm text-slate-600 max-w-2xl">
        Campaign performance from your connected data. Use the filter to find specific campaigns.
      </p>
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h3 className="text-sm font-semibold text-slate-800 uppercase tracking-wider">Campaigns</h3>
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} strokeWidth={2} />
            <input
              type="text"
              placeholder="Filter campaigns..."
              value={campaignFilter}
              onChange={(e) => setCampaignFilter(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-slate-800 placeholder-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
              aria-label="Filter campaigns"
            />
          </div>
        </div>
        <div className="glass-card overflow-hidden">
          <CampaignTable items={filteredItems} loading={loading} />
        </div>
      </div>
    </div>
  )
}
