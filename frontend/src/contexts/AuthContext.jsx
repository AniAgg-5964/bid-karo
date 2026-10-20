import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, getToken, setToken as persistToken } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(getToken());
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  const clearSession = useCallback(() => {
    persistToken(null);
    setTokenState(null);
    setSession(null);
    setLoading(false);
  }, []);

  useEffect(() => {
    let active = true;
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .get("/auth/me")
      .then((data) => {
        if (active) setSession(data);
      })
      .catch(() => {
        if (active) clearSession();
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token, clearSession]);

  useEffect(() => {
    const onExpired = () => {
      setTokenState(null);
      setSession(null);
      setLoading(false);
    };
    window.addEventListener("bidkaro:auth-expired", onExpired);
    return () => window.removeEventListener("bidkaro:auth-expired", onExpired);
  }, []);

  const applyAuth = useCallback((data) => {
    persistToken(data.access_token);
    setTokenState(data.access_token);
    setSession({ user: data.user, company: data.company });
    setLoading(false);
  }, []);

  const login = useCallback(
    async (credentials) => {
      const data = await api.post("/auth/login", credentials);
      if (data.otp_required) return data;
      applyAuth(data);
      return data;
    },
    [applyAuth],
  );

  const register = useCallback(async (payload) => {
    return api.post("/auth/register", payload);
  }, []);

  const verifyOtp = useCallback(
    async (payload) => {
      const data = await api.post("/auth/verify-otp", payload);
      applyAuth(data);
      return data;
    },
    [applyAuth],
  );

  const resendOtp = useCallback(
    async (payload) => api.post("/auth/resend-otp", payload),
    [],
  );

  const updateSecurity = useCallback(
    async (payload) => {
      const user = await api.post("/auth/security", payload);
      setSession((current) => (current ? { ...current, user } : current));
      return user;
    },
    [],
  );

  const refreshSession = useCallback(async () => {
    const data = await api.get("/auth/me");
    setSession(data);
    return data;
  }, []);

  const updateCompany = useCallback((company) => {
    setSession((current) => (current ? { ...current, company } : current));
  }, []);

  const value = useMemo(
    () => ({
      token,
      session,
      loading,
      isAuthenticated: Boolean(token && session),
      login,
      register,
      verifyOtp,
      resendOtp,
      updateSecurity,
      logout: clearSession,
      refreshSession,
      updateCompany,
    }),
    [
      token,
      session,
      loading,
      login,
      register,
      verifyOtp,
      resendOtp,
      updateSecurity,
      clearSession,
      refreshSession,
      updateCompany,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
