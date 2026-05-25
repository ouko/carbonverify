import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
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
import { FieldDashboardPage } from './pages/FieldDashboardPage';
import { SecuritySettingsPage } from './pages/SecuritySettingsPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { ComplianceDashboardPage } from './pages/ComplianceDashboardPage';
import { BrokeragePage } from './pages/BrokeragePage';
import { TokenizationPage } from './pages/TokenizationPage';
import { CorporateDashboardPage } from './pages/CorporateDashboardPage';
import LeadsPage from './pages/LeadsPage';
import CommandLayout from './components/CommandLayout';
import { InboxPage } from './pages/command/InboxPage';
import { ProjectsGridPage } from './pages/command/ProjectsGridPage';
import { VVBPipelinePage } from './pages/command/VVBPipelinePage';
import { QualityMetricsPage } from './pages/command/QualityMetricsPage';
import { AgentPerformancePage } from './pages/command/AgentPerformancePage';
import { SettingsPage } from './pages/command/SettingsPage';

function App() {
  useEffect(() => {
    useAuthStore.getState().initialize()
  }, [])

  return (
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
              <Route path="/field" element={<FieldDashboardPage />} />
              <Route path="/security" element={<SecuritySettingsPage />} />
              <Route path="/audit" element={<AuditLogPage />} />
              <Route path="/compliance" element={<ComplianceDashboardPage />} />
              <Route path="/brokerage" element={<BrokeragePage />} />
              <Route path="/tokenization" element={<TokenizationPage />} />
              <Route path="/corporate" element={<CorporateDashboardPage />} />
              <Route path="/leads" element={<LeadsPage />} />
            </Route>
            <Route element={<CommandLayout />}>
              <Route path="/command-center/inbox" element={<InboxPage />} />
              <Route path="/command-center/projects" element={<ProjectsGridPage />} />
              <Route path="/command-center/vvb" element={<VVBPipelinePage />} />
              <Route path="/command-center/quality" element={<QualityMetricsPage />} />
              <Route path="/command-center/agents" element={<AgentPerformancePage />} />
              <Route path="/command-center/settings" element={<SettingsPage />} />
              <Route path="/command-center" element={<Navigate to="/command-center/inbox" replace />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
