import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectDetailPage from './pages/ProjectDetailPage';
import DataSourcesPage from './pages/DataSourcesPage';
import CalculationsPage from './pages/CalculationsPage';
import ReportsPage from './pages/ReportsPage';
import ReviewQueuePage from './pages/ReviewQueuePage';
import { FieldDashboardPage } from './pages/FieldDashboardPage';
import CommandLayout from './components/CommandLayout';
import { InboxPage } from './pages/command/InboxPage';
import { ProjectsGridPage } from './pages/command/ProjectsGridPage';
import { VVBPipelinePage } from './pages/command/VVBPipelinePage';
import { QualityMetricsPage } from './pages/command/QualityMetricsPage';
import { AgentPerformancePage } from './pages/command/AgentPerformancePage';
import { SettingsPage } from './pages/command/SettingsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5 * 60 * 1000, retry: 1 },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
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
              <Route path="/field" element={<FieldDashboardPage />} />
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
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
