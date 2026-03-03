/**
 * Firebase App and Auth initialization for email/password login.
 * Uses VITE_FIREBASE_* env vars from .env. If not set, auth is disabled (e.g. dev without Firebase).
 */
import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

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
