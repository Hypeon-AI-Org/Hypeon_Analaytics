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

function SphereLogo() {
  return (
    <>
      <style>
        {`
          @keyframes rotate360 {
  0% { transform: rotateX(0deg) rotateY(0deg) rotateZ(0deg); }
  50% { transform: rotateX(180deg) rotateY(180deg) rotateZ(30deg); }
  100% { transform: rotateX(360deg) rotateY(360deg) rotateZ(0deg); }
}

          .sphere-container {
            perspective: 1200px;
          }

          .sphere {
            position: relative;
            width: 64px;
            height: 64px;
            transform-style: preserve-3d;
            animation: rotate360 14s linear infinite;
          }

         .sphere-layer {
  position: absolute;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: radial-gradient(
    circle at 35% 35%,
    #ffffff 0%,
    #ddd6fe 20%,
    #a78bfa 40%,
    #7c3aed 65%,
    #4c1d95 100%
  );
  box-shadow:
    inset -14px -16px 28px rgba(0,0,0,0.45),
    inset 12px 12px 22px rgba(255,255,255,0.6),
    0 10px 30px rgba(124,58,237,0.4);
}

          .layer-1 { transform: rotateY(0deg); }
          .layer-2 { transform: rotateY(90deg); }
          .layer-3 { transform: rotateX(90deg); }

          .glow {
            position: absolute;
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(139,92,246,0.4), transparent 70%);
            filter: blur(32px);
          }
            
        `}
        
      </style>

      <div className="sphere-container flex items-center justify-center">
        <div className="relative flex items-center justify-center">
          <div className="glow" />
          <div className="sphere">
            <div className="sphere-layer layer-1" />
            <div className="sphere-layer layer-2" />
            <div className="sphere-layer layer-3" />
          </div>
        </div>
      </div>
    </>
  )
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

  const suggestedPrompts = [
    { question: 'Why did revenue drop yesterday?', action: 'Analyze performance →' },
    { question: 'Which campaign is performing best?', action: 'View ROAS details →' },
    { question: 'Predict sales for next month', action: 'Run predictive model →' },
  ]

  return (
    <div className="flex h-full min-h-0 overflow-hidden bg-slate-50 animate-copilot-fade-in">
      {/* Left sidebar: dark blue/charcoal theme (match reference) */}
      <aside className="w-52 flex-shrink-0 flex flex-col min-h-0 bg-gradient-to-b from-slate-900 to-slate-800 text-white border-r border-slate-700/50 animate-copilot-slide-in-left">
        <div className="p-3 border-b border-white/10">
          <div className="flex items-center gap-1.5 mb-4=">
            <span className="text-sm font-bold text-white">Hypeon Analytics</span>
          </div>
      
          <button
            type="button"
            onClick={startNewChat}
            className="w-full mt-2 flex items-center justify-center gap-1.5 rounded-lg py-2 px-3 text-xs font-semibold bg-blue-600 text-white hover:bg-blue-500 transition-all"
          >
            <span aria-hidden>+</span>
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-1.5 scrollbar-sidebar">
          <p className="px-2 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">RECENT CONVERSATIONS</p>
          {sessions.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-slate-500 italic">No recent chats</p>
          ) : (
            <ul className="space-y-0.5">
              {sessions.map((s) => (
                <li key={s.session_id}>
                  <button
                    type="button"
                    onClick={() => loadSession(s.session_id)}
                    className={`w-full text-left px-2 py-2 rounded-md text-xs transition-colors flex items-center gap-1.5 ${
                      activeSessionId === s.session_id
                        ? 'bg-blue-900/70 text-white font-bold'
                        : 'text-slate-400 hover:bg-white/10 hover:text-white font-normal'
                    }`}
                  >
                    <span className={`shrink-0 ${activeSessionId === s.session_id ? 'text-white' : 'text-slate-400'}`} aria-hidden>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    </span>
                    <span className="min-w-0 flex-1 truncate">{s.title || 'New chat'}</span>
                    <span className={`text-[10px] shrink-0 ${activeSessionId === s.session_id ? 'text-slate-300' : 'text-slate-500'}`}>{formatSessionDate(s.updated_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div ref={listEndRef} />
        <div className="p-3 border-t border-white/10">
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="w-full flex items-center gap-2 rounded-lg px-2 py-3 text-xs font-semibold text-slate-200 hover:bg-white/10 hover:text-white transition-colors"
          >
            <span className="text-slate-400 shrink-0" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                <path d="M3 3v18h18" />
                <path d="M18 17V9" />
                <path d="M13 17V5" />
                <path d="M8 17v-3" />
              </svg>
            </span>
            Back to Analytics
          </button>
        </div>
        <div className="p-3 border-t border-white/10 flex items-center gap-3">
          <div className="relative shrink-0">
            <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center text-white text-xs font-semibold">JD</div>
            <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-400 border-2 border-[#141b21]" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-white truncate">John Doe</p>
            <p className="text-[10px] text-slate-400 uppercase tracking-wider mt-0.5">ENTERPRISE PLAN</p>
          </div>
          <button type="button" className="text-slate-400 hover:text-white p-1 rounded" aria-label="Settings">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          </button>
        </div>
      </aside>

      {/* Main chat area: only this column scrolls (GPT-like) */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden bg-white font-copilot animate-copilot-main-in">
        <div className="flex-1 min-h-0 overflow-y-auto relative px-6 pt-8 pb-4">
          <div className="w-full max-w-2xl mx-auto px-4 sm:px-6">
            {messages.length === 0 && !loading && (
               <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6 font-copilot animate-copilot-fade-in">
                <div className="mb-6 shrink-0" aria-hidden>
                  <SphereLogo />
                </div>
                <h3 className="text-1xl sm:text-2xl font-bold text-slate-800 tracking-tight">Ask anything about your analytics</h3>
                <p className="mt-3 text-slate-500 text-base max-w-md mx-auto font-normal">
                  Get instant AI-powered insights, predictions, and automated reporting from your enterprise data.
                </p>
                {/* Same card structure: 2 on top row, 1 below left with space to right */}
                <div className="mt-8 w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-3 justify-items-center sm:justify-items-stretch">
                {suggestedPrompts.map(({ question, action }, promptIdx) => (
    <button
      key={question}
      type="button"
      onClick={() => setInput(question)}
      style={{ animationDelay: `${promptIdx * 50}ms` }}
      className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-left 
                 hover:bg-slate-50 hover:border-slate-300 
                 transition-all duration-200 
                 shadow-sm hover:shadow-md hover:-translate-y-0.5
                 flex items-center gap-2 group font-copilot animate-copilot-slide-up opacity-0"
    >
      <span
        className="w-7 h-7 rounded-md flex items-center justify-center 
                   text-blue-600 bg-blue-50 group-hover:bg-blue-100 
                   transition-colors shrink-0"
        aria-hidden
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="w-3.5 h-3.5"
        >
          <path d="M2 18 L6 14 L10 18 L14 10 L18 14 L22 10" />
        </svg>
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-slate-800 truncate">
          {question}
        </p>
        <p className="text-[11px] text-slate-500 mt-0.5 font-normal group-hover:underline">
          {action}
        </p>
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
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} mb-6 ${msg.role === 'user' ? 'animate-copilot-slide-in-right opacity-0' : 'animate-copilot-slide-in-left opacity-0'}`}
              >
                <div
                  className={`max-w-[85%] min-w-0 rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'glass-card border border-slate-200'
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
                        <div className="mt-3 rounded-xl border border-slate-200 bg-white/90 p-3">
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
              <div className="flex justify-start mb-6 animate-copilot-fade-in">
                <div className="glass-card rounded-2xl px-4 py-3 flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                  <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse" style={{ animationDelay: '150ms' }} />
                  <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-pulse" style={{ animationDelay: '300ms' }} />
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

        <div className="flex-shrink-0 bg-white px-6 py-4 flex justify-center">
          <div className="w-full max-w-2xl mx-auto">
            {/* Input bar aligned with chat content */}
            <div className="flex items-center rounded-2xl border border-slate-200 bg-slate-50/80 shadow-sm transition-all duration-300 focus-within:ring-2 focus-within:ring-blue-500/30 focus-within:border-blue-400 focus-within:bg-white px-2">
  
  <input
    ref={inputRef}
    type="text"
    value={input}
    onChange={(e) => setInput(e.target.value)}
    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
    placeholder="What should I do today?"
    className="flex-1 min-w-0 px-4 py-4 text-sm placeholder-slate-400 bg-transparent focus:outline-none"
    disabled={loading}
    aria-label="Message Copilot"
  />

  

  {/* Send Button */}
  <button
  type="button"
  onClick={send}
  disabled={loading || !input.trim()}
  className="
    ml-2
    w-11 h-11
    rounded-full
    bg-blue-600
    text-white
    flex items-center justify-center
    transition-all duration-200
    hover:bg-blue-500
    hover:scale-105
    active:scale-95
    disabled:opacity-40
    disabled:cursor-not-allowed
    shadow-md hover:shadow-lg
  "
  aria-label="Send"
>
  {loading ? (
    <span className="text-sm">…</span>
  ) : (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="w-5 h-5"
    >
      {/* Minimal upward arrow like your image */}
      <path d="M12 19V5" />
      <path d="M5 12l7-7 7 7" />
    </svg>
  )}
</button>

</div>
            <p className="mt-2 text-[10px] text-slate-400 text-center">
              AI COPILOT CAN MAKE MISTAKES. VERIFY IMPORTANT INFO.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
