import React, { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import { fetchInsights, copilotStream } from './api'

export default function CopilotChat() {
  const [insights, setInsights] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [messages, setMessages] = useState([])
  const [streamPhase, setStreamPhase] = useState(null)
  const [streamText, setStreamText] = useState('')
  const [loadingInsights, setLoadingInsights] = useState(true)
  const [error, setError] = useState(null)
  const streamRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamText, streamPhase])

  useEffect(() => {
    setLoadingInsights(true)
    fetchInsights({ limit: 50 })
      .then((data) => {
        const list = data.items || []
        setInsights(list)
        if (list.length > 0 && !selectedId) setSelectedId(list[0].insight_id)
        setLoadingInsights(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoadingInsights(false)
      })
  }, [])

  const askCopilot = () => {
    if (!selectedId) return
    const insight = insights.find((i) => i.insight_id === selectedId)
    const summary = insight?.summary || selectedId
    setMessages((prev) => [...prev, { role: 'user', text: `Explain this insight: ${summary.slice(0, 80)}…`, insight_id: selectedId }])
    setStreamPhase('loading')
    setStreamText('')
    setError(null)

    const { promise, cancel } = copilotStream(selectedId, (ev) => {
      if (ev.phase === 'loading' || ev.phase === 'generating') {
        setStreamPhase(ev.phase)
        setStreamText('')
      } else if (ev.phase === 'chunk' && ev.text) {
        setStreamPhase('chunk')
        setStreamText((prev) => prev + ev.text)
      } else if (ev.phase === 'done' && ev.data) {
        setStreamPhase(null)
        const d = ev.data
        const text = [d.tldr, d.explanation, d.business_reasoning].filter(Boolean).join('\n\n')
        setMessages((prev) => [...prev, { role: 'assistant', text: text || JSON.stringify(d), data: d }])
        setStreamText('')
      } else if (ev.phase === 'error') {
        setStreamPhase(null)
        setMessages((prev) => [...prev, { role: 'assistant', text: `Error: ${ev.error || 'Unknown'}`, error: true }])
        setError(ev.error)
        setStreamText('')
      }
    })
    streamRef.current = cancel
    promise.catch((err) => {
      setStreamPhase(null)
      setMessages((prev) => [...prev, { role: 'assistant', text: `Error: ${err.message}`, error: true }])
      setError(err.message)
      setStreamText('')
    })
  }

  const clearChat = () => {
    if (streamRef.current) streamRef.current()
    setStreamPhase(null)
    setStreamText('')
    setMessages([])
  }

  const phaseMessage = streamPhase === 'loading' ? 'Accessing insights & decision history…' : streamPhase === 'generating' ? 'Generating analysis…' : null

  return (
    <div className="flex flex-col h-[calc(100vh-0px)]">
      <div className="flex-shrink-0 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex flex-wrap gap-3 items-end">
          <label className="flex-1 min-w-[200px]">
            <span className="block text-xs font-medium text-slate-500 mb-1">Select insight</span>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              disabled={loadingInsights}
            >
              <option value="">— Select —</option>
              {insights.map((i) => (
                <option key={i.insight_id} value={i.insight_id}>
                  {i.insight_type || 'insight'} — {(i.summary || i.insight_id).slice(0, 50)}…
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={askCopilot}
            disabled={!selectedId || !!streamPhase}
            className="rounded-lg bg-slate-800 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {streamPhase ? '…' : 'Ask Copilot'}
          </button>
          {messages.length > 0 && !streamPhase && (
            <button
              type="button"
              onClick={clearChat}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Clear chat
            </button>
          )}
        </div>
        {error && !streamPhase && (
          <div className="mt-2 rounded-lg bg-red-50 text-red-700 px-3 py-2 text-sm" role="alert">
            {error}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto bg-slate-50/50 px-6 py-4">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 && !streamPhase && (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
              <p className="text-sm">Select an insight and click <strong>Ask Copilot</strong> to get an explanation.</p>
              <p className="text-xs mt-2">Responses are grounded in your insights and decision history.</p>
            </div>
          )}

          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                  m.role === 'user'
                    ? 'bg-slate-800 text-white'
                    : m.error
                    ? 'bg-red-50 text-red-800 border border-red-200'
                    : 'bg-white text-slate-800 border border-slate-200 shadow-sm'
                }`}
              >
                <p className="text-xs font-medium opacity-80 mb-1">{m.role === 'user' ? 'You' : 'Copilot'}</p>
                <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0">
                  {m.role === 'assistant' ? (
                    <ReactMarkdown>{m.text}</ReactMarkdown>
                  ) : (
                    <p className="whitespace-pre-wrap">{m.text}</p>
                  )}
                </div>
                {m.data?.action_steps?.length > 0 && (
                  <ul className="mt-2 list-disc list-inside text-slate-700 text-sm">
                    {m.data.action_steps.map((step, i) => (
                      <li key={i}>{typeof step === 'string' ? step : step}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))}

          {phaseMessage && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-white border border-slate-200 shadow-sm px-4 py-3 flex items-center gap-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-sm text-slate-600">{phaseMessage}</span>
              </div>
            </div>
          )}

          {streamPhase === 'chunk' && streamText && (
            <div className="flex justify-start">
              <div className="max-w-[85%] rounded-2xl bg-white border border-slate-200 shadow-sm px-4 py-3">
                <p className="text-xs font-medium text-slate-500 mb-1">Copilot</p>
                <div className="prose prose-sm max-w-none prose-p:my-1">
                  <ReactMarkdown>{streamText}</ReactMarkdown>
                </div>
                <span className="inline-block w-2 h-4 ml-0.5 bg-slate-400 animate-pulse" aria-hidden />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
