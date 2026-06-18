import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./auth/AuthContext";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import AssetsPage from "./pages/AssetsPage";
import VlansPage from "./pages/VlansPage";
import ScansPage from "./pages/ScansPage";
import ChangesPage from "./pages/ChangesPage";
import CompliancePage from "./pages/CompliancePage";
import TasksPage from "./pages/TasksPage";
import SettingsPage from "./pages/SettingsPage";
import AgentsPage from "./pages/AgentsPage";
import UsersPage from "./pages/UsersPage";

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
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/assets" element={<AssetsPage />} />
        <Route path="/vlans" element={<VlansPage />} />
        <Route path="/scans" element={<ScansPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/changes" element={<ChangesPage />} />
        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/compliance" element={<CompliancePage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
