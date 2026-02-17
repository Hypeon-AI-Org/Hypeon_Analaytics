import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Metrics from './pages/Metrics'
import Decisions from './pages/Decisions'
import Report from './pages/Report'
import Copilot from './pages/Copilot'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/metrics" element={<Metrics />} />
        <Route path="/decisions" element={<Decisions />} />
        <Route path="/report" element={<Report />} />
        <Route path="/copilot" element={<Copilot />} />
      </Routes>
    </Layout>
  )
}

export default App
