import React from 'react'
import { Calendar, Download } from 'lucide-react'

function formatReportDateRange(days = 30) {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - days)
  return `${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
}

export default function PageReportHeader({ days = 30, onExport }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Reporting Period</h3>
        <p className="mt-1 flex items-center gap-2 text-slate-600">
          <Calendar className="flex-shrink-0" size={16} strokeWidth={2} />
          Last {days} days ({formatReportDateRange(days)})
        </p>
      </div>
      <button
        type="button"
        onClick={onExport}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
      >
        <Download size={18} strokeWidth={2} />
        Export Report
      </button>
    </div>
  )
}
