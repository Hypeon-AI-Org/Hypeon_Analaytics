/**
 * Runtime config: read from window.__APP_CONFIG__ (injected at container startup)
 * with fallback to Vite build-time import.meta.env.
 */
function getConfig(key) {
  if (typeof window !== 'undefined' && window.__APP_CONFIG__ && key in window.__APP_CONFIG__) {
    const v = window.__APP_CONFIG__[key]
    if (v != null && v !== '') return v
  }
  return import.meta.env[key] ?? ''
}

export function getApiBase() {
  return getConfig('VITE_API_BASE') || ''
}

export function getApiKey() {
  return getConfig('VITE_API_KEY') || ''
}

export function getFirebaseConfig() {
  return {
    apiKey: getConfig('VITE_FIREBASE_API_KEY'),
    authDomain: getConfig('VITE_FIREBASE_AUTH_DOMAIN'),
    projectId: getConfig('VITE_FIREBASE_PROJECT_ID'),
    storageBucket: getConfig('VITE_FIREBASE_STORAGE_BUCKET'),
    messagingSenderId: getConfig('VITE_FIREBASE_MESSAGING_SENDER_ID'),
    appId: getConfig('VITE_FIREBASE_APP_ID'),
    measurementId: getConfig('VITE_FIREBASE_MEASUREMENT_ID') || undefined,
  }
}
