import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./contexts/AuthContext";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute, PublicOnlyRoute } from "./components/layout/ProtectedRoute";
import { FullPageLoader } from "./components/ui/Spinner";
import { LoginPage } from "./pages/auth/LoginPage";
import { RegisterPage } from "./pages/auth/RegisterPage";
import { OnboardingPage } from "./pages/onboarding/OnboardingPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { TendersPage } from "./pages/TendersPage";
import { TenderDetailPage } from "./pages/TenderDetailPage";
import { ChecklistPage } from "./pages/ChecklistPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { ChangesPage } from "./pages/ChangesPage";
import { RemindersPage } from "./pages/RemindersPage";
import { CompanyProfilePage } from "./pages/CompanyProfilePage";
import { SettingsPage } from "./pages/SettingsPage";
import { NotFoundPage } from "./pages/NotFoundPage";

function HomeRedirect() {
  const { loading, isAuthenticated, session } = useAuth();
  if (loading) return <FullPageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return (
    <Navigate
      to={session?.company?.onboarding_completed ? "/app/dashboard" : "/onboarding"}
      replace
    />
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnlyRoute>
            <RegisterPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/onboarding"
        element={
          <ProtectedRoute requireOnboarding={false}>
            <OnboardingPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/app/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="discover" element={<DiscoverPage />} />
        <Route path="tenders" element={<TendersPage />} />
        <Route path="tenders/:tenderId" element={<TenderDetailPage />} />
        <Route path="checklist" element={<ChecklistPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="changes" element={<ChangesPage />} />
        <Route path="reminders" element={<RemindersPage />} />
        <Route path="company" element={<CompanyProfilePage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
