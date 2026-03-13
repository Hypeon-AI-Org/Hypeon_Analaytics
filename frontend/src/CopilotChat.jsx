import React, { useState, useRef, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, ThumbsUp, ThumbsDown } from 'lucide-react'
import html2canvas from 'html2canvas'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { copilotChatStream, copilotChatHistory, fetchCopilotSessions, fetchCopilotStoreInfo, deleteCopilotSessions } from './api'
import { useAuth } from './contexts/AuthContext'
import { useUserOrg } from './contexts/UserOrgContext'

/** Derive 2-letter initials from Firebase user (displayName or email). */
function userInitials(user) {
  if (!user) return '?'
  const name = (user.displayName || '').trim()
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean)
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    if (parts[0].length >= 2) return parts[0].slice(0, 2).toUpperCase()
    return parts[0][0].toUpperCase()
  }
  const email = (user.email || '').trim()
  if (email) {
    const local = email.split('@')[0] || ''
    if (local.length >= 2) return local.slice(0, 2).toUpperCase()
    return local[0]?.toUpperCase() || '?'
  }
  return '?'
}

/** Display name for sidebar: displayName or email local part or email. */
function userDisplayName(user) {
  if (!user) return 'Guest'
  const name = (user.displayName || '').trim()
  if (name) return name
  const email = (user.email || '').trim()
  if (email) return email.split('@')[0] || email
  return 'Guest'
}

const COPILOT_SESSION_KEY = 'hypeon_copilot_session_id'

/** Split steps into reasoning (model's thought process) and pipeline (discovering, SQL, run, format). */
function splitThinkingSteps(steps) {
  if (!steps?.length) return { reasoningSteps: [], pipelineSteps: [] }
  const reasoningSteps = steps.filter((s) => s.stepKind === 'reasoning' || s.step === 'Thinking…')
  const pipelineSteps = steps.filter((s) => s.stepKind !== 'reasoning' && s.step !== 'Thinking…')
  return { reasoningSteps, pipelineSteps }
}

/** Parse reasoning text into list items (lines or bullets) for clearer display. */
function parseReasoningToList(detail) {
  if (!detail || typeof detail !== 'string') return []
  const lines = detail
    .split(/\n+/)
    .map((l) => l.replace(/^[\s•\-*]+\s*/, '').trim())
    .filter(Boolean)
  return lines.length ? lines : (detail.trim() ? [detail.trim()] : [])
}

/** Sidebar logo: put your image at frontend/public/logo.png (or .svg and use /logo.svg). Falls back to default if missing. */
const SIDEBAR_LOGO = '/images/hypeon.png'

function formatSessionDate(ts) {
  if (ts == null) return ''
  const d = new Date(ts * 1000)
  const now = new Date()
  const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return d.toLocaleDateString()
}

/** Detect if data is chartable (has at least one numeric column and one label column). Returns { xKey, yKey, useLine } or null. */
function getChartConfig(data) {
  if (!Array.isArray(data) || data.length < 2) return null
  const keys = Object.keys(data[0] || {})
  if (keys.length < 2) return null
  let xKey = null
  let yKey = null
  const dateLike = /date|time|day|month|year|week|ts/i
  for (const k of keys) {
    const vals = data.map((r) => r[k])
    const allNumeric = vals.every((v) => v === null || v === undefined || typeof v === 'number' || (typeof v === 'string' && !Number.isNaN(Number(v))))
    const allString = vals.every((v) => v === null || v === undefined || typeof v === 'string')
    if (allNumeric && vals.some((v) => v != null && v !== '')) {
      if (!yKey) yKey = k
    } else if (allString || typeof vals[0] === 'string' || typeof vals[0] === 'number') {
      if (!xKey) xKey = k
    }
  }
  if (!xKey) xKey = keys[0]
  if (!yKey) {
    const firstNumeric = keys.find((k) => {
      const v = data[0][k]
      return typeof v === 'number' || (typeof v === 'string' && !Number.isNaN(Number(v)))
    })
    if (firstNumeric) yKey = firstNumeric
  }
  if (!xKey || !yKey || xKey === yKey) return null
  const useLine = dateLike.test(xKey) || dateLike.test(yKey) || keys.some((k) => dateLike.test(k))
  return { xKey, yKey, useLine }
}

function CopyButton({ onCopy, className = '', title = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  const handleClick = async () => {
    await onCopy()
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button
      type="button"
      onClick={handleClick}
      title={title}
      className={`p-1.5 rounded text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors ${className}`}
      aria-label={title}
    >
      {copied ? (
        <span className="text-xs text-emerald-600">✓</span>
      ) : (
        <Copy size={14} strokeWidth={2} aria-hidden />
      )}
    </button>
  )
}

function TableWithCopy({ children, ...tableProps }) {
  const tableRef = useRef(null)
  const copyTable = async () => {
    if (!tableRef.current) return
    const table = tableRef.current
    const rows = Array.from(table.querySelectorAll('tr')).map((tr) =>
      Array.from(tr.querySelectorAll('th, td')).map((cell) => cell.textContent.trim()).join('\t')
    )
    await navigator.clipboard.writeText(rows.join('\n'))
  }
  return (
    <div className="relative my-3 overflow-x-auto">
      <div className="absolute top-2 right-2 z-10">
        <CopyButton onCopy={copyTable} title="Copy table" />
      </div>
      <table ref={tableRef} className="min-w-full text-sm border-collapse prose-table:w-full prose-th:bg-slate-100 prose-td:border-b prose-td:border-slate-200" {...tableProps}>
        {children}
      </table>
    </div>
  )
}

function CopilotDataChart({ data }) {
  const chartRef = useRef(null)
  const config = getChartConfig(data)
  const copyAsImage = async () => {
    if (!chartRef.current) return
    try {
      const canvas = await html2canvas(chartRef.current, {
        backgroundColor: '#ffffff',
        scale: 2,
        useCORS: true,
        logging: false,
        ignoreElements: (el) => el.closest?.('[data-chart-copy-ignore="true"]') != null,
      })
      canvas.toBlob((b) => {
        if (b) navigator.clipboard.write([new ClipboardItem({ 'image/png': b })])
      }, 'image/png')
    } catch (_) {
      const svg = chartRef.current.querySelector('svg')
      if (!svg) return
      try {
        const clone = svg.cloneNode(true)
        const outW = 800
        const outH = 440
        const rect = svg.getBoundingClientRect()
        const srcW = parseFloat(svg.getAttribute('width')) || rect.width || 400
        const srcH = parseFloat(svg.getAttribute('height')) || rect.height || 220
        clone.setAttribute('width', String(outW))
        clone.setAttribute('height', String(outH))
        if (!clone.getAttribute('viewBox') && !clone.getAttribute('viewbox')) clone.setAttribute('viewBox', `0 0 ${srcW} ${srcH}`)
        const svgStr = new XMLSerializer().serializeToString(clone)
        const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const img = new Image()
        img.onload = () => {
          const c = document.createElement('canvas')
          c.width = outW
          c.height = outH
          const ctx = c.getContext('2d')
          if (ctx) {
            ctx.fillStyle = '#ffffff'
            ctx.fillRect(0, 0, outW, outH)
            ctx.drawImage(img, 0, 0, outW, outH)
            c.toBlob((b) => { if (b) navigator.clipboard.write([new ClipboardItem({ 'image/png': b })]); URL.revokeObjectURL(url) }, 'image/png')
          } else URL.revokeObjectURL(url)
        }
        img.onerror = () => URL.revokeObjectURL(url)
        img.src = url
      } catch (__) {}
    }
  }
  if (!config) return null
  const { xKey, yKey, useLine } = config
  const chartData = data.slice(0, 50).map((r) => ({ ...r, [xKey]: r[xKey] != null ? String(r[xKey]) : '', [yKey]: Number(r[yKey]) || 0 }))
  return (
    <div ref={chartRef} className="relative mt-3 mb-2 rounded-xl border border-slate-200 bg-white/80 p-3" style={{ minHeight: 220 }}>
      <div className="absolute top-2 right-2 z-10" data-chart-copy-ignore="true">
        <CopyButton onCopy={copyAsImage} title="Copy as image" />
      </div>
      <ResponsiveContainer width="100%" height={220}>
        {useLine ? (
          <LineChart data={chartData}>
            <XAxis dataKey={xKey} stroke="#64748b" fontSize={11} tick={{ fill: '#475569' }} />
            <YAxis stroke="#64748b" fontSize={11} tick={{ fill: '#475569' }} />
            <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0' }} />
            <Line type="monotone" dataKey={yKey} stroke="#7c3aed" strokeWidth={2} dot={{ fill: '#7c3aed', r: 3 }} />
          </LineChart>
        ) : (
          <BarChart data={chartData}>
            <XAxis dataKey={xKey} stroke="#64748b" fontSize={11} tick={{ fill: '#475569' }} />
            <YAxis stroke="#64748b" fontSize={11} tick={{ fill: '#475569' }} />
            <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0' }} />
            <Bar dataKey={yKey} fill="#7c3aed" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function HypeOnGradientLogo({ size = 'lg' }) {
  const dims = size === 'xl' ? { box: 'w-24 h-24', svg: 48 } : size === 'lg' ? { box: 'w-16 h-16', svg: 32 } : size === 'sidebar' ? { box: 'w-12 h-12', svg: 24 } : size === 'md' ? { box: 'w-10 h-10', svg: 20 } : { box: 'w-6 h-6', svg: 12 }
  return (
    <div
      className={`flex items-center justify-center flex-shrink-0 ${dims.box}`}
      aria-hidden
    >
      <svg
        width={dims.svg}
        height={dims.svg}
        viewBox="0 0 24 24"
        fill="none"
        className="flex-shrink-0"
      >
        <path
          d="M7 17L17 7M17 7h-7m7 0v7"
          stroke="#171717"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

function SidebarLogo({ size = 'sm' }) {
  const [imgFailed, setImgFailed] = React.useState(false)
  const boxClass = size === 'xl' ? 'w-24 h-24' : size === 'lg' ? 'w-16 h-16' : size === 'sidebar' ? 'w-12 h-12' : size === 'md' ? 'w-10 h-10' : 'w-6 h-6'
  if (!imgFailed && SIDEBAR_LOGO) {
    return (
      <img
        src={SIDEBAR_LOGO}
        alt="Logo"
        className={`object-contain flex-shrink-0 logo-bw ${boxClass}`}
        onError={() => setImgFailed(true)}
      />
    )
  }
  return <HypeOnGradientLogo size={size} />
}

export default function CopilotChat() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { selectedClientId, organizationId, organizationName } = useUserOrg()
  const initialSessionId = location.state?.sessionId || null
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streamStatus, setStreamStatus] = useState(null)
  const [error, setError] = useState(null)
  const streamRef = useRef(null)
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(initialSessionId || sessionStorage.getItem(COPILOT_SESSION_KEY))
  const sessionIdRef = useRef(initialSessionId || sessionStorage.getItem(COPILOT_SESSION_KEY))
  const messagesEndRef = useRef(null)
  const listEndRef = useRef(null)
  const inputRef = useRef(null)
  const streamingTextRef = useRef('')
  const thinkingStepsRef = useRef([])
  const thinkingStartTimeRef = useRef(null)
  const [thinkingElapsedSec, setThinkingElapsedSec] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [model, setModel] = useState('basic')
  const [storeInfo, setStoreInfo] = useState(null)
  const [sessionsError, setSessionsError] = useState(null)
  const [chatsModalOpen, setChatsModalOpen] = useState(false)
  const [selectedSessionIds, setSelectedSessionIds] = useState(new Set())
  const [modalSearchQuery, setModalSearchQuery] = useState('')
  const [deleteInProgress, setDeleteInProgress] = useState(false)
  const [currentThinkingSteps, setCurrentThinkingSteps] = useState([])
  const [streamThinkingMinimized, setStreamThinkingMinimized] = useState(false)
  const [expandedThinkingMsgId, setExpandedThinkingMsgId] = useState(null)
  const [feedbackByIndex, setFeedbackByIndex] = useState({})

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })

  const setMessageFeedback = (msgIdx, value) => {
    setFeedbackByIndex((prev) => ({ ...prev, [msgIdx]: prev[msgIdx] === value ? null : value }))
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Live elapsed seconds for "Thought for Xs" while thinking
  useEffect(() => {
    if (!loading || !currentThinkingSteps.length || streamThinkingMinimized) return
    const start = thinkingStartTimeRef.current || Date.now()
    const tick = () => setThinkingElapsedSec(Math.round((Date.now() - start) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [loading, currentThinkingSteps.length, streamThinkingMinimized])

  const loadSessions = () => {
    setSessionsError(null)
    fetchCopilotSessions(organizationId)
      .then((r) => {
        setSessions(r.sessions || [])
        setSessionsError(null)
      })
      .catch((err) => {
        setSessions([])
        setSessionsError(err?.message || 'Could not load chat history')
      })
  }

  useEffect(() => {
    fetchCopilotStoreInfo().then((info) => info && setStoreInfo(info)).catch(() => {})
    loadSessions()
  }, [organizationId])

  const loadSession = (sid) => {
    sessionIdRef.current = sid
    setActiveSessionId(sid)
    sessionStorage.setItem(COPILOT_SESSION_KEY, sid)
    setError(null)
    setMessages([])
    setFeedbackByIndex({})
    navigate('/copilot', { state: { sessionId: sid }, replace: true })
    copilotChatHistory(sid)
      .then(({ messages: history }) => {
        setMessages(
          (history || []).map((m) => ({
            role: m.role,
            text: m.content || '',
            layout: m.layout ?? null,
            data: m.data ?? null,
          }))
        )
      })
      .catch(() => setMessages([]))
  }

  const startNewChat = () => {
    sessionIdRef.current = null
    setActiveSessionId(null)
    sessionStorage.removeItem(COPILOT_SESSION_KEY)
    setMessages([])
    setFeedbackByIndex({})
    setError(null)
    setInput('')
    navigate('/copilot', { state: {}, replace: true })
  }

  useEffect(() => {
    if (initialSessionId) {
      sessionIdRef.current = initialSessionId
      setActiveSessionId(initialSessionId)
      copilotChatHistory(initialSessionId)
        .then(({ messages: history }) => {
          if (history?.length) {
            setMessages(
              history.map((m) => ({
                role: m.role,
                text: m.content || '',
                layout: m.layout ?? null,
                data: m.data ?? null,
              }))
            )
          }
        })
        .catch(() => {})
    } else if (!initialSessionId) {
      const stored = sessionStorage.getItem(COPILOT_SESSION_KEY)
      if (stored) {
        sessionIdRef.current = stored
        setActiveSessionId(stored)
        copilotChatHistory(stored).then(({ messages: history }) => {
          if (history?.length) setMessages(history.map((m) => ({ role: m.role, text: m.content || '', layout: m.layout ?? null, data: m.data ?? null })))
        }).catch(() => {})
      } else {
        sessionIdRef.current = null
        setActiveSessionId(null)
        setMessages([])
      }
    }
  }, [initialSessionId])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setError(null)
    setStreamStatus(null)
    setInput('')
    setCurrentThinkingSteps([])
    setStreamThinkingMinimized(false)
    setThinkingElapsedSec(null)
    thinkingStepsRef.current = []
    thinkingStartTimeRef.current = null
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)
    if (streamRef.current?.cancel) streamRef.current.cancel()
    streamingTextRef.current = ''
    const { promise, cancel } = copilotChatStream(
      { message: text, session_id: sessionIdRef.current || undefined, client_id: selectedClientId },
      (ev) => {
        if (ev.phase === 'thinking') {
          if (!thinkingStartTimeRef.current) thinkingStartTimeRef.current = Date.now()
          setStreamStatus(ev.message || 'Reasoning…')
          const stepEntry = { step: ev.message || 'Thinking…', detail: ev.detail ?? '', detailKind: ev.detail_kind ?? 'text', stepKind: ev.step_kind || 'reasoning' }
          thinkingStepsRef.current = [...thinkingStepsRef.current, stepEntry]
          setCurrentThinkingSteps(thinkingStepsRef.current)
        } else if (ev.phase === 'thinking_chunk' && ev.chunk) {
          const steps = thinkingStepsRef.current
          if (steps.length) {
            const last = steps[steps.length - 1]
            const updated = [...steps.slice(0, -1), { ...last, detail: (last.detail || '') + ev.chunk }]
            thinkingStepsRef.current = updated
            setCurrentThinkingSteps(updated)
          }
        } else if (ev.phase === 'analyzing' || ev.phase === 'discovering' || ev.phase === 'generating_sql' || ev.phase === 'running_query' || ev.phase === 'formatting') {
          if (!thinkingStartTimeRef.current) thinkingStartTimeRef.current = Date.now()
          setStreamStatus(ev.message || 'Processing…')
          const detail = ev.sql_preview ?? ev.detail ?? (ev.tables_count != null ? `Found ${ev.tables_count} tables` : null)
          const detailKind = ev.detail_kind ?? 'text'
          const stepEntry = { step: ev.message || 'Processing…', detail, detailKind, stepKind: 'pipeline' }
          thinkingStepsRef.current = [...thinkingStepsRef.current, stepEntry]
          setCurrentThinkingSteps(thinkingStepsRef.current)
        } else if (ev.phase === 'answer_chunk' && ev.chunk) {
          streamingTextRef.current += ev.chunk
          setStreamThinkingMinimized(true)
          setStreamStatus(null) // clear "Formatting results…" so user sees answer streaming
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            if (last?.role === 'assistant' && last?.streaming) {
              return [...prev.slice(0, -1), { ...last, text: streamingTextRef.current }]
            }
            return [...prev, { role: 'assistant', text: streamingTextRef.current, streaming: true }]
          })
        } else if (ev.phase === 'done') {
          if (ev.session_id) {
            sessionIdRef.current = ev.session_id
            setActiveSessionId(ev.session_id)
            sessionStorage.setItem(COPILOT_SESSION_KEY, ev.session_id)
            loadSessions()
          }
          const thinkingDurationSec = thinkingStartTimeRef.current
            ? Math.round((Date.now() - thinkingStartTimeRef.current) / 1000)
            : null
          setMessages((prev) => {
            const last = prev[prev.length - 1]
            const finalText = ev.answer ?? streamingTextRef.current ?? ''
            const thinkingSteps = thinkingStepsRef.current.length ? thinkingStepsRef.current.slice() : null
            if (last?.role === 'assistant' && last?.streaming) {
              return [...prev.slice(0, -1), { role: 'assistant', text: finalText, data: ev.data || null, thinkingSteps, thinkingMinimized: true, thinkingDurationSec }]
            }
            return [...prev, { role: 'assistant', text: finalText, data: ev.data || null, thinkingSteps, thinkingMinimized: true, thinkingDurationSec }]
          })
          setCurrentThinkingSteps([])
          setStreamThinkingMinimized(false)
          setThinkingElapsedSec(null)
          thinkingStartTimeRef.current = null
          setStreamStatus(null)
          setLoading(false)
        } else if (ev.phase === 'error') {
          setError(ev.error || 'Something went wrong')
          setMessages((prev) => [...prev, { role: 'assistant', text: '', error: ev.error }])
          setStreamStatus(null)
          setThinkingElapsedSec(null)
          thinkingStartTimeRef.current = null
          setLoading(false)
        }
      }
    )
    streamRef.current = { cancel }
    try {
      await promise
    } catch (err) {
      if (err.name === 'AbortError') return
      setError(err.message || 'Something went wrong')
      setMessages((prev) => [...prev, { role: 'assistant', text: '', error: err.message }])
      setStreamStatus(null)
      setThinkingElapsedSec(null)
      thinkingStartTimeRef.current = null
      setLoading(false)
    } finally {
      streamRef.current = null
    }
  }

  const exampleCards = [
    {
      title: "ROAS overview",
      description: "Return on ad spend at a glance.",
      icon: "chart",
      question: "Give me a quick overview of our ROAS performance."
    },
    {
      title: "Campaign performance",
      description: "How campaigns perform across channels.",
      icon: "brand",
      question: "Analyze our campaign performance across all channels."
    },
    {
      title: "CPC trends",
      description: "Cost-per-click and optimization.",
      icon: "trend",
      question: "How is our CPC trending and where can we optimize?"
    },
    {
      title: "LTV",
      description: "Customer lifetime value.",
      icon: "search",
      question: "What is our customer lifetime value and how can we improve it?"
    }
  ];

  const filteredSessions = searchQuery.trim()
    ? sessions.filter((s) => (s.title || 'New chat').toLowerCase().includes(searchQuery.toLowerCase()))
    : sessions

  const openChatsModal = () => {
    setModalSearchQuery('')
    setSelectedSessionIds(new Set())
    setChatsModalOpen(true)
  }

  const modalFilteredSessions = modalSearchQuery.trim()
    ? sessions.filter((s) => (s.title || 'New chat').toLowerCase().includes(modalSearchQuery.toLowerCase()))
    : sessions

  const toggleSessionSelection = (sessionId) => {
    setSelectedSessionIds((prev) => {
      const next = new Set(prev)
      if (next.has(sessionId)) next.delete(sessionId)
      else next.add(sessionId)
      return next
    })
  }

  const selectAllSessions = () => {
    setSelectedSessionIds(new Set(modalFilteredSessions.map((s) => s.session_id)))
  }

  const deselectAllSessions = () => setSelectedSessionIds(new Set())

  const deleteSelectedSessions = async () => {
    const ids = Array.from(selectedSessionIds)
    if (ids.length === 0) return
    setDeleteInProgress(true)
    try {
      await deleteCopilotSessions(ids)
      const activeWasDeleted = ids.includes(activeSessionId)
      setSelectedSessionIds(new Set())
      setChatsModalOpen(false)
      loadSessions()
      if (activeWasDeleted) startNewChat()
    } catch (err) {
      setError(err?.message || 'Failed to delete chats')
    } finally {
      setDeleteInProgress(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 overflow-hidden copilot-page-bg animate-copilot-fade-in">
      {/* Left sidebar: glass panel, fixed */}
      <aside
        className={`copilot-sidebar flex flex-col min-h-0 ${sidebarOpen ? '' : 'copilot-sidebar-collapsed'}`}
      >
        <div className={`topRow ${!sidebarOpen ? 'railTop' : ''}`}>
          <div className={`headerLeft ${!sidebarOpen ? 'justify-center' : ''}`}>
            {sidebarOpen ? (
              <div className="logoWrapper">
                <SidebarLogo size="sidebar" />
              </div>
            ) : (
              <button
                type="button"
                className="logoMini"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
              >
                <span className="logoImg">
                  <SidebarLogo size="sidebar" />
                </span>
                <span className="logoMiniArrow" aria-hidden>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </span>
              </button>
            )}
            {sidebarOpen && (
              <span className="brandText truncate"></span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen((o) => !o)}
            className="topToggle"
            aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`w-4 h-4 transition-transform ${sidebarOpen ? '' : 'rotate-180'}`}>
              <path d="M15 19l-7-7 7-7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
        <div className={`section ${!sidebarOpen ? 'railTop' : ''}`}>
          <button
            type="button"
            onClick={startNewChat}
            className={`newChat ${!sidebarOpen ? 'railIconBtn' : ''}`}
          >
            <span className="iconWrap" aria-hidden>+</span>
            <span className="newChatText">New chat</span>
          </button>
          <div className={`menuBtn ${!sidebarOpen ? 'railIconBtn' : ''}`}>
            <span className="iconWrap shrink-0" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chats"
              aria-label="Search chats"
            />
          </div>
        </div>
        <div className="chatsWrapper flex-1 min-h-0 overflow-hidden flex flex-col">
          {sidebarOpen && (
            <>
              <button
                type="button"
                onClick={openChatsModal}
                className="sectionTitle text-left w-full cursor-pointer hover:opacity-80 transition-opacity bg-transparent border-0 p-0"
              >
                YOUR CHATS
              </button>
              {storeInfo?.store === 'memory' && (
                <p className="px-2 py-1 text-xs text-amber-600 dark:text-amber-400" title="Backend is using in-memory store; history is lost on restart. Configure Firestore for persistent chat history.">
                  History not saved (in-memory)
                </p>
              )}
              {sessionsError && (
                <p className="px-2 py-1 text-xs text-red-600 dark:text-red-400" title={sessionsError}>
                  {sessionsError}
                </p>
              )}
              {filteredSessions.length === 0 && !sessionsError ? (
                <p className="px-2 py-1.5 text-xs text-slate-500 italic">No recent chats</p>
              ) : filteredSessions.length > 0 ? (
                <ul className="list">
                  {filteredSessions.map((s) => (
                    <li key={s.session_id}>
                      <button
                        type="button"
                        onClick={() => loadSession(s.session_id)}
                        className={`listItem ${activeSessionId === s.session_id ? 'active' : ''}`}
                        title={s.title || 'New chat'}
                      >
                        <span className="shrink-0" aria-hidden>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3.5 h-3.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                        </span>
                        <span className="chatTitle">{s.title || 'New chat'}</span>
                        <span className="text-[10px] shrink-0 text-slate-400">{formatSessionDate(s.updated_at)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </div>
        <div ref={listEndRef} />
        {sidebarOpen && (
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="backToAnalytics"
          >
            <span className="iconWrap shrink-0" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4">
                <path d="M3 3v18h18" /><path d="M18 17V9" /><path d="M13 17V5" /><path d="M8 17v-3" />
              </svg>
            </span>
            Back to Analytics
          </button>
        )}
        <div className={`footer sidebar-avatar-wrap ${!sidebarOpen ? 'railBottom justify-center' : ''}`}>
          <div className={`avatar ${!sidebarOpen ? 'avatarRail' : ''}`} aria-hidden>{userInitials(user)}</div>
          {sidebarOpen && (
            <div className="min-w-0 flex-1">
              <p className="username truncate">{userDisplayName(user)}</p>
              <p className="plan mt-0.5">{organizationName || 'Member'}</p>
            </div>
          )}
        </div>
      </aside>

      {/* Main chat area – margin so content is not under fixed sidebar */}
      <div
        className={`flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden bg-transparent font-copilot animate-copilot-main-in transition-[margin] duration-300 ${
          sidebarOpen ? 'ml-[240px]' : 'ml-[50px]'
        }`}
      >
        <div className="flex-1 min-h-0 overflow-y-auto relative px-6 pt-8 pb-4">
          <div className="w-full max-w-4xl mx-auto px-4 sm:px-6">
            {messages.length === 0 && !loading && (
              <div className="absolute inset-0 flex flex-col items-center justify-center px-6 font-copilot animate-copilot-fade-in text-center">
                <div className="mb-8 shrink-0" aria-hidden>
                  <SidebarLogo size="xl" />
                </div>
                <h2 className="text-2xl sm:text-3xl font-semibold text-slate-800 tracking-tight">What would you like to know?</h2>
                <p className="mt-3 text-slate-500 text-sm max-w-sm mx-auto">
                  Ask in plain language and get answers from your data.
                </p>
                <p className="mt-8 text-xs text-slate-400">Suggested questions</p>
                <div className="mt-3 w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {exampleCards.map(({ title, description, icon, question }, idx) => (
                    <button
                      key={title}
                      type="button"
                      onClick={() => setInput(question)}
                      style={{ animationDelay: `${idx * 50}ms` }}
                      className="rounded-lg border border-slate-200/80 bg-white px-4 py-3 text-left hover:border-slate-300 hover:bg-slate-50/50 transition-colors flex items-center gap-3 group animate-copilot-slide-up opacity-0"
                    >
                      <span className="w-8 h-8 rounded-md flex items-center justify-center bg-slate-100 text-slate-500 group-hover:text-slate-700 shrink-0" aria-hidden>
                        {icon === 'chart' && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>}
                        {icon === 'brand' && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>}
                        {icon === 'trend' && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>}
                        {icon === 'search' && <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>}
                      </span>
                      <div className="min-w-0 flex-1 text-left">
                        <p className="text-sm font-medium text-slate-800">{title}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                style={{ animationDelay: `${idx * 25}ms` }}
                className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} mb-6 ${msg.role === 'user' ? 'animate-copilot-slide-in-right opacity-0' : 'animate-copilot-slide-in-left opacity-0'}`}
              >
                <div
                  className={`min-w-0 rounded-2xl px-4 py-3 ${msg.role === 'user' ? 'max-w-[85%]' : 'max-w-full'} ${
                    msg.role === 'user'
                      ? 'bg-white text-slate-900 border border-slate-200'
                      : 'bg-transparent'
                  }`}
                >
                  {msg.error ? (
                    <p className="text-sm text-red-600">{msg.error}</p>
                  ) : msg.role === 'user' ? (
                    <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                  ) : (
                    <>
                      {(() => {
                        const isStreamingMsg = idx === messages.length - 1 && msg.role === 'assistant' && (msg.streaming || loading)
                        const steps = msg.thinkingSteps ?? (isStreamingMsg ? currentThinkingSteps : null)
                        const minimized = msg.thinkingMinimized ?? (isStreamingMsg ? streamThinkingMinimized : true)
                        const durationSec = msg.thinkingDurationSec ?? (isStreamingMsg ? thinkingElapsedSec : null)
                        if (!steps || steps.length === 0) return null
                        const { reasoningSteps, pipelineSteps } = splitThinkingSteps(steps)
                        const hasReasoning = reasoningSteps.length > 0
                        const hasPipeline = pipelineSteps.length > 0
                        const isSectionExpanded = (isStreamingMsg && !minimized) || expandedThinkingMsgId === idx
                        return (
                          <div className="mb-3">
                            <button
                              type="button"
                              onClick={() => setExpandedThinkingMsgId((prev) => (prev === idx ? null : idx))}
                              className="w-full flex items-center justify-between gap-2 text-left py-2 px-0 min-h-0 rounded-none border-0 bg-transparent hover:bg-slate-50/50 transition-colors"
                              aria-expanded={isSectionExpanded}
                            >
                              <span className="text-xs font-medium text-slate-600">
                                {durationSec != null ? `Thought (${durationSec}s)` : 'Thought'}
                              </span>
                              <span className="shrink-0 text-slate-400 transition-transform duration-150" style={{ transform: isSectionExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }} aria-hidden>&gt;</span>
                            </button>
                            {isSectionExpanded && (
                              <div className="mt-1.5 space-y-3 pl-2 border-l-2 border-slate-200/60">
                                {hasReasoning && (
                                  <div>
                                    <p className="text-xs font-medium text-slate-500 mb-1.5">Reasoning</p>
                                    {reasoningSteps.map((s, i) => {
                                      const items = parseReasoningToList(s.detail)
                                      if (items.length > 0) {
                                        return (
                                          <ul key={i} className="text-xs text-slate-600 space-y-1 list-disc list-inside mt-1">
                                            {items.map((line, j) => (
                                              <li key={j} className="leading-relaxed">
                                                <span className="prose prose-sm max-w-none prose-p:my-0 prose-ul:my-0 prose-li:my-0">
                                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{line}</ReactMarkdown>
                                                </span>
                                              </li>
                                            ))}
                                          </ul>
                                        )
                                      }
                                      if (s.detail?.trim()) {
                                        return (
                                          <div key={i} className="mt-1 p-2 rounded bg-slate-50/80 text-slate-600 text-xs prose prose-sm max-w-none">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.detail}</ReactMarkdown>
                                          </div>
                                        )
                                      }
                                      return null
                                    })}
                                  </div>
                                )}
                                {hasPipeline && (
                                  <div>
                                    <p className="text-xs font-medium text-slate-500 mb-1.5">Steps</p>
                                    <div className="space-y-2">
                                      {pipelineSteps.map((s, i) => (
                                        <div key={i} className="text-xs">
                                          <p className="font-medium text-slate-600">{s.step}</p>
                                          {s.detail && (
                                            s.detailKind === 'sql'
                                              ? <pre className="mt-1 p-2 rounded bg-slate-100 text-slate-700 overflow-x-auto text-[11px] whitespace-pre-wrap break-all font-mono">{s.detail}</pre>
                                              : (
                                                  <div className="mt-1 p-2 rounded bg-slate-50/80 text-slate-600 text-xs prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-strong:font-semibold prose-strong:text-slate-700">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.detail}</ReactMarkdown>
                                                  </div>
                                                )
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })()}
                      {msg.data && Array.isArray(msg.data) && msg.data.length > 0 && getChartConfig(msg.data) && (
                        <CopilotDataChart data={msg.data} />
                      )}
                      {msg.text ? (
                        <div className="prose prose-sm max-w-none text-slate-700 prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-table:border-collapse prose-table:w-full prose-th:bg-slate-100 prose-td:border-b prose-td:border-slate-200 pt-1">
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ table: TableWithCopy }}>{msg.text}</ReactMarkdown>
                        </div>
                      ) : null}
                      {msg.data && Array.isArray(msg.data) && msg.data.length > 0 && (
                        <details className="group mt-3">
                          <summary className="text-xs font-medium text-slate-500 cursor-pointer list-none flex items-center gap-2 py-1 hover:text-slate-700">
                            <span className="inline-block w-3 h-3 rounded border border-slate-300 group-open:rotate-90 transition-transform" aria-hidden />
                            Raw data ({msg.data.length} row{msg.data.length !== 1 ? 's' : ''})
                          </summary>
                          <div className="relative mt-2 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50/50 max-h-60 overflow-y-auto">
                            <div className="absolute top-2 right-2 z-10">
                              <CopyButton
                                onCopy={async () => {
                                  const headers = Object.keys(msg.data[0])
                                  const rows = msg.data.slice(0, 25).map((row) => headers.map((k) => String(row[k] ?? '')).join('\t'))
                                  const text = [headers.join('\t'), ...rows].join('\n')
                                  await navigator.clipboard.writeText(text)
                                }}
                                title="Copy table"
                              />
                            </div>
                            <table className="min-w-full text-sm copilot-data-table">
                              <thead className="bg-slate-100 sticky top-0">
                                <tr>
                                  {Object.keys(msg.data[0]).map((k) => (
                                    <th key={k} className="px-3 py-2 text-left font-medium text-slate-700 whitespace-nowrap">{k}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {msg.data.slice(0, 25).map((row, i) => (
                                  <tr key={i} className="border-t border-slate-200 hover:bg-slate-50/80">
                                    {Object.values(row).map((v, j) => (
                                      <td key={j} className="px-3 py-2 text-slate-600">{String(v ?? '')}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            {msg.data.length > 25 && (
                              <p className="px-3 py-2 text-xs text-slate-500 border-t border-slate-200">Showing first 25 of {msg.data.length} rows</p>
                            )}
                          </div>
                        </details>
                      )}
                    </>
                  )}
                </div>
                {/* Copy outside user box; copy + like/dislike on next line for assistant */}
                <div className={`flex items-center gap-0.5 mt-1.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <CopyButton
                    onCopy={async () => {
                      const text = msg.role === 'user' ? msg.text : [msg.text, msg.error].filter(Boolean).join('\n')
                      if (text) await navigator.clipboard.writeText(text)
                    }}
                    title="Copy"
                  />
                  {msg.role === 'assistant' && !msg.error && (
                    <>
                      <button
                        type="button"
                        onClick={() => setMessageFeedback(idx, 'like')}
                        className={`p-1.5 rounded transition-colors ${feedbackByIndex[idx] === 'like' ? 'text-slate-800 bg-slate-200/80' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'}`}
                        title="Like"
                        aria-label="Like"
                        aria-pressed={feedbackByIndex[idx] === 'like'}
                      >
                        <ThumbsUp size={14} strokeWidth={feedbackByIndex[idx] === 'like' ? 2.5 : 2} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setMessageFeedback(idx, 'dislike')}
                        className={`p-1.5 rounded transition-colors ${feedbackByIndex[idx] === 'dislike' ? 'text-slate-800 bg-slate-200/80' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700'}`}
                        title="Dislike"
                        aria-label="Dislike"
                        aria-pressed={feedbackByIndex[idx] === 'dislike'}
                      >
                        <ThumbsDown size={14} strokeWidth={feedbackByIndex[idx] === 'dislike' ? 2.5 : 2} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start mb-6 animate-copilot-fade-in flex flex-col gap-3">
                <div className="rounded-2xl px-4 py-3 flex items-center gap-3 min-w-[200px] bg-transparent">
                  <span className="flex gap-1 shrink-0">
                    <span className="inline-block w-2 h-2 rounded-full bg-slate-500 animate-pulse" />
                    <span className="inline-block w-2 h-2 rounded-full bg-slate-500 animate-pulse" style={{ animationDelay: '150ms' }} />
                    <span className="inline-block w-2 h-2 rounded-full bg-slate-500 animate-pulse" style={{ animationDelay: '300ms' }} />
                  </span>
                  <span className="text-sm text-slate-600 font-medium">{streamStatus || 'Reasoning…'}</span>
                </div>
                {currentThinkingSteps.length > 0 && !streamThinkingMinimized && (() => {
                  const { reasoningSteps, pipelineSteps } = splitThinkingSteps(currentThinkingSteps)
                  return (
                    <div className="rounded-2xl px-4 py-3 max-w-full bg-transparent space-y-3">
                      {reasoningSteps.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-600 mb-2">
                            {thinkingElapsedSec != null ? `Reasoning (${thinkingElapsedSec}s)` : 'Reasoning'}
                          </p>
                          <div className="pl-2 border-l-2 border-slate-200/60">
                            {reasoningSteps.map((s, i) => {
                              const items = parseReasoningToList(s.detail)
                              if (items.length > 0) {
                                return (
                                  <ul key={i} className="text-xs text-slate-600 space-y-1 list-disc list-inside mt-1">
                                    {items.map((line, j) => (
                                      <li key={j} className="leading-relaxed">
                                        <span className="prose prose-sm max-w-none prose-p:my-0 prose-ul:my-0 prose-li:my-0">
                                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{line}</ReactMarkdown>
                                        </span>
                                      </li>
                                    ))}
                                  </ul>
                                )
                              }
                              return (
                                <div key={i} className="mt-1 text-xs text-slate-600">
                                  {s.detail?.trim() ? (
                                    <div className="rounded bg-slate-50/80 p-2">
                                      <span className="inline-block animate-pulse">▌</span>
                                      <span className="prose prose-sm max-w-none prose-p:my-0">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.detail}</ReactMarkdown>
                                      </span>
                                    </div>
                                  ) : (
                                    <span className="text-slate-400 italic">Thinking…</span>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                      {pipelineSteps.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 mb-1.5">Steps</p>
                          <div className="pl-2 space-y-2 border-l-2 border-slate-200/60">
                            {pipelineSteps.map((s, i) => (
                              <div key={i} className="text-xs">
                                <p className="font-medium text-slate-600">{s.step}</p>
                                {s.detail && (
                                  s.detailKind === 'sql'
                                    ? <pre className="mt-1 p-2 rounded bg-slate-100 text-slate-700 overflow-x-auto text-[11px] whitespace-pre-wrap break-all font-mono">{s.detail}</pre>
                                    : (
                                        <div className="mt-1 p-2 rounded bg-slate-50/80 text-slate-600 text-xs prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-strong:font-semibold prose-strong:text-slate-700">
                                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.detail}</ReactMarkdown>
                                        </div>
                                      )
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {error && (
          <div className="flex-shrink-0 px-6 py-2 bg-red-50/90 border-t border-red-100 text-red-700 text-sm flex items-center justify-between gap-3">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => {
                setError(null)
                const lastUser = [...messages].reverse().find((m) => m.role === 'user')
                if (lastUser?.text) {
                  setInput(lastUser.text)
                  inputRef.current?.focus()
                }
              }}
              className="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
            >
              Retry
            </button>
          </div>
        )}

        <div className="flex-shrink-0 px-6 py-4 flex justify-center">
          <div className="w-full max-w-4xl mx-auto">
            <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm transition-all duration-200 focus-within:ring-2 focus-within:ring-slate-300/50 focus-within:border-slate-400 px-3 py-2">
              <div className="flex items-center gap-2">
              
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
                  placeholder="Describe what you want to analyze..."
                  className="flex-1 min-w-0 py-3 text-sm placeholder-slate-400 bg-transparent focus:outline-none"
                  disabled={loading}
                  aria-label="Message"
                />
                <button
                  type="button"
                  onClick={send}
                  disabled={loading || !input.trim()}
                  className="w-10 h-10 rounded-full bg-slate-800 text-white flex items-center justify-center transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
                  aria-label="Send"
                >
                  {loading ? <span className="text-sm">…</span> : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>
                  )}
                </button>
              </div>
              
            </div>
            <p className="mt-2 text-[10px] text-slate-400 text-center">
              AI COPILOT CAN MAKE MISTAKES. VERIFY IMPORTANT INFO.
            </p>
          </div>
        </div>
      </div>

      {/* Your Chats modal: search, select, delete */}
      {chatsModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-copilot-fade-in"
          onClick={() => setChatsModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="chats-modal-title"
        >
          <div
            className="bg-white rounded-2xl shadow-lg max-w-md w-full max-h-[80vh] flex flex-col border border-slate-200/80"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
              <h2 id="chats-modal-title" className="text-lg font-semibold text-slate-800">
                Your chats
              </h2>
              <button
                type="button"
                onClick={() => setChatsModalOpen(false)}
                className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
                aria-label="Close"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
                  <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
            <div className="px-4 py-3 border-b border-slate-100">
              <input
                type="text"
                value={modalSearchQuery}
                onChange={(e) => setModalSearchQuery(e.target.value)}
                placeholder="Search chats"
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-slate-500"
                aria-label="Search chats"
              />
            </div>
            <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-100 bg-slate-50/50">
              <button
                type="button"
                onClick={selectAllSessions}
                className="text-xs font-medium text-slate-600 hover:text-slate-800"
              >
                Select all
              </button>
              <span className="text-slate-300">|</span>
              <button
                type="button"
                onClick={deselectAllSessions}
                className="text-xs font-medium text-slate-600 hover:text-slate-800"
              >
                Deselect all
              </button>
              {selectedSessionIds.size > 0 && (
                <span className="ml-auto text-xs text-slate-500">
                  {selectedSessionIds.size} selected
                </span>
              )}
            </div>
            <ul className="flex-1 min-h-0 overflow-y-auto px-2 py-2">
              {modalFilteredSessions.length === 0 ? (
                <li className="px-3 py-4 text-sm text-slate-500 italic">No chats match</li>
              ) : (
                modalFilteredSessions.map((s) => (
                  <li key={s.session_id}>
                    <label className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-50 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={selectedSessionIds.has(s.session_id)}
                        onChange={() => toggleSessionSelection(s.session_id)}
                        className="w-4 h-4 rounded border-slate-300 text-slate-700 focus:ring-slate-500"
                      />
                      <span className="flex-1 min-w-0 truncate text-sm text-slate-700 group-hover:text-slate-900">
                        {s.title || 'New chat'}
                      </span>
                      <span className="text-[10px] text-slate-400 shrink-0">{formatSessionDate(s.updated_at)}</span>
                    </label>
                  </li>
                ))
              )}
            </ul>
            <div className="flex items-center justify-end gap-2 px-4 py-4 border-t border-slate-200 bg-slate-50/50 rounded-b-2xl">
              <button
                type="button"
                onClick={() => setChatsModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={deleteSelectedSessions}
                disabled={selectedSessionIds.size === 0 || deleteInProgress}
                className="px-4 py-2 text-sm font-medium text-white bg-red-500 hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                {deleteInProgress ? 'Deleting…' : `Delete${selectedSessionIds.size > 0 ? ` (${selectedSessionIds.size})` : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
