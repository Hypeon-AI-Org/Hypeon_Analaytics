import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const AUTH_CARD_CLASS = 'w-full max-w-md mx-4 rounded-2xl border border-slate-200/80 bg-white/95 shadow-xl shadow-slate-200/50 backdrop-blur-sm p-8'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { signIn, isConfigured } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/copilot'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!email.trim() || !password) {
      setError('Please enter email and password.')
      return
    }
    if (!isConfigured) {
      setError('Login is not configured. Set VITE_FIREBASE_* in .env.')
      return
    }
    setSubmitting(true)
    try {
      await signIn(email.trim(), password)
      navigate(from, { replace: true })
    } catch (err) {
      const message = err.code === 'auth/invalid-credential' || err.code === 'auth/wrong-password'
        ? 'Invalid email or password.'
        : err.message || 'Sign in failed.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (!isConfigured) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className={AUTH_CARD_CLASS}>
          <h1 className="text-xl font-bold text-slate-800 mb-2">Sign in</h1>
          <p className="text-slate-600 text-sm mb-2">
            Firebase is not configured. Add your Web app config to the <strong>repo root .env</strong> to enable login.
          </p>
          <ol className="text-slate-600 text-sm list-decimal list-inside space-y-1 mb-4">
            <li>Open <a href="https://console.firebase.google.com/" target="_blank" rel="noreferrer" className="text-blue-600 underline">Firebase Console</a> → your project → Project settings (gear) → Your apps.</li>
            <li>Create or select a Web app, then copy <code className="bg-slate-100 px-1 rounded">apiKey</code> and <code className="bg-slate-100 px-1 rounded">appId</code> from the config object.</li>
            <li>In the repo root <code className="bg-slate-100 px-1 rounded">.env</code>, set <code className="bg-slate-100 px-1 rounded">VITE_FIREBASE_API_KEY</code> and <code className="bg-slate-100 px-1 rounded">VITE_FIREBASE_APP_ID</code> to those values.</li>
            <li>Restart the frontend dev server (<code className="bg-slate-100 px-1 rounded">npm run dev</code>).</li>
          </ol>
          <p className="text-slate-500 text-xs">
            You can still use the app with header-based auth (X-Organization-Id, X-API-Key) if the backend allows it.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className={AUTH_CARD_CLASS}>
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">Welcome back</h1>
          <p className="text-slate-500 text-sm mt-1">Sign in to HypeOn Analytics</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-300 focus:outline-none transition-shadow"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-slate-700 mb-1">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-300 focus:outline-none transition-shadow"
              placeholder="••••••••"
            />
          </div>
          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2" role="alert">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-slate-800 text-white py-3 px-4 font-semibold hover:bg-slate-900 focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-black/10"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
          <p className="text-center text-sm text-slate-600">
            <Link to="/forgot-password" className="text-slate-700 hover:text-slate-900 font-medium hover:underline">
              Forgot password?
            </Link>
          </p>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          Don’t have an account?{' '}
          <Link to="/signup" className="font-semibold text-slate-700 hover:text-slate-900 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}
