import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Building2, Eye, EyeOff, LockKeyhole, Mail, UserRound } from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/Button";
import { FieldError, Input, Label } from "../../components/ui/Field";
import { AuthShell } from "./AuthShell";

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { register } = useAuth();
  const [form, setForm] = useState({
    full_name: "",
    company_name: "",
    email: "",
    password: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const update = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await register(form);
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title={t("auth.registerTitle")}
      subtitle={t("auth.registerSubtitle")}
      footer={
        <span>
          {t("auth.alreadyHave")}{" "}
          <Link to="/login" className="font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300">
            {t("auth.signInLink")}
          </Link>
        </span>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div>
          <Label htmlFor="full_name">{t("auth.fullName")}</Label>
          <div className="relative">
            <UserRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-400" />
            <Input
              id="full_name"
              autoComplete="name"
              required
              value={form.full_name}
              onChange={update("full_name")}
              className="pl-9"
              placeholder="Asha Rao"
            />
          </div>
        </div>

        <div>
          <Label htmlFor="company_name">{t("auth.companyName")}</Label>
          <div className="relative">
            <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-400" />
            <Input
              id="company_name"
              autoComplete="organization"
              required
              value={form.company_name}
              onChange={update("company_name")}
              className="pl-9"
              placeholder="Asha Infra Pvt Ltd"
            />
          </div>
        </div>

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
              onChange={update("email")}
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
              autoComplete="new-password"
              required
              minLength={8}
              value={form.password}
              onChange={update("password")}
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
          <p className="mt-1.5 text-xs muted">{t("auth.passwordHint")}</p>
        </div>

        <FieldError>{error}</FieldError>

        <Button type="submit" className="w-full" size="lg" loading={submitting}>
          {submitting ? t("auth.creatingAccount") : t("auth.createAccount")}
        </Button>
      </form>
    </AuthShell>
  );
}
