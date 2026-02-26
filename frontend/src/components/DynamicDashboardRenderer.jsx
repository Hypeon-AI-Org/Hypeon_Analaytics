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

const CHART_COLORS = ['#db2777', '#ec4899', '#f472b6', '#f9a8d4', '#fbcfe8', '#be185d']

export default function DynamicDashboardRenderer({ layout }) {
  if (!layout?.widgets || !Array.isArray(layout.widgets)) {
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
  const trendSym = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '—'
  return (
    <div className="glass-card p-5">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
      <p className="mt-1 text-2xl font-bold text-slate-800">{formatValue(value)}</p>
      {trend != null && <p className={`text-xs mt-0.5 font-medium ${trendCls}`}>{trendSym}</p>}
      {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
    </div>
  )
}

function ChartWidget({ widget }) {
  const { chartType, title, data = [], xKey, yKey } = widget
  if (!data.length) {
    return (
      <div className="glass-card p-5">
        <p className="text-sm font-semibold text-slate-700">{title || 'Chart'}</p>
        <p className="text-slate-400 text-sm mt-1">No data</p>
      </div>
    )
  }
  const x = xKey || (data[0] && Object.keys(data[0])[0])
  const y = yKey || (data[0] && Object.keys(data[0])[1])
  return (
    <div className="glass-card p-5">
      {title && <p className="text-sm font-semibold text-slate-700 mb-2">{title}</p>}
      <ResponsiveContainer width="100%" height={200}>
        {chartType === 'line' ? (
          <LineChart data={data}>
            <XAxis dataKey={x} stroke="#9d174d" fontSize={11} />
            <YAxis stroke="#9d174d" fontSize={11} />
            <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #fbcfe8' }} />
            <Line type="monotone" dataKey={y} stroke="#db2777" strokeWidth={2} dot={{ fill: '#db2777' }} />
          </LineChart>
        ) : chartType === 'pie' ? (
          <PieChart>
            <Pie data={data} dataKey={y} nameKey={x} cx="50%" cy="50%" outerRadius={80} label>
              {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #fbcfe8' }} />
            <Legend />
          </PieChart>
        ) : (
          <BarChart data={data}>
            <XAxis dataKey={x} stroke="#9d174d" fontSize={11} />
            <YAxis stroke="#9d174d" fontSize={11} />
            <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #fbcfe8' }} />
            <Bar dataKey={y} fill="#db2777" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function TableWidget({ widget }) {
  const { title, columns = [], rows = [] } = widget
  return (
    <div className="glass-card overflow-hidden md:col-span-2 lg:col-span-3">
      {title && (
        <div className="px-5 py-3 border-b border-pink-100/60 font-semibold text-slate-700 text-sm uppercase tracking-wider">
          {title}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-pink-100/60">
          <thead className="bg-pink-50/50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-5 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-pink-100/40">
            {rows.map((row, ri) => (
              <tr key={ri} className="hover:bg-pink-50/30 transition-colors">
                {columns.map((col) => (
                  <td key={col.key} className="px-5 py-3 text-sm text-slate-700">
                    {formatValue(row[col.key])}
                  </td>
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
    <div className="glass-card p-5 md:col-span-2">
      {title && <p className="text-sm font-semibold text-slate-700 mb-3">{title}</p>}
      <div className="space-y-2">
        {stages.map((stage, i) => (
          <div key={i}>
            <div className="flex justify-between text-sm">
              <span className="font-medium text-slate-700">{stage.name}</span>
              <span className="text-slate-500">
                {formatValue(stage.value)}
                {stage.dropPct != null ? ` (${Number(stage.dropPct).toFixed(1)}% drop)` : ''}
              </span>
            </div>
            <div className="h-6 bg-pink-100/40 rounded-lg overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-lg transition-all duration-300"
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
