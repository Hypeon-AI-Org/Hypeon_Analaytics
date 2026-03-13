import React, { useState, useEffect, useMemo } from 'react'
import {
  Database,
  Table as TableIcon,
  BarChart3,
  LineChart as LineChartIcon,
  RefreshCw,
  ChevronRight,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
} from 'recharts'
import {
  fetchDynamicDashboardTables,
  fetchDynamicDashboardPreview,
  fetchDynamicDashboardAggregate,
  fetchDynamicDashboardTimeSeries,
} from '../api'
import ErrorBanner from '../components/ErrorBanner'

const CHART_COLORS = ['#374151', '#4b5563', '#6b7280', '#059669', '#0d9488', '#2563eb']

function formatCellValue(v) {
  if (v == null) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2)
  if (typeof v === 'string' && v.length > 80) return v.slice(0, 80) + '…'
  return String(v)
}

export default function ExplorePage() {
  const [tables, setTables] = useState([])
  const [tablesLoading, setTablesLoading] = useState(true)
  const [tablesError, setTablesError] = useState(null)
  const [selectedTable, setSelectedTable] = useState(null)
  const [previewRows, setPreviewRows] = useState([])
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState(null)
  const [chartData, setChartData] = useState([])
  const [chartType, setChartType] = useState('breakdown')
  const [chartLoading, setChartLoading] = useState(false)
  const [chartError, setChartError] = useState(null)
  const [groupByCol, setGroupByCol] = useState('')
  const [metricCol, setMetricCol] = useState('')
  const [aggFunc, setAggFunc] = useState('sum')
  const [dateCol, setDateCol] = useState('')
  const [dateTrunc, setDateTrunc] = useState('day')

  const loadTables = () => {
    setTablesLoading(true)
    setTablesError(null)
    fetchDynamicDashboardTables()
      .then((res) => {
        setTables(res.tables || [])
        setTablesLoading(false)
      })
      .catch((err) => {
        setTablesError(err.message)
        setTablesLoading(false)
      })
  }

  useEffect(() => {
    loadTables()
  }, [])

  const tablesByDataset = useMemo(() => {
    const map = new Map()
    for (const t of tables) {
      const key = `${t.project || ''}.${t.dataset || ''}`
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(t)
    }
    return map
  }, [tables])

  const loadPreview = () => {
    if (!selectedTable) return
    setPreviewLoading(true)
    setPreviewError(null)
    fetchDynamicDashboardPreview({
      project: selectedTable.project,
      dataset: selectedTable.dataset,
      table: selectedTable.table_name,
      limit: 200,
    })
      .then((res) => {
        setPreviewRows(res.rows || [])
        setPreviewLoading(false)
      })
      .catch((err) => {
        setPreviewError(err.message)
        setPreviewLoading(false)
      })
  }

  useEffect(() => {
    if (selectedTable) {
      setPreviewRows([])
      setPreviewError(null)
      setChartData([])
      setChartError(null)
      const cols = selectedTable.columns || []
      const firstStr = cols.find((c) => (c.data_type || '').toLowerCase().includes('string') || (c.data_type || '').toLowerCase().includes('int'))?.name
      const firstNum = cols.find((c) => (c.data_type || '').toLowerCase().includes('float') || (c.data_type || '').toLowerCase().includes('int') || (c.data_type || '').toLowerCase().includes('numeric'))?.name
      const firstDate = cols.find((c) => (c.data_type || '').toLowerCase().includes('date') || (c.data_type || '').toLowerCase().includes('timestamp'))?.name
      setGroupByCol(firstStr || (cols[0]?.name || ''))
      setMetricCol(firstNum || (cols[1]?.name || ''))
      setDateCol(firstDate || '')
    }
  }, [selectedTable])

  const runChart = () => {
    if (!selectedTable) return
    setChartLoading(true)
    setChartError(null)
    if (chartType === 'breakdown') {
      fetchDynamicDashboardAggregate({
        project: selectedTable.project,
        dataset: selectedTable.dataset,
        table: selectedTable.table_name,
        group_by_column: groupByCol,
        metric_column: metricCol,
        agg: aggFunc,
        limit: 50,
      })
        .then((res) => {
          setChartData(res.rows || [])
          setChartLoading(false)
        })
        .catch((err) => {
          setChartError(err.message)
          setChartLoading(false)
        })
    } else {
      fetchDynamicDashboardTimeSeries({
        project: selectedTable.project,
        dataset: selectedTable.dataset,
        table: selectedTable.table_name,
        date_column: dateCol,
        metric_column: metricCol,
        agg: aggFunc,
        date_trunc: dateTrunc,
        limit: 366,
      })
        .then((res) => {
          const rows = (res.rows || []).map((r) => ({
            ...r,
            date_value: r.date_value ? String(r.date_value).slice(0, 10) : r.date_value,
          }))
          setChartData(rows)
          setChartLoading(false)
        })
        .catch((err) => {
          setChartError(err.message)
          setChartLoading(false)
        })
    }
  }

  const columns = selectedTable?.columns || []
  const numericColumns = columns.filter(
    (c) =>
      (c.data_type || '').toLowerCase().includes('float') ||
      (c.data_type || '').toLowerCase().includes('int') ||
      (c.data_type || '').toLowerCase().includes('numeric')
  )
  const stringColumns = columns.filter(
    (c) =>
      (c.data_type || '').toLowerCase().includes('string') ||
      (c.data_type || '').toLowerCase().includes('int')
  )
  const dateColumns = columns.filter(
    (c) =>
      (c.data_type || '').toLowerCase().includes('date') ||
      (c.data_type || '').toLowerCase().includes('timestamp')
  )

  return (
    <div className="flex-1 overflow-auto flex flex-col bg-slate-50/50">
      <div className="flex-shrink-0 px-6 py-4 border-b border-slate-200 bg-white">
        <h1 className="text-lg font-semibold text-slate-800">Explore data</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Browse your datasets and tables, preview rows, and build breakdown or time-series charts from any table.
        </p>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Left: table list */}
        <aside className="w-72 flex-shrink-0 border-r border-slate-200 bg-white overflow-y-auto">
          <div className="p-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tables</span>
            <button
              type="button"
              onClick={loadTables}
              disabled={tablesLoading}
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw size={16} className={tablesLoading ? 'animate-spin' : ''} />
            </button>
          </div>
          {tablesError && (
            <div className="px-3 pb-2">
              <ErrorBanner message={tablesError} onRetry={loadTables} />
            </div>
          )}
          {tablesLoading && !tables.length && (
            <div className="px-3 py-6 text-sm text-slate-500">Loading tables…</div>
          )}
          <div className="pb-4">
            {Array.from(tablesByDataset.entries()).map(([key, list]) => (
              <div key={key} className="mb-2">
                <div className="px-3 py-1.5 text-xs font-medium text-slate-400 truncate" title={key}>
                  {key}
                </div>
                {list.map((t) => {
                  const isSelected =
                    selectedTable &&
                    selectedTable.project === t.project &&
                    selectedTable.dataset === t.dataset &&
                    selectedTable.table_name === t.table_name
                  return (
                    <button
                      key={`${t.project}.${t.dataset}.${t.table_name}`}
                      type="button"
                      onClick={() => setSelectedTable(t)}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
                        isSelected ? 'bg-slate-100 text-slate-900 font-medium' : 'text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      <TableIcon size={16} className="flex-shrink-0 text-slate-400" />
                      <span className="truncate">{t.table_name}</span>
                      <ChevronRight size={14} className={`flex-shrink-0 ml-auto ${isSelected ? 'text-slate-600' : 'text-slate-300'}`} />
                    </button>
                  )
                })}
              </div>
            ))}
          </div>
        </aside>

        {/* Main: schema, preview, chart */}
        <main className="flex-1 overflow-auto p-6">
          {!selectedTable && (
            <div className="flex flex-col items-center justify-center h-64 text-slate-500">
              <Database size={48} className="text-slate-300 mb-3" />
              <p className="text-sm">Select a table from the left to preview data and build charts.</p>
            </div>
          )}

          {selectedTable && (
            <div className="space-y-6 max-w-5xl">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-slate-800">
                  {selectedTable.dataset}.{selectedTable.table_name}
                </h2>
                <button
                  type="button"
                  onClick={loadPreview}
                  disabled={previewLoading}
                  className="text-sm font-medium text-slate-700 hover:text-slate-900 disabled:opacity-50"
                >
                  {previewLoading ? 'Loading…' : 'Load preview'}
                </button>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
                  <h3 className="text-sm font-semibold text-slate-700">Columns</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200">
                        <th className="px-4 py-2 text-left font-medium text-slate-500">Name</th>
                        <th className="px-4 py-2 text-left font-medium text-slate-500">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {columns.map((c) => (
                        <tr key={c.name} className="border-b border-slate-100">
                          <td className="px-4 py-2 font-mono text-slate-800">{c.name}</td>
                          <td className="px-4 py-2 text-slate-500">{c.data_type || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {previewError && <ErrorBanner message={previewError} onRetry={loadPreview} />}
              {previewRows.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
                    <h3 className="text-sm font-semibold text-slate-700">Preview ({previewRows.length} rows)</h3>
                  </div>
                  <div className="overflow-x-auto max-h-96 overflow-y-auto">
                    <table className="min-w-full text-sm">
                      <thead className="sticky top-0 bg-slate-50">
                        <tr className="border-b border-slate-200">
                          {previewRows[0] && Object.keys(previewRows[0]).map((k) => (
                            <th key={k} className="px-4 py-2 text-left font-medium text-slate-500 whitespace-nowrap">
                              {k}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewRows.map((row, i) => (
                          <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                            {Object.entries(row).map(([k, v]) => (
                              <td key={k} className="px-4 py-2 text-slate-700 whitespace-nowrap max-w-xs truncate" title={String(v)}>
                                {formatCellValue(v)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex flex-wrap items-center gap-4">
                  <h3 className="text-sm font-semibold text-slate-700">Chart</h3>
                  <select
                    value={chartType}
                    onChange={(e) => setChartType(e.target.value)}
                    className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 bg-white"
                  >
                    <option value="breakdown">Breakdown (group by category)</option>
                    <option value="time-series">Time series</option>
                  </select>
                  {chartType === 'breakdown' && (
                    <>
                      <label className="text-xs text-slate-500">
                        Group by
                        <select
                          value={groupByCol}
                          onChange={(e) => setGroupByCol(e.target.value)}
                          className="ml-1 rounded border border-slate-200 px-2 py-1 text-sm"
                        >
                          {stringColumns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <label className="text-xs text-slate-500">
                        Metric
                        <select
                          value={metricCol}
                          onChange={(e) => setMetricCol(e.target.value)}
                          className="ml-1 rounded border border-slate-200 px-2 py-1 text-sm"
                        >
                          {columns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <select
                        value={aggFunc}
                        onChange={(e) => setAggFunc(e.target.value)}
                        className="rounded border border-slate-200 px-2 py-1 text-sm"
                      >
                        <option value="sum">Sum</option>
                        <option value="avg">Avg</option>
                        <option value="count">Count</option>
                        <option value="min">Min</option>
                        <option value="max">Max</option>
                      </select>
                    </>
                  )}
                  {chartType === 'time-series' && (
                    <>
                      <label className="text-xs text-slate-500">
                        Date
                        <select
                          value={dateCol}
                          onChange={(e) => setDateCol(e.target.value)}
                          className="ml-1 rounded border border-slate-200 px-2 py-1 text-sm"
                        >
                          {dateColumns.length ? dateColumns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name}</option>
                          )) : columns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <label className="text-xs text-slate-500">
                        Metric
                        <select
                          value={metricCol}
                          onChange={(e) => setMetricCol(e.target.value)}
                          className="ml-1 rounded border border-slate-200 px-2 py-1 text-sm"
                        >
                          {columns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <select
                        value={dateTrunc}
                        onChange={(e) => setDateTrunc(e.target.value)}
                        className="rounded border border-slate-200 px-2 py-1 text-sm"
                      >
                        <option value="day">By day</option>
                        <option value="week">By week</option>
                        <option value="month">By month</option>
                      </select>
                      <select
                        value={aggFunc}
                        onChange={(e) => setAggFunc(e.target.value)}
                        className="rounded border border-slate-200 px-2 py-1 text-sm"
                      >
                        <option value="sum">Sum</option>
                        <option value="avg">Avg</option>
                        <option value="count">Count</option>
                        <option value="min">Min</option>
                        <option value="max">Max</option>
                      </select>
                    </>
                  )}
                  <button
                    type="button"
                    onClick={runChart}
                    disabled={chartLoading || (chartType === 'breakdown' && (!groupByCol || !metricCol)) || (chartType === 'time-series' && (!dateCol || !metricCol))}
                    className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {chartType === 'breakdown' ? <BarChart3 size={16} /> : <LineChartIcon size={16} />}
                    {chartLoading ? 'Loading…' : 'Run'}
                  </button>
                </div>
                {chartError && (
                  <div className="px-4 py-2">
                    <ErrorBanner message={chartError} onRetry={runChart} />
                  </div>
                )}
                <div className="p-4 min-h-[280px]">
                  {chartData.length > 0 && chartType === 'breakdown' && (
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="group_value" tick={{ fontSize: 11 }} stroke="#94a3b8" angle={-45} textAnchor="end" height={60} />
                        <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                        <Tooltip />
                        <Bar dataKey="metric_value" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} name="Value" />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                  {chartData.length > 0 && chartType === 'time-series' && (
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="date_value" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                        <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                        <Tooltip />
                        <Line type="monotone" dataKey="metric_value" stroke={CHART_COLORS[2]} strokeWidth={2} dot={false} name="Value" />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                  {!chartData.length && !chartLoading && !chartError && (
                    <p className="text-sm text-slate-500">Choose options above and click Run to build a chart.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
