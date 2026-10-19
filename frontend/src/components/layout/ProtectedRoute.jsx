import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../../contexts/AuthContext";
import { FullPageLoader } from "../ui/Spinner";

export function ProtectedRoute({ children, requireOnboarding = true }) {
  const { loading, isAuthenticated, session } = useAuth();
  const location = useLocation();

  if (loading) return <FullPageLoader />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (requireOnboarding && !session?.company?.onboarding_completed) {
    return <Navigate to="/onboarding" replace />;
  }
  return children;
}

export function PublicOnlyRoute({ children }) {
  const { loading, isAuthenticated, session } = useAuth();
  if (loading) return <FullPageLoader />;
  if (isAuthenticated) {
    return (
      <Navigate
        to={session?.company?.onboarding_completed ? "/app/dashboard" : "/onboarding"}
        replace
      />
    );
  }
  return children;
}
