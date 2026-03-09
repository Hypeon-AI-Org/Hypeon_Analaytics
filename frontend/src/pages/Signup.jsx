import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const MIN_PASSWORD_LENGTH = 6
const AUTH_CARD_CLASS = 'w-full max-w-md mx-4 rounded-2xl border border-slate-200/80 bg-white/95 shadow-xl shadow-slate-200/50 backdrop-blur-sm p-8'

export default function Signup() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { signUp, isConfigured } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    const trimmedEmail = email.trim()
    if (!trimmedEmail || !password) {
      setError('Please enter email and password.')
      return
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    if (!isConfigured) {
      setError('Sign up is not configured. Set VITE_FIREBASE_* in .env.')
      return
    }
    setSubmitting(true)
    try {
      await signUp(trimmedEmail, password, displayName.trim() || null)
      navigate('/copilot', { replace: true })
    } catch (err) {
      const code = err.code || ''
      let message = err.message || 'Sign up failed.'
      if (code === 'auth/email-already-in-use') message = 'This email is already registered. Sign in or use another email.'
      else if (code === 'auth/invalid-email') message = 'Please enter a valid email address.'
      else if (code === 'auth/weak-password') message = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (!isConfigured) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className={AUTH_CARD_CLASS}>
          <h1 className="text-xl font-bold text-slate-800 mb-2">Sign up</h1>
          <p className="text-slate-600 text-sm">
            Firebase is not configured. Add VITE_FIREBASE_* to .env to enable sign up.
          </p>
          <Link to="/login" className="mt-4 inline-block text-sm font-medium text-slate-700 hover:text-slate-900 hover:underline">
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-white py-8">
      <div className={AUTH_CARD_CLASS}>
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">Create an account</h1>
          <p className="text-slate-500 text-sm mt-1">Join HypeOn Analytics</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="signup-email" className="block text-sm font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="signup-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-300 focus:outline-none transition-shadow"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label htmlFor="signup-display" className="block text-sm font-medium text-slate-700 mb-1">
              Name <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <input
              id="signup-display"
              type="text"
              autoComplete="name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-300 focus:outline-none transition-shadow"
              placeholder="Your name"
            />
          </div>
          <div>
            <label htmlFor="signup-password" className="block text-sm font-medium text-slate-700 mb-1">
              Password
            </label>
            <input
              id="signup-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-300 focus:outline-none transition-shadow"
              placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
            />
          </div>
          <div>
            <label htmlFor="signup-confirm" className="block text-sm font-medium text-slate-700 mb-1">
              Confirm password
            </label>
            <input
              id="signup-confirm"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
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
            {submitting ? 'Creating account…' : 'Sign up'}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-slate-600">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-slate-700 hover:text-slate-900 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
