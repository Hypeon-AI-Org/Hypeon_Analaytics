import React, { useState, useRef, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { copilotChat, copilotChatHistory, fetchCopilotSessions } from './api'
import DynamicDashboardRenderer from './components/DynamicDashboardRenderer'
import DashboardRendererErrorBoundary from './components/DashboardRendererErrorBoundary'

const COPILOT_SESSION_KEY = 'hypeon_copilot_session_id'

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

export default function CopilotChat() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialSessionId = location.state?.sessionId || null
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(initialSessionId || sessionStorage.getItem(COPILOT_SESSION_KEY))
  const sessionIdRef = useRef(initialSessionId || sessionStorage.getItem(COPILOT_SESSION_KEY))
  const messagesEndRef = useRef(null)
  const listEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  const loadSessions = () => {
    fetchCopilotSessions()
      .then((r) => setSessions(r.sessions || []))
      .catch(() => setSessions([]))
  }

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSession = (sid) => {
    sessionIdRef.current = sid
    setActiveSessionId(sid)
    sessionStorage.setItem(COPILOT_SESSION_KEY, sid)
    setError(null)
    setMessages([])
    navigate('/copilot', { state: { sessionId: sid }, replace: true })
    copilotChatHistory(sid)
      .then(({ messages: history }) => {
        setMessages(
          (history || []).map((m) => ({
            role: m.role,
            text: m.content || '',
            layout: m.layout ?? null,
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
          if (history?.length) setMessages(history.map((m) => ({ role: m.role, text: m.content || '', layout: m.layout ?? null })))
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
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)
    try {
      const res = await copilotChat({
        message: text,
        session_id: sessionIdRef.current || undefined,
      })
      if (res.session_id) {
        sessionIdRef.current = res.session_id
        setActiveSessionId(res.session_id)
        sessionStorage.setItem(COPILOT_SESSION_KEY, res.session_id)
        loadSessions()
      }
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: res.text || '', layout: res.layout || null },
      ])
    } catch (err) {
      setError(err.message || 'Something went wrong')
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: '', error: err.message },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-0px)] bg-gradient-app">
      {/* Left sidebar: session list (ChatGPT/Claude style) */}
      <aside className="w-64 flex-shrink-0 flex flex-col border-r border-pink-100/60 bg-white/50 backdrop-blur-md">
        <div className="p-4 border-b border-pink-100/60">
          <button
            type="button"
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 rounded-xl py-2.5 px-3 text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 transition-colors border border-brand-500/50"
          >
            <span aria-hidden>+</span>
            New chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <p className="px-2 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Recent</p>
          {sessions.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-400">No chats yet</p>
          ) : (
            <ul className="space-y-0.5">
              {sessions.map((s) => (
                <li key={s.session_id}>
                  <button
                    type="button"
                    onClick={() => loadSession(s.session_id)}
                    className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors truncate block ${
                      activeSessionId === s.session_id
                        ? 'bg-brand-100 text-brand-800 border border-brand-200'
                        : 'text-slate-700 hover:bg-pink-50/80'
                    }`}
                  >
                    <span className="block truncate">{s.title || 'New chat'}</span>
                    <span className="text-xs text-slate-400">{formatSessionDate(s.updated_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div ref={listEndRef} />
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-shrink-0 border-b border-pink-100/60 bg-white/70 backdrop-blur-md px-6 py-3">
          <h2 className="text-base font-semibold text-slate-800">Copilot</h2>
          <p className="text-xs text-slate-500 mt-0.5">Ask about performance, campaigns, funnel, and actions</p>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="max-w-3xl mx-auto">
            {messages.length === 0 && !loading && (
              <div className="glass-card p-8 text-center">
                <p className="text-sm font-medium text-slate-700">Start a conversation</p>
                <p className="mt-2 text-sm text-slate-500">Try: &quot;Summarize my top campaigns&quot; or &quot;Show me a table of spend by campaign&quot;</p>
                <div className="mt-6 flex flex-wrap gap-2 justify-center">
                  {['How am I doing overall?', 'Top campaigns by ROAS', 'Funnel drop-off', 'Recommended actions'].map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => setInput(q)}
                      className="rounded-lg border border-pink-200 bg-white/80 px-3 py-2 text-xs text-slate-600 hover:bg-brand-50 hover:border-brand-200 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} mb-6`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-brand-600 text-white'
                      : 'glass-card border border-pink-100/60'
                  }`}
                >
                  {msg.error ? (
                    <p className="text-sm text-red-600">{msg.error}</p>
                  ) : msg.role === 'user' ? (
                    <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                  ) : (
                    <>
                      {msg.text ? (
                        <div className="prose prose-sm max-w-none text-slate-700 prose-p:my-1 prose-ul:my-1 prose-li:my-0">
                          <ReactMarkdown>{msg.text}</ReactMarkdown>
                        </div>
                      ) : null}
                      {msg.layout?.widgets?.length > 0 && (
                        <div className="mt-3 rounded-xl border border-pink-100/60 bg-white/90 p-3">
                          <DashboardRendererErrorBoundary>
                            <DynamicDashboardRenderer layout={msg.layout} />
                          </DashboardRendererErrorBoundary>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start mb-6">
                <div className="glass-card rounded-2xl px-4 py-3 flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
                  <span className="inline-block w-2 h-2 rounded-full bg-brand-500 animate-pulse" style={{ animationDelay: '150ms' }} />
                  <span className="inline-block w-2 h-2 rounded-full bg-brand-500 animate-pulse" style={{ animationDelay: '300ms' }} />
                  <span className="text-sm text-slate-500 ml-1">Thinking…</span>
                </div>
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

        <div className="flex-shrink-0 border-t border-pink-100/60 bg-white/70 backdrop-blur-md p-4">
          <div className="max-w-3xl mx-auto flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
              placeholder="Message Copilot…"
              className="flex-1 rounded-xl border border-pink-200/80 bg-white/90 px-4 py-3 text-sm placeholder-slate-400 focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500"
              disabled={loading}
              aria-label="Message Copilot"
            />
            <button
              type="button"
              onClick={send}
              disabled={loading || !input.trim()}
              className="rounded-xl bg-brand-600 text-white px-5 py-3 text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? '…' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
