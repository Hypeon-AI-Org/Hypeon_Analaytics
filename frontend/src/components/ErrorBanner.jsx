import React from 'react'

/**
 * Shared error display with optional retry. Use for page-level and section-level errors.
 */
export default function ErrorBanner({ message, onRetry, className = '' }) {
  return (
    <div
      className={`rounded-xl border border-red-200 bg-red-50/90 text-red-700 px-4 py-3 flex items-center justify-between gap-3 ${className}`}
      role="alert"
    >
      <span className="text-sm">{message}</span>
      {typeof onRetry === 'function' && (
        <button
          type="button"
          onClick={onRetry}
          className="flex-shrink-0 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}
