import React, { useState } from 'react'

const PRESETS = [
  { label: '7d', days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
]

export default function DateRangePicker({ onChange, initialDays = 30 }) {
  const [activePreset, setActivePreset] = useState(initialDays)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [showCustom, setShowCustom] = useState(false)

  const selectPreset = (days) => {
    setActivePreset(days)
    setShowCustom(false)
    onChange({ days })
  }

  const applyCustom = () => {
    if (customStart && customEnd) {
      setActivePreset(null)
      onChange({ start_date: customStart, end_date: customEnd })
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map((p) => (
        <button
          key={p.days}
          type="button"
          onClick={() => selectPreset(p.days)}
          className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-colors ${
            activePreset === p.days && !showCustom
              ? 'bg-brand-600 text-white'
              : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
          }`}
        >
          {p.label}
        </button>
      ))}
      <button
        type="button"
        onClick={() => setShowCustom(!showCustom)}
        className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-colors ${
          showCustom
            ? 'bg-brand-600 text-white'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
        }`}
      >
        Custom
      </button>
      {showCustom && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={customStart}
            onChange={(e) => setCustomStart(e.target.value)}
            className="rounded-xl border border-pink-200/80 px-2 py-1.5 text-sm focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
          />
          <span className="text-slate-400 text-sm">to</span>
          <input
            type="date"
            value={customEnd}
            onChange={(e) => setCustomEnd(e.target.value)}
            className="rounded-xl border border-pink-200/80 px-2 py-1.5 text-sm focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
          />
          <button
            type="button"
            onClick={applyCustom}
            disabled={!customStart || !customEnd}
            className="px-3 py-1.5 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Apply
          </button>
        </div>
      )}
    </div>
  )
}
