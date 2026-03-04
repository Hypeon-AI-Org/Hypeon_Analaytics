/**
 * Firebase App and Auth initialization for email/password login.
 * Uses runtime config (window.__APP_CONFIG__) or Vite build-time env. If not set, auth is disabled.
 */
import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getFirebaseConfig } from './runtimeConfig'

const firebaseConfig = getFirebaseConfig()

let app = null
let auth = null

if (firebaseConfig.apiKey && firebaseConfig.projectId) {
  try {
    app = initializeApp(firebaseConfig)
    auth = getAuth(app)
  } catch (e) {
    console.warn('Firebase init failed:', e)
  }
}

export { app, auth }
export const isFirebaseConfigured = () => !!auth
