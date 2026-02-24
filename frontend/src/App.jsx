import React, { useState } from 'react'
import Layout from './Layout'
import Dashboard from './Dashboard'
import InsightsList from './InsightsList'
import CopilotChat from './CopilotChat'

const PAGES = [
  { id: 'dashboard', label: 'Dashboard', Component: Dashboard },
  { id: 'insights', label: 'Insights', Component: InsightsList },
  { id: 'copilot', label: 'Copilot', Component: CopilotChat },
]

export default function App() {
  const [page, setPage] = useState('dashboard')
  const current = PAGES.find((p) => p.id === page) || PAGES[0]
  const Component = current.Component

  return (
    <Layout page={page} onNavigate={setPage}>
      {page === 'copilot' ? (
        <Component />
      ) : (
        <>
          <header className="flex-shrink-0 border-b border-slate-200 bg-white px-6 py-4">
            <h2 className="text-lg font-semibold text-slate-800">{current.label}</h2>
          </header>
          <div className="flex-1 overflow-auto px-6 py-6">
            <Component />
          </div>
        </>
      )}
    </Layout>
  )
}
