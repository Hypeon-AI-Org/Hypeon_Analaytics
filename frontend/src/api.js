const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function fetchInsights(params = {}) {
  const sp = new URLSearchParams()
  if (params.client_id != null) sp.set('client_id', params.client_id)
  if (params.status) sp.set('status', params.status)
  if (params.limit) sp.set('limit', params.limit)
  const url = `${API_BASE}/insights?${sp}`
  const res = await fetch(url, { headers: { 'X-API-Key': import.meta.env.VITE_API_KEY || '' } })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function applyRecommendation(insightId, status, userId = null) {
  const res = await fetch(`${API_BASE}/recommendations/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': import.meta.env.VITE_API_KEY || '' },
    body: JSON.stringify({ insight_id: insightId, status, user_id: userId }),
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function simulateBudgetShift(body) {
  const res = await fetch(`${API_BASE}/simulate_budget_shift`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': import.meta.env.VITE_API_KEY || '' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}
