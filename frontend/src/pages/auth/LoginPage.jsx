import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/Button";
import { FieldError, Input, Label } from "../../components/ui/Field";
import { AuthShell } from "./AuthShell";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const data = await login(form);
      navigate(data.company.onboarding_completed ? "/app/dashboard" : "/onboarding", {
        replace: true,
      });
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title={t("auth.welcomeBack")}
      subtitle={t("auth.loginSubtitle")}
      footer={
        <span>
          {t("auth.newTo")}{" "}
          <Link to="/register" className="font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300">
            {t("auth.createAccount")}
          </Link>
        </span>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div>
          <Label htmlFor="email">{t("auth.email")}</Label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-400" />
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={form.email}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              className="pl-9"
              placeholder="you@company.com"
            />
          </div>
        </div>

        <div>
          <Label htmlFor="password">{t("auth.password")}</Label>
          <div className="relative">
            <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-400" />
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
              className="pl-9 pr-10"
              placeholder="••••••••"
            />
            <button
              type="button"
              onClick={() => setShowPassword((current) => !current)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-navy-400 hover:bg-navy-50 hover:text-navy-700 dark:hover:bg-navy-800"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <FieldError>{error}</FieldError>

        <Button type="submit" className="w-full" size="lg" loading={submitting}>
          {submitting ? t("auth.signingIn") : t("auth.signIn")}
        </Button>
      </form>
    </AuthShell>
  );
}
