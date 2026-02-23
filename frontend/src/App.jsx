import React from 'react'
import InsightsList from './InsightsList'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-4 px-4">
          <h1 className="text-xl font-semibold text-gray-800">HypeOn Analytics V1 — Insights</h1>
        </div>
      </header>
      <main className="max-w-7xl mx-auto py-6 px-4">
        <InsightsList />
      </main>
    </div>
  )
}
