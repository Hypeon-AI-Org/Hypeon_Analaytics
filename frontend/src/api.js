const API_BASE = import.meta.env.VITE_API_BASE || ''

function defaultHeaders() {
  const h = { 'X-Organization-Id': 'default' }
  if (import.meta.env.VITE_API_KEY) h['X-API-Key'] = import.meta.env.VITE_API_KEY
  return h
}

// ----- Dashboard API (cache-only, <300ms) -----
export async function fetchBusinessOverview(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  const res = await fetch(`${API_BASE}/api/v1/dashboard/business-overview?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchCampaignPerformance(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  const res = await fetch(`${API_BASE}/api/v1/dashboard/campaign-performance?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchFunnel(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  const res = await fetch(`${API_BASE}/api/v1/dashboard/funnel?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function fetchActions(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  const res = await fetch(`${API_BASE}/api/v1/dashboard/actions?${sp}`, { headers: defaultHeaders() })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

// ----- V1 Copilot (free-form query, structured response + optional layout) -----
export async function queryCopilot({ query, client_id, session_id, insight_id } = {}) {
  const res = await fetch(`${API_BASE}/api/v1/copilot/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...defaultHeaders() },
    body: JSON.stringify({ query: query || '', client_id, session_id, insight_id }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail?.message || err.message || res.statusText)
  }
  return res.json()
}

export function copilotStreamV1({ query, client_id, session_id, insight_id }, onEvent) {
  const controller = new AbortController()
  const promise = (async () => {
    const res = await fetch(`${API_BASE}/api/v1/copilot/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...defaultHeaders() },
      body: JSON.stringify({ query: query || '', client_id, session_id, insight_id }),
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
            onEvent(JSON.parse(m[1]))
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

export async function simulateBudgetShift(body) {
  const res = await fetch(`${API_BASE}/simulate_budget_shift`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...defaultHeaders() },
    body: JSON.stringify(body),
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
