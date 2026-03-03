import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const AUTH_CARD_CLASS = 'w-full max-w-md mx-4 rounded-2xl border border-slate-200/80 bg-white/95 shadow-xl shadow-slate-200/50 backdrop-blur-sm p-8'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const { sendPasswordReset, isConfigured } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!email.trim()) {
      setError('Please enter your email address.')
      return
    }
    if (!isConfigured) {
      setError('Password reset is not configured. Set VITE_FIREBASE_* in .env.')
      return
    }
    setSubmitting(true)
    try {
      await sendPasswordReset(email.trim())
      setSent(true)
    } catch (err) {
      const code = err.code || ''
      let message = err.message || 'Failed to send reset email.'
      if (code === 'auth/user-not-found') message = 'No account found with this email.'
      else if (code === 'auth/invalid-email') message = 'Please enter a valid email address.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (!isConfigured) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-brand-50/30">
        <div className={AUTH_CARD_CLASS}>
          <h1 className="text-xl font-bold text-slate-800 mb-2">Reset password</h1>
          <p className="text-slate-600 text-sm">Firebase is not configured.</p>
          <Link to="/login" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:text-brand-700 hover:underline">
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  if (sent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-brand-50/30">
        <div className={AUTH_CARD_CLASS}>
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-brand-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-slate-800 mb-2">Check your email</h1>
            <p className="text-slate-600 text-sm">
              If an account exists for {email}, we sent a link to reset your password.
            </p>
          </div>
          <Link to="/login" className="mt-6 block text-center font-semibold text-brand-600 hover:text-brand-700 hover:underline">
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-brand-50/30">
      <div className={AUTH_CARD_CLASS}>
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-slate-800 tracking-tight">Reset password</h1>
          <p className="text-slate-500 text-sm mt-1">
            Enter your email and we’ll send you a link to reset your password.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="forgot-email" className="block text-sm font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              id="forgot-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-4 py-3 text-slate-800 placeholder-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 focus:outline-none transition-shadow"
              placeholder="you@example.com"
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
            {submitting ? 'Sending…' : 'Send reset link'}
          </button>
        </form>
        <Link to="/login" className="mt-6 block text-center text-sm font-medium text-brand-600 hover:text-brand-700 hover:underline">
          Back to sign in
        </Link>
      </div>
    </div>
  )
}
