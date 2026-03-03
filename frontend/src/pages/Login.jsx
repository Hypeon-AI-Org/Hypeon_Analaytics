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

  const from = location.state?.from?.pathname || '/dashboard'

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
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-brand-50/30">
        <div className={AUTH_CARD_CLASS}>
          <h1 className="text-xl font-bold text-slate-800 mb-2">Sign in</h1>
          <p className="text-slate-600 text-sm">
            Firebase is not configured. Add VITE_FIREBASE_API_KEY, VITE_FIREBASE_PROJECT_ID, etc. to your .env to enable login.
          </p>
          <p className="text-slate-500 text-xs mt-4">
            You can still use the app with header-based auth (X-Organization-Id, X-API-Key) if the backend allows it.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-brand-50/30">
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
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 focus:outline-none transition-shadow"
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
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 focus:outline-none transition-shadow"
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
            className="w-full rounded-xl bg-brand-600 text-white py-3 px-4 font-semibold hover:bg-brand-700 focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-brand-500/25"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
          <p className="text-center text-sm text-slate-600">
            <Link to="/forgot-password" className="text-brand-600 hover:text-brand-700 font-medium hover:underline">
              Forgot password?
            </Link>
          </p>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          Don’t have an account?{' '}
          <Link to="/signup" className="font-semibold text-brand-600 hover:text-brand-700 hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  )
}
