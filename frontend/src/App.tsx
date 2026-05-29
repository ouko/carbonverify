import { Suspense, lazy, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LoadingSpinner } from './components/LoadingSpinner';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import LoginPage from './pages/LoginPage';

// Invite acceptance page (public, but checks invite token)
const InviteAcceptPage = lazy(() => import('./pages/InviteAcceptPage').then(m => ({ default: m.default })));

// Core dashboard pages (eager — visited on every login)
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.default })));

// Lazy load all other pages for code-splitting
const ProjectsPage = lazy(() => import('./pages/ProjectsPage').then(m => ({ default: m.default })));
const ProjectDetailPage = lazy(() => import('./pages/ProjectDetailPage').then(m => ({ default: m.default })));
const ProjectCreatePage = lazy(() => import('./pages/ProjectCreatePage').then(m => ({ default: m.default })));
const DataSourcesPage = lazy(() => import('./pages/DataSourcesPage').then(m => ({ default: m.default })));
const DataSourceDetailPage = lazy(() => import('./pages/DataSourceDetailPage').then(m => ({ default: m.default })));
const CalculationsPage = lazy(() => import('./pages/CalculationsPage').then(m => ({ default: m.default })));
const CalculationDetailPage = lazy(() => import('./pages/CalculationDetailPage').then(m => ({ default: m.default })));
const ReportsPage = lazy(() => import('./pages/ReportsPage').then(m => ({ default: m.default })));
const ReportDetailPage = lazy(() => import('./pages/ReportDetailPage').then(m => ({ default: m.default })));
const ReviewQueuePage = lazy(() => import('./pages/ReviewQueuePage').then(m => ({ default: m.default })));
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

// Admin pages
const AdminLayout = lazy(() => import('./layouts/AdminLayout').then(m => ({ default: m.default })));
const AdminDashboardPage = lazy(() => import('./pages/admin/AdminDashboardPage').then(m => ({ default: m.default })));
const UserManagementPage = lazy(() => import('./pages/admin/UserManagementPage').then(m => ({ default: m.default })));
const UserDetailPage = lazy(() => import('./pages/admin/UserDetailPage').then(m => ({ default: m.default })));
const SessionManagementPage = lazy(() => import('./pages/admin/SessionManagementPage').then(m => ({ default: m.default })));
const AdminSettingsPage = lazy(() => import('./pages/admin/AdminSettingsPage').then(m => ({ default: m.default })));

function App() {
  useEffect(() => {
    useAuthStore.getState().initialize()
  }, [])

  return (
    <ErrorBoundary>
      <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<InviteAcceptPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Suspense fallback={<LoadingSpinner />}><DashboardPage /></Suspense>} />
                <Route path="/projects" element={<Suspense fallback={<LoadingSpinner />}><ProjectsPage /></Suspense>} />
                <Route path="/projects/new" element={<Suspense fallback={<LoadingSpinner />}><ProjectCreatePage /></Suspense>} />
                <Route path="/projects/:id" element={<Suspense fallback={<LoadingSpinner />}><ProjectDetailPage /></Suspense>} />
                <Route path="/data-sources" element={<Suspense fallback={<LoadingSpinner />}><DataSourcesPage /></Suspense>} />
                <Route path="/data-sources/:id" element={<Suspense fallback={<LoadingSpinner />}><DataSourceDetailPage /></Suspense>} />
                <Route path="/calculations" element={<Suspense fallback={<LoadingSpinner />}><CalculationsPage /></Suspense>} />
                <Route path="/calculations/:id" element={<Suspense fallback={<LoadingSpinner />}><CalculationDetailPage /></Suspense>} />
                <Route path="/reports" element={<Suspense fallback={<LoadingSpinner />}><ReportsPage /></Suspense>} />
                <Route path="/reports/:id" element={<Suspense fallback={<LoadingSpinner />}><ReportDetailPage /></Suspense>} />
                <Route path="/review-queue" element={<Suspense fallback={<LoadingSpinner />}><ReviewQueuePage /></Suspense>} />
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
              <Route element={<AdminRoute />}>
                <Route element={<Suspense fallback={<LoadingSpinner />}><AdminLayout /></Suspense>}>
                  <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
                  <Route path="/admin/dashboard" element={<Suspense fallback={<LoadingSpinner />}><AdminDashboardPage /></Suspense>} />
                  <Route path="/admin/users" element={<Suspense fallback={<LoadingSpinner />}><UserManagementPage /></Suspense>} />
                  <Route path="/admin/users/:id" element={<Suspense fallback={<LoadingSpinner />}><UserDetailPage /></Suspense>} />
                  <Route path="/admin/sessions" element={<Suspense fallback={<LoadingSpinner />}><SessionManagementPage /></Suspense>} />
                  <Route path="/admin/settings" element={<Suspense fallback={<LoadingSpinner />}><AdminSettingsPage /></Suspense>} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}

export default App;
