import { Suspense, lazy, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoadingSpinner } from './components/LoadingSpinner';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectDetailPage from './pages/ProjectDetailPage';
import ProjectCreatePage from './pages/ProjectCreatePage';
import DataSourcesPage from './pages/DataSourcesPage';
import CalculationsPage from './pages/CalculationsPage';
import ReportsPage from './pages/ReportsPage';
import ReviewQueuePage from './pages/ReviewQueuePage';

// Lazy load heavy pages for code-splitting
const FieldDashboardPage = lazy(() => import('./pages/FieldDashboardPage').then(m => ({ default: m.FieldDashboardPage })));
const SecuritySettingsPage = lazy(() => import('./pages/SecuritySettingsPage').then(m => ({ default: m.SecuritySettingsPage })));
const AuditLogPage = lazy(() => import('./pages/AuditLogPage').then(m => ({ default: m.AuditLogPage })));
const ComplianceDashboardPage = lazy(() => import('./pages/ComplianceDashboardPage').then(m => ({ default: m.ComplianceDashboardPage })));
const BrokeragePage = lazy(() => import('./pages/BrokeragePage').then(m => ({ default: m.BrokeragePage })));
const TokenizationPage = lazy(() => import('./pages/TokenizationPage').then(m => ({ default: m.TokenizationPage })));
const CorporateDashboardPage = lazy(() => import('./pages/CorporateDashboardPage').then(m => ({ default: m.CorporateDashboardPage })));
const LeadsPage = lazy(() => import('./pages/LeadsPage').then(m => ({ default: m.default })));
const CommandLayout = lazy(() => import('./components/CommandLayout').then(m => ({ default: m.default })));
const InboxPage = lazy(() => import('./pages/command/InboxPage').then(m => ({ default: m.InboxPage })));
const ProjectsGridPage = lazy(() => import('./pages/command/ProjectsGridPage').then(m => ({ default: m.ProjectsGridPage })));
const VVBPipelinePage = lazy(() => import('./pages/command/VVBPipelinePage').then(m => ({ default: m.VVBPipelinePage })));
const QualityMetricsPage = lazy(() => import('./pages/command/QualityMetricsPage').then(m => ({ default: m.QualityMetricsPage })));
const AgentPerformancePage = lazy(() => import('./pages/command/AgentPerformancePage').then(m => ({ default: m.AgentPerformancePage })));
const SettingsPage = lazy(() => import('./pages/command/SettingsPage').then(m => ({ default: m.SettingsPage })));

function App() {
  useEffect(() => {
    useAuthStore.getState().initialize()
  }, [])

  return (
    <ErrorBoundary>
      <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/projects/new" element={<ProjectCreatePage />} />
                <Route path="/projects/:id" element={<ProjectDetailPage />} />
                <Route path="/data-sources" element={<DataSourcesPage />} />
                <Route path="/calculations" element={<CalculationsPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/review-queue" element={<ReviewQueuePage />} />
                <Route path="/field" element={<Suspense fallback={<LoadingSpinner />}><FieldDashboardPage /></Suspense>} />
                <Route path="/security" element={<Suspense fallback={<LoadingSpinner />}><SecuritySettingsPage /></Suspense>} />
                <Route path="/audit" element={<Suspense fallback={<LoadingSpinner />}><AuditLogPage /></Suspense>} />
                <Route path="/compliance" element={<Suspense fallback={<LoadingSpinner />}><ComplianceDashboardPage /></Suspense>} />
                <Route path="/brokerage" element={<Suspense fallback={<LoadingSpinner />}><BrokeragePage /></Suspense>} />
                <Route path="/tokenization" element={<Suspense fallback={<LoadingSpinner />}><TokenizationPage /></Suspense>} />
                <Route path="/corporate" element={<Suspense fallback={<LoadingSpinner />}><CorporateDashboardPage /></Suspense>} />
                <Route path="/leads" element={<Suspense fallback={<LoadingSpinner />}><LeadsPage /></Suspense>} />
              </Route>
              <Route element={<Suspense fallback={<LoadingSpinner />}><CommandLayout /></Suspense>}>
                <Route path="/command-center/inbox" element={<Suspense fallback={<LoadingSpinner />}><InboxPage /></Suspense>} />
                <Route path="/command-center/projects" element={<Suspense fallback={<LoadingSpinner />}><ProjectsGridPage /></Suspense>} />
                <Route path="/command-center/vvb" element={<Suspense fallback={<LoadingSpinner />}><VVBPipelinePage /></Suspense>} />
                <Route path="/command-center/quality" element={<Suspense fallback={<LoadingSpinner />}><QualityMetricsPage /></Suspense>} />
                <Route path="/command-center/agents" element={<Suspense fallback={<LoadingSpinner />}><AgentPerformancePage /></Suspense>} />
                <Route path="/command-center/settings" element={<Suspense fallback={<LoadingSpinner />}><SettingsPage /></Suspense>} />
                <Route path="/command-center" element={<Navigate to="/command-center/inbox" replace />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}

export default App;
