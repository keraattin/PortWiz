import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./auth/AuthContext";
import { useI18n } from "./i18n/I18nContext";

// Route components are code-split so the initial bundle stays small: each page
// (and its heavy imports) loads only when first visited.
const LoginPage = lazy(() => import("./pages/LoginPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));
const AssetDetailPage = lazy(() => import("./pages/AssetDetailPage"));
const VlansPage = lazy(() => import("./pages/VlansPage"));
const ScansPage = lazy(() => import("./pages/ScansPage"));
const ScanRunDetailPage = lazy(() => import("./pages/ScanRunDetailPage"));
const PortsPage = lazy(() => import("./pages/PortsPage"));
const CertificatesPage = lazy(() => import("./pages/CertificatesPage"));
const PortDetailPage = lazy(() => import("./pages/PortDetailPage"));
const ChangesPage = lazy(() => import("./pages/ChangesPage"));
const ChangeDetailPage = lazy(() => import("./pages/ChangeDetailPage"));
const CVEPage = lazy(() => import("./pages/CVEPage"));
const CompliancePage = lazy(() => import("./pages/CompliancePage"));
const TasksPage = lazy(() => import("./pages/TasksPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const AgentsPage = lazy(() => import("./pages/AgentsPage"));
const AgentEnrollPage = lazy(() => import("./pages/AgentEnrollPage"));
const AgentDetailPage = lazy(() => import("./pages/AgentDetailPage"));
const SegmentsPage = lazy(() => import("./pages/SegmentsPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const UserDetailPage = lazy(() => import("./pages/UserDetailPage"));
const DocsPage = lazy(() => import("./pages/DocsPage"));

function PageLoader() {
  const { t } = useI18n();
  return (
    <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">
      {t("common.loading")}
    </div>
  );
}

function ProtectedLayout() {
  const { token, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        Loading…
      </div>
    );
  }
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <Layout />;
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/assets/:id" element={<AssetDetailPage />} />
          <Route path="/vlans" element={<VlansPage />} />
          <Route path="/scans" element={<ScansPage />} />
          <Route path="/scans/:runId" element={<ScanRunDetailPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/agents/new" element={<AgentEnrollPage />} />
          <Route path="/agents/:id" element={<AgentDetailPage />} />
          <Route path="/segments" element={<SegmentsPage />} />
          <Route path="/ports" element={<PortsPage />} />
          <Route path="/ports/:port" element={<PortDetailPage />} />
          <Route path="/certificates" element={<CertificatesPage />} />
          <Route path="/changes" element={<ChangesPage />} />
          <Route path="/changes/:id" element={<ChangeDetailPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/cve" element={<CVEPage />} />
          <Route path="/compliance" element={<CompliancePage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/users/:id" element={<UserDetailPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/docs/:guideId" element={<DocsPage />} />
          <Route path="/help" element={<Navigate to="/docs" replace />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
