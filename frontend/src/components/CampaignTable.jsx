import React, { useState } from 'react'

const STATUS_STYLE = {
  Scaling: 'bg-emerald-100 text-emerald-800',
  Stable: 'bg-blue-100 text-blue-800',
  Wasting: 'bg-red-100 text-red-800',
}

export default function CampaignTable({ items = [], loading }) {
  const [sortBy, setSortBy] = useState('roas')
  const [sortDir, setSortDir] = useState('desc')

  const sorted = [...items].sort((a, b) => {
    const va = a[sortBy]
    const vb = b[sortBy]
    const n = (typeof va === 'number' ? va : Number(va) || 0) - (typeof vb === 'number' ? vb : Number(vb) || 0)
    return sortDir === 'asc' ? n : -n
  })

  const toggle = (col) => {
    if (sortBy === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else setSortBy(col)
  }

  if (loading) {
    return (
      <div className="animate-pulse rounded-lg border border-slate-200 bg-slate-50 h-64" />
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {['campaign', 'spend', 'revenue', 'roas', 'status'].map((col) => (
                <th
                  key={col}
                  className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase cursor-pointer hover:bg-slate-100"
                  onClick={() => toggle(col)}
                >
                  {col === 'roas' ? 'ROAS' : col.charAt(0).toUpperCase() + col.slice(1)}
                  {sortBy === col && (sortDir === 'asc' ? ' ↑' : ' ↓')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {sorted.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm text-slate-800">{row.campaign}</td>
                <td className="px-4 py-3 text-sm text-slate-700">{formatNum(row.spend)}</td>
                <td className="px-4 py-3 text-sm text-slate-700">{formatNum(row.revenue)}</td>
                <td className="px-4 py-3 text-sm text-slate-700">{formatNum(row.roas)}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[row.status] || 'bg-slate-100 text-slate-800'}`}>
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sorted.length === 0 && (
        <p className="p-4 text-center text-slate-500">No campaign data. Cache may not be populated yet.</p>
      )}
    </div>
  )
}

function formatNum(v) {
  if (v == null) return '—'
  const n = Number(v)
  return Number.isInteger(n) ? n : n.toFixed(2)
}
