import { useCallback, useEffect, useRef, useState } from 'react'
import { api, CopilotMessageItem, CopilotSessionItem } from '../api'
import CopilotMessageContent from '../components/CopilotMessageContent'

const SUGGESTED_QUESTIONS = [
  'How are we doing?',
  'Spend by channel',
  'Revenue by channel',
  'Which channel performs best?',
  'What decisions do we have?',
  'How do I optimize budget?',
  'Is our attribution stable?',
  'Should we scale up?',
]

function formatSessionTitle(title: string | null | undefined, id: number): string {
  if (title && title.trim()) return title.length > 36 ? title.slice(0, 36) + '…' : title
  return `Chat ${id}`
}

function formatSessionDate(d: string): string {
  const date = new Date(d)
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  if (sameDay) return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function Copilot() {
  const [context, setContext] = useState<Awaited<ReturnType<typeof api.copilotContext>> | null>(null)
  const [sessions, setSessions] = useState<CopilotSessionItem[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<CopilotMessageItem[]>([])
  const [input, setInput] = useState('')
  const [streamingContent, setStreamingContent] = useState<string | null>(null)
  const [streamingSources, setStreamingSources] = useState<string[] | null>(null)
  const [streamingModelVersions, setStreamingModelVersions] = useState<{
    mta_version?: string
    mmm_version?: string
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const loadSessions = useCallback(() => {
    api.copilotSessions().then((r) => setSessions(r.sessions)).catch(() => setSessions([]))
  }, [])

  const loadMessages = useCallback((sessionId: number) => {
    api
      .copilotSessionMessages(sessionId)
      .then((r) => setMessages(r.messages))
      .catch(() => setMessages([]))
  }, [])

  useEffect(() => {
    // Use range that includes sample data (from 2025-01-01); backend falls back to longer lookback if empty
    const end = new Date().toISOString().slice(0, 10)
    api
      .copilotContext(90, { start_date: '2025-01-01', end_date: end })
      .then(setContext)
      .catch(() => setContext(null))
    loadSessions()
  }, [loadSessions])

  useEffect(() => {
    if (currentSessionId != null) loadMessages(currentSessionId)
    else setMessages([])
  }, [currentSessionId, loadMessages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const startNewChat = () => {
    setCurrentSessionId(null)
    setMessages([])
    setInput('')
    setStreamingContent(null)
    setStreamingSources(null)
    setStreamingModelVersions(null)
    setError(null)
    api
      .copilotCreateSession()
      .then((s) => {
        setSessions((prev) => [s, ...prev])
        setCurrentSessionId(s.id)
      })
      .catch((e: Error) =>
        setError(e?.message ? `Failed to create session: ${e.message}` : 'Failed to create session')
      )
  }

  const selectSession = (s: CopilotSessionItem) => {
    setCurrentSessionId(s.id)
    setError(null)
  }

  const ask = async (q: string) => {
    const text = (q || input).trim()
    if (!text) return
    setLoading(true)
    setError(null)
    setStreamingContent('')
    setStreamingSources(null)
    setStreamingModelVersions(null)

    let sessionId: number | undefined = currentSessionId ?? undefined
    if (sessionId == null) {
      try {
        const s = await api.copilotCreateSession()
        setSessions((prev) => [s, ...prev])
        setCurrentSessionId(s.id)
        sessionId = s.id
      } catch {
        setError('Failed to create session')
        setLoading(false)
        return
      }
    }

    setInput('')
    setMessages((prev) => [...prev, { id: -1, role: 'user', content: text, created_at: new Date().toISOString() }])

    const dateRange =
      context?.start_date && context?.end_date
        ? { start_date: context.start_date, end_date: context.end_date }
        : undefined
    api
      .copilotAskStream(text, sessionId, {
        onData: (delta) => setStreamingContent((prev) => (prev ?? '') + delta),
        onDone: (answer, sources, modelVersions) => {
          setStreamingContent(null)
          setStreamingSources(sources ?? null)
          setStreamingModelVersions(modelVersions ?? null)
          loadSessions()
          api.copilotSessionMessages(sessionId!).then((r) => setMessages(r.messages))
        },
        onError: (err) => setError(err),
      }, dateRange)
      .finally(() => setLoading(false))
  }

  const isEmpty = messages.length === 0 && !streamingContent && !loading
  const showSuggestions = isEmpty

  return (
    <div className="flex h-full min-h-0 bg-surface-50">
      {/* Sidebar: sessions (ChatGPT-style) */}
      <aside className="w-64 shrink-0 flex flex-col border-r border-surface-200 bg-white">
        <div className="p-3 border-b border-surface-200">
          <button
            type="button"
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-surface-900 text-white py-2.5 px-3 text-sm font-medium hover:bg-surface-800 transition-colors"
          >
            <span aria-hidden>+</span>
            New chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <p className="text-xs font-medium text-surface-400 uppercase tracking-wide px-2 mb-2">
            Recent
          </p>
          {sessions.length === 0 && (
            <p className="text-xs text-surface-400 px-2">No chats yet.</p>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => selectSession(s)}
              className={`w-full text-left rounded-lg px-3 py-2.5 text-sm mb-0.5 flex flex-col gap-0.5 ${
                currentSessionId === s.id
                  ? 'bg-surface-100 text-surface-900 font-medium'
                  : 'text-surface-600 hover:bg-surface-50'
              }`}
              title={s.title ?? `Session ${s.id}`}
            >
              <span className="truncate">{formatSessionTitle(s.title, s.id)}</span>
              <span className="text-xs text-surface-400">{formatSessionDate(s.created_at)}</span>
            </button>
          ))}
        </div>
        {context && (
          <div className="p-3 border-t border-surface-200 bg-surface-50/50">
            <p className="text-xs font-medium text-surface-500 mb-1">Data in scope</p>
            <p className="text-xs text-surface-500">
              {context.start_date} → {context.end_date} · ${context.total_spend?.toLocaleString(undefined, { maximumFractionDigits: 0 })} spend
            </p>
          </div>
        )}
      </aside>

      {/* Main: messages + input */}
      <main className="flex-1 flex flex-col min-w-0">
        {error && (
          <div className="mx-4 mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6">
            {showSuggestions && (
              <div className="text-center py-12">
                <h2 className="text-xl font-semibold text-surface-800 mb-1">HypeOn Copilot</h2>
                <p className="text-surface-500 text-sm mb-8">
                  Ask about your dashboard in plain language. Data is fetched when you ask.
                </p>
                <p className="text-xs font-medium text-surface-400 uppercase tracking-wide mb-3">
                  Try asking
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => ask(q)}
                      disabled={loading}
                      className="rounded-full border border-surface-200 bg-white px-4 py-2 text-sm text-surface-700 hover:bg-surface-50 hover:border-surface-300 transition-colors disabled:opacity-50"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!showSuggestions && (
              <div className="space-y-6">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                        m.role === 'user'
                          ? 'bg-brand-600 text-white'
                          : 'bg-white border border-surface-200 shadow-sm'
                      }`}
                    >
                      {m.role === 'user' ? (
                        <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                      ) : (
                        <div className="text-sm">
                          <CopilotMessageContent content={m.content} />
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {streamingContent != null && (
                  <div className="flex justify-start">
                    <div className="max-w-[85%] rounded-2xl px-4 py-3 bg-white border border-surface-200 shadow-sm">
                      <div className="text-sm">
                        <CopilotMessageContent content={streamingContent} />
                        <span className="animate-pulse">▌</span>
                      </div>
                    </div>
                  </div>
                )}

                {streamingSources != null && streamingSources.length > 0 && (
                  <div className="flex justify-start">
                    <div className="max-w-[85%] text-xs text-surface-500 px-2">
                      Based on: {streamingSources.join(', ')}
                      {streamingModelVersions &&
                        (streamingModelVersions.mta_version || streamingModelVersions.mmm_version) && (
                          <span className="ml-2">
                            · MTA {streamingModelVersions.mta_version ?? '—'}, MMM{' '}
                            {streamingModelVersions.mmm_version ?? '—'}
                          </span>
                        )}
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        {/* Input area (fixed at bottom) */}
        <div className="border-t border-surface-200 bg-white p-4">
          <div className="max-w-3xl mx-auto flex gap-3 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  ask(input)
                }
              }}
              placeholder="Ask anything about your dashboard..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-surface-200 px-4 py-3 text-surface-900 placeholder:text-surface-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent min-h-[48px] max-h-32"
              disabled={loading}
            />
            <button
              type="button"
              onClick={() => ask(input)}
              disabled={loading || !input.trim()}
              className="shrink-0 rounded-xl bg-brand-600 text-white px-5 py-3 font-medium hover:bg-brand-700 disabled:opacity-50 disabled:pointer-events-none min-h-[48px]"
            >
              {loading ? '…' : 'Send'}
            </button>
          </div>
          <p className="text-xs text-surface-400 text-center mt-2 max-w-3xl mx-auto">
            Copilot uses your dashboard data and session context to answer follow-up questions.
          </p>
        </div>
      </main>
    </div>
  )
}
