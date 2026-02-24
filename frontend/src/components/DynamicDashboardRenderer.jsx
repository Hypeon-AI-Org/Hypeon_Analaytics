import React from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'

const CHART_COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981']

export default function DynamicDashboardRenderer({ layout }) {
  if (!layout || !layout.widgets || !Array.isArray(layout.widgets)) {
    return null
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {layout.widgets.map((widget, idx) => (
        <Widget key={idx} widget={widget} />
      ))}
    </div>
  )
}

function Widget({ widget }) {
  const { type } = widget
  if (type === 'kpi') return <KpiCard widget={widget} />
  if (type === 'chart') return <ChartWidget widget={widget} />
  if (type === 'table') return <TableWidget widget={widget} />
  if (type === 'funnel') return <FunnelWidget widget={widget} />
  return null
}

function KpiCard({ widget }) {
  const { title, value, trend, subtitle } = widget
  const trendCls = trend === 'up' ? 'text-emerald-600' : trend === 'down' ? 'text-red-600' : 'text-slate-500'
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-800">{formatValue(value)}</p>
      {trend != null && <p className={`text-xs mt-0.5 ${trendCls}`}>{trend === 'up' ? '↑' : trend === 'down' ? '↓' : '—'}</p>}
      {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
    </div>
  )
}

function ChartWidget({ widget }) {
  const { chartType, title, data = [], xKey, yKey } = widget
  if (!data.length) return <div className="rounded-lg border bg-white p-4"><p className="text-sm text-slate-500">{title || 'Chart'}</p><p className="text-slate-400">No data</p></div>
  const x = xKey || (data[0] && Object.keys(data[0])[0])
  const y = yKey || (data[0] && Object.keys(data[0])[1])
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      {title && <p className="text-sm font-medium text-slate-700 mb-2">{title}</p>}
      <ResponsiveContainer width="100%" height={200}>
        {chartType === 'line' ? (
          <LineChart data={data}>
            <XAxis dataKey={x} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey={y} stroke="#6366f1" strokeWidth={2} />
          </LineChart>
        ) : chartType === 'pie' ? (
          <PieChart>
            <Pie data={data} dataKey={y} nameKey={x} cx="50%" cy="50%" outerRadius={80} label>
              {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        ) : (
          <BarChart data={data}>
            <XAxis dataKey={x} />
            <YAxis />
            <Tooltip />
            <Bar dataKey={y} fill="#6366f1" />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function TableWidget({ widget }) {
  const { title, columns = [], rows = [] } = widget
  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden md:col-span-2 lg:col-span-3">
      {title && <div className="px-4 py-2 border-b border-slate-200 font-medium text-slate-700">{title}</div>}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              {columns.map((col) => (
                <th key={col.key} className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase">{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {rows.map((row, ri) => (
              <tr key={ri} className="hover:bg-slate-50">
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-2 text-sm text-slate-700">{formatValue(row[col.key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function FunnelWidget({ widget }) {
  const { title, stages = [] } = widget
  if (!stages.length) return null
  const maxVal = Math.max(...stages.map((s) => Number(s.value) || 0), 1)
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm md:col-span-2">
      {title && <p className="text-sm font-medium text-slate-700 mb-3">{title}</p>}
      <div className="space-y-2">
        {stages.map((stage, i) => (
          <div key={i}>
            <div className="flex justify-between text-sm">
              <span className="font-medium text-slate-700">{stage.name}</span>
              <span className="text-slate-500">{formatValue(stage.value)}{stage.dropPct != null ? ` (${Number(stage.dropPct).toFixed(1)}% drop)` : ''}</span>
            </div>
            <div className="h-6 bg-slate-100 rounded overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded"
                style={{ width: `${(Number(stage.value) / maxVal) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function formatValue(v) {
  if (v == null) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v : v.toFixed(2)
  return String(v)
}
