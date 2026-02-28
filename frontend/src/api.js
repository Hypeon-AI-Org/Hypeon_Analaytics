const API_BASE = import.meta.env.VITE_API_BASE || ''

function defaultHeaders() {
  const h = { 'X-Organization-Id': 'default' }
  if (import.meta.env.VITE_API_KEY) h['X-API-Key'] = import.meta.env.VITE_API_KEY
  return h
}

function apiErrorMessage(res, err) {
  if (err && typeof err === 'object' && typeof err.detail === 'object' && err.detail?.message) return err.detail.message
  if (err?.message) return err.message
  if (res) {
    if (res.status === 502 || res.status === 503) return 'Backend not reachable. Start the backend on port 8001 and retry.'
    if (res.status === 404) return 'Not found. Ensure backend is running and routes are mounted.'
  }
  return res?.statusText || 'Request failed'
}

// ----- Dashboard API (cache-only, <300ms) -----
export async function fetchBusinessOverview(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  const res = await fetch(`${API_BASE}/api/v1/dashboard/business-overview?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorMessage(res, err))
  }
  return res.json()
}

export async function fetchCampaignPerformance(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  const res = await fetch(`${API_BASE}/api/v1/dashboard/campaign-performance?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorMessage(res, err))
  }
  return res.json()
}

export async function fetchFunnel(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  const res = await fetch(`${API_BASE}/api/v1/dashboard/funnel?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(apiErrorMessage(res, err))
  }
  return res.json()
}

// Actions endpoint removed (no decision engine). Action Center shows empty list.
export async function fetchActions(params = {}) {
  return Promise.resolve({ items: [], count: 0 })
}

// ----- Analysis API (raw staging tables, in-depth breakdowns) -----
export async function fetchGoogleAdsAnalysis({ client_id, days, start_date, end_date } = {}) {
  const sp = new URLSearchParams()
  if (client_id != null) sp.set('client_id', client_id)
  if (days != null) sp.set('days', days)
  if (start_date) sp.set('start_date', start_date)
  if (end_date) sp.set('end_date', end_date)
  const res = await fetch(`${API_BASE}/api/v1/analysis/google-ads?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchGoogleAnalyticsAnalysis({ client_id, days, start_date, end_date } = {}) {
  const sp = new URLSearchParams()
  if (client_id != null) sp.set('client_id', client_id)
  if (days != null) sp.set('days', days)
  if (start_date) sp.set('start_date', start_date)
  if (end_date) sp.set('end_date', end_date)
  const res = await fetch(`${API_BASE}/api/v1/analysis/google-analytics?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

// ----- Copilot chat (LLM + run_sql on ADS/GA4 datasets) -----
export async function copilotChat({ message, session_id, client_id } = {}) {
  const res = await fetch(`${API_BASE}/api/v1/copilot/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...defaultHeaders() },
    body: JSON.stringify({ message: message || '', session_id, client_id }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const msg = (typeof err.detail === 'object' && err.detail?.message) || err.message || res.statusText
    throw new Error(msg || 'Request failed')
  }
  return res.json()
}

export async function copilotChatHistory(session_id) {
  const res = await fetch(`${API_BASE}/api/v1/copilot/chat/history?session_id=${encodeURIComponent(session_id)}`, {
    headers: defaultHeaders(),
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchCopilotSessions() {
  const res = await fetch(`${API_BASE}/api/v1/copilot/sessions`, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

// ----- Existing -----
export async function fetchInsights(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  if (params.status) sp.set('status', params.status)
  if (params.limit) sp.set('limit', params.limit)
  const url = `${API_BASE}/insights?${sp}`
  const res = await fetch(url, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function applyRecommendation(insightId, status, userId = null) {
  const res = await fetch(`${API_BASE}/recommendations/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...defaultHeaders() },
    body: JSON.stringify({ insight_id: insightId, status, user_id: userId }),
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function copilotQuery(insightId) {
  const res = await fetch(`${API_BASE}/copilot_query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...defaultHeaders() },
    body: JSON.stringify({ insight_id: insightId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail?.message || err.message || res.statusText)
  }
  return res.json()
}

export function copilotStream(insightId, onEvent) {
  const controller = new AbortController()
  const promise = (async () => {
    const res = await fetch(`${API_BASE}/copilot/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...defaultHeaders() },
      body: JSON.stringify({ insight_id: insightId }),
      signal: controller.signal,
    })
    if (!res.ok) throw new Error(res.statusText)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n\n')
      buf = lines.pop() || ''
      for (const block of lines) {
        const m = block.match(/^data:\s*(.+)$/m)
        if (m) {
          try {
            const ev = JSON.parse(m[1])
            onEvent(ev)
          } catch (_) {}
        }
      }
    }
    if (buf) {
      const m = buf.match(/^data:\s*(.+)$/m)
      if (m) try { onEvent(JSON.parse(m[1])) } catch (_) {}
    }
  })()
  return { promise, cancel: () => controller.abort() }
}
