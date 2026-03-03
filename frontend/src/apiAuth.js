/**
 * Bridge for API layer to get current Firebase ID token.
 * AuthContext sets the provider when user state changes.
 */
let _getToken = null

export function setTokenProvider(fn) {
  _getToken = fn
}

export async function getTokenForRequest() {
  if (!_getToken) return null
  try {
    const result = _getToken()
    return result && typeof result.then === 'function' ? await result : result
  } catch {
    return null
  }
}
