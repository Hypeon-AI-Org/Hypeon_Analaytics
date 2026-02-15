import { useCallback, useEffect, useState } from 'react'
import { api, CopilotMessageItem, CopilotSessionItem } from '../api'

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

export default function Copilot() {
  const [context, setContext] = useState<Awaited<ReturnType<typeof api.copilotContext>> | null>(null)
  const [sessions, setSessions] = useState<CopilotSessionItem[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<CopilotMessageItem[]>([])
  const [question, setQuestion] = useState('')
  const [streamingContent, setStreamingContent] = useState<string | null>(null)
  const [streamingSources, setStreamingSources] = useState<string[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSessions = useCallback(() => {
    api.copilotSessions().then((r) => setSessions(r.sessions)).catch(() => setSessions([]))
  }, [])

  const loadMessages = useCallback((sessionId: number) => {
    api.copilotSessionMessages(sessionId).then((r) => setMessages(r.messages)).catch(() => setMessages([]))
  }, [])

  useEffect(() => {
    api.copilotContext(90).then(setContext).catch(() => setContext(null))
    loadSessions()
  }, [loadSessions])

  useEffect(() => {
    if (currentSessionId != null) loadMessages(currentSessionId)
    else setMessages([])
  }, [currentSessionId, loadMessages])

  const startNewChat = () => {
    setCurrentSessionId(null)
    setMessages([])
    setQuestion('')
    setError(null)
    api
      .copilotCreateSession()
      .then((s) => {
        setSessions((prev) => [s, ...prev])
        setCurrentSessionId(s.id)
      })
      .catch((e: Error) => setError(e?.message ? `Failed to create session: ${e.message}` : 'Failed to create session'))
  }

  const selectSession = (s: CopilotSessionItem) => {
    setCurrentSessionId(s.id)
    setError(null)
  }

  const ask = async (q: string) => {
    const text = (q || question).trim()
    if (!text) return
    setLoading(true)
    setError(null)
    setStreamingContent('')
    setStreamingSources(null)

    let sessionId: number | undefined = currentSessionId ?? undefined
    if (sessionId == null) {
      try {
        const s = await api.copilotCreateSession()
        setSessions((prev) => [s, ...prev])
        setCurrentSessionId(s.id)
        sessionId = s.id
      } catch {
        setError((e as Error)?.message ? `Create session: ${(e as Error).message}` : 'Failed to create session')
        setLoading(false)
        return
      }
    }

    api
      .copilotAskStream(
        text,
        sessionId,
        {
          onData: (delta) => setStreamingContent((prev) => (prev ?? '') + delta),
          onDone: (answer, sources) => {
            setStreamingContent(null)
            setStreamingSources(sources)
            setQuestion('')
            loadSessions()
            api.copilotSessionMessages(sessionId!).then((r) => setMessages(r.messages))
          },
          onError: (err) => setError(err),
        }
      )
      .finally(() => setLoading(false))
  }

  return (
    <div className="min-h-screen flex">
      {/* Sidebar: sessions */}
      <aside className="w-56 shrink-0 border-r border-surface-200 bg-surface-50 flex flex-col">
        <div className="p-3 border-b border-surface-200">
          <button
            type="button"
            onClick={startNewChat}
            className="w-full rounded-lg bg-brand-600 text-white py-2 px-3 text-sm font-medium hover:bg-brand-700"
          >
            New chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          <p className="text-xs font-medium text-surface-500 uppercase tracking-wide px-2 mb-2">Past sessions</p>
          {sessions.length === 0 && (
            <p className="text-xs text-surface-400 px-2">No sessions yet. Start a new chat.</p>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => selectSession(s)}
              className={`w-full text-left rounded-lg px-3 py-2 text-sm mb-1 truncate ${
                currentSessionId === s.id ? 'bg-brand-100 text-brand-800 border border-brand-200' : 'text-surface-700 hover:bg-surface-100'
              }`}
              title={s.title ?? `Session ${s.id}`}
            >
              {s.title ?? `Chat ${s.id}`}
            </button>
          ))}
        </div>
      </aside>

      {/* Main: context card + input + messages */}
      <main className="flex-1 flex flex-col max-w-2xl mx-auto px-4 py-6 w-full">
        <div className="text-center mb-6">
          <h1 className="font-display text-2xl font-semibold text-surface-900 mb-1">Copilot</h1>
          <p className="text-surface-500 text-sm">
            Ask like a founder. Answers use your dashboard data and sound like an experienced marketing specialist.
          </p>
          {context && (
            <div className="mt-4 p-4 bg-white rounded-xl border border-surface-200 text-left">
              <p className="text-xs font-medium text-surface-500 uppercase tracking-wide mb-2">Data in scope</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div><span className="text-surface-500">Period</span><br />{context.start_date} → {context.end_date}</div>
                <div><span className="text-surface-500">Spend</span><br />${context.total_spend?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                <div><span className="text-surface-500">Revenue</span><br />${context.total_revenue?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                <div><span className="text-surface-500">ROAS</span><br />{context.roas_overall ?? '—'}</div>
              </div>
              <p className="text-xs text-surface-400 mt-2">Channels: {context.channels?.length ? context.channels.join(', ') : 'none'} · {context.decisions_total ?? 0} decisions</p>
            </div>
          )}
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm">{error}</div>
        )}

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && ask(question)}
            placeholder="e.g. How are we doing? Where should we spend?"
            className="flex-1 rounded-xl border border-surface-200 px-4 py-3 text-surface-900 placeholder:text-surface-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            type="button"
            onClick={() => ask(question)}
            disabled={loading || !question.trim()}
            className="rounded-xl bg-brand-600 text-white px-5 py-3 font-medium hover:bg-brand-700 disabled:opacity-50 disabled:pointer-events-none"
          >
            {loading ? '…' : 'Ask'}
          </button>
        </div>

        <p className="text-xs text-surface-500 mb-2">Suggested</p>
        <div className="flex flex-wrap gap-2 mb-6">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => ask(q)}
              disabled={loading}
              className="rounded-lg bg-white border border-surface-200 px-3 py-2 text-sm text-surface-700 hover:bg-surface-50 hover:border-surface-300 disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>

        <div className="flex-1 space-y-4">
          {messages.length === 0 && !streamingContent && !loading && (
            <div className="text-center py-12 text-surface-500 text-sm">
              Start a new chat or pick a past session. Ask things like &ldquo;How are we doing?&rdquo; or &ldquo;Which channel performs best?&rdquo;
            </div>
          )}
          {messages.map((m, i) => (
            <div key={m.role === 'user' ? `u-${i}` : `a-${i}`} className="space-y-1">
              <p className="text-xs font-medium text-surface-500">{m.role === 'user' ? 'You' : 'Copilot'}</p>
              <div
                className={
                  m.role === 'user'
                    ? 'text-sm text-surface-800'
                    : 'pl-4 border-l-2 border-brand-200 bg-white rounded-r-xl p-4 text-sm text-surface-700'
                }
              >
                {m.content}
              </div>
            </div>
          ))}
          {streamingContent != null && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-surface-500">Copilot</p>
              <div className="pl-4 border-l-2 border-brand-200 bg-white rounded-r-xl p-4 text-sm text-surface-700">
                {streamingContent}
                <span className="animate-pulse">▌</span>
              </div>
            </div>
          )}
          {streamingSources != null && streamingSources.length > 0 && (
            <p className="text-xs text-surface-400">Based on: {streamingSources.join(', ')}</p>
          )}
        </div>
      </main>
    </div>
  )
}
