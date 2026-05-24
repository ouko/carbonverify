import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectDetailPage from './pages/ProjectDetailPage'
import DataSourcesPage from './pages/DataSourcesPage'
import CalculationsPage from './pages/CalculationsPage'
import ReportsPage from './pages/ReportsPage'
import ReviewQueuePage from './pages/ReviewQueuePage'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  const initialize = useAuthStore((s) => s.initialize)

  useEffect(() => {
    initialize()
  }, [initialize])

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/data-sources" element={<DataSourcesPage />} />
          <Route path="/calculations" element={<CalculationsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/review-queue" element={<ReviewQueuePage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
