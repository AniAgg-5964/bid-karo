import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  BellRing,
  ExternalLink,
  Globe2,
  LogOut,
  Moon,
  Palette,
  ShieldCheck,
  Sun,
  UserRound,
} from "lucide-react";

import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { useToast } from "../contexts/ToastContext";
import { changeLanguage, SUPPORTED_LANGUAGES } from "../i18n";
import { API_URL, api } from "../lib/api";
import { currentLocale } from "../i18n";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { FieldError, Input, Label } from "../components/ui/Field";
import { Modal } from "../components/ui/Modal";
import { cn, formatDate } from "../lib/utils";

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const toast = useToast();
  const { session, logout, updateSecurity, refreshSession } = useAuth();
  const { theme, setTheme } = useTheme();
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [securityOpen, setSecurityOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [securityBusy, setSecurityBusy] = useState(false);
  const [securityError, setSecurityError] = useState("");
  const [reminderEmail, setReminderEmail] = useState(
    Boolean(session?.company?.reminder_email_enabled),
  );
  const [leadDays, setLeadDays] = useState(
    session?.company?.reminder_lead_days?.length
      ? session.company.reminder_lead_days
      : [7, 3, 1],
  );
  const [savingReminders, setSavingReminders] = useState(false);

  const docsUrl = `${API_URL.replace(/\/api$/, "")}/docs`;

  const onLanguage = async (code) => {
    await changeLanguage(code);
    toast.success(t("settings.saved"));
  };

  const onTheme = (value) => {
    setTheme(value);
    toast.success(t("settings.saved"));
  };

  const toggleLeadDay = (day) => {
    setLeadDays((current) => {
      if (current.includes(day)) {
        const next = current.filter((item) => item !== day);
        return next.length ? next : current;
      }
      return [...current, day].sort((a, b) => b - a);
    });
  };

  const saveReminders = async () => {
    setSavingReminders(true);
    try {
      await api.patch("/companies/me", {
        reminder_email_enabled: reminderEmail,
        reminder_lead_days: leadDays,
      });
      await refreshSession().catch(() => null);
      toast.success(t("settings.remindersSaved"));
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setSavingReminders(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Palette className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("settings.appearance")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 pt-4">
              <div>
                <p className="text-sm font-medium text-navy-900 dark:text-white">{t("settings.language")}</p>
                <p className="mt-0.5 text-xs muted">{t("settings.languageHint")}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {SUPPORTED_LANGUAGES.map((language) => (
                    <button
                      key={language.code}
                      type="button"
                      onClick={() => onLanguage(language.code)}
                      className={cn(
                        "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2.5 text-sm font-medium transition",
                        i18n.language === language.code
                          ? "border-teal-300 bg-teal-50 text-teal-800 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-200"
                          : "border-navy-200 text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800",
                      )}
                    >
                      <Globe2 className="h-4 w-4" />
                      {language.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="border-t border-navy-100 pt-5 dark:border-navy-800">
                <p className="text-sm font-medium text-navy-900 dark:text-white">{t("settings.theme")}</p>
                <p className="mt-0.5 text-xs muted">{t("settings.themeHint")}</p>
                <div className="mt-3 flex gap-2">
                  {[
                    { key: "light", icon: Sun },
                    { key: "dark", icon: Moon },
                  ].map(({ key, icon: Icon }) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => onTheme(key)}
                      className={cn(
                        "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2.5 text-sm font-medium capitalize transition",
                        theme === key
                          ? "border-teal-300 bg-teal-50 text-teal-800 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-200"
                          : "border-navy-200 text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800",
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {t(`common.${key}`)}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <BellRing className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("settings.reminders")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-4">
              <div>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-navy-900 dark:text-white">
                    {t("settings.emailReminders")}
                  </p>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={reminderEmail}
                    onClick={() => setReminderEmail((value) => !value)}
                    className={cn(
                      "relative h-6 w-11 rounded-full transition",
                      reminderEmail ? "bg-teal-600" : "bg-navy-200 dark:bg-navy-700",
                    )}
                  >
                    <span
                      className={cn(
                        "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition",
                        reminderEmail ? "left-[22px]" : "left-0.5",
                      )}
                    />
                  </button>
                </div>
                <p className="mt-1 text-xs leading-5 muted">
                  {reminderEmail
                    ? t("settings.emailRemindersOn")
                    : t("settings.emailRemindersOff")}
                </p>
                <p className="mt-1 text-xs leading-5 muted">{t("settings.remindersHint")}</p>
              </div>

              <div className="border-t border-navy-100 pt-4 dark:border-navy-800">
                <p className="text-sm font-medium text-navy-900 dark:text-white">
                  {t("settings.leadDays")}
                </p>
                <p className="mt-0.5 text-xs muted">{t("settings.leadDaysHint")}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[14, 7, 3, 1].map((day) => (
                    <button
                      key={day}
                      type="button"
                      onClick={() => toggleLeadDay(day)}
                      aria-pressed={leadDays.includes(day)}
                      className={cn(
                        "rounded-lg border px-3 py-1.5 text-xs font-semibold transition",
                        leadDays.includes(day)
                          ? "border-teal-300 bg-teal-50 text-teal-800 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-200"
                          : "border-navy-200 text-navy-600 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-300 dark:hover:bg-navy-800",
                      )}
                    >
                      {day}d
                    </button>
                  ))}
                </div>
                <Button className="mt-4" size="sm" onClick={saveReminders} loading={savingReminders}>
                  {t("common.save")}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <UserRound className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("settings.account")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <dl className="grid gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("settings.email")}</dt>
                  <dd className="mt-1 text-sm text-navy-900 dark:text-white">{session?.user?.email}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("settings.role")}</dt>
                  <dd className="mt-1 text-sm capitalize text-navy-900 dark:text-white">{session?.user?.role || "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("settings.company")}</dt>
                  <dd className="mt-1 text-sm text-navy-900 dark:text-white">{session?.company?.name}</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-navy-500 dark:text-navy-300">
                    {t("settings.memberSince")}
                  </dt>
                  <dd className="mt-1 text-sm text-navy-900 dark:text-white">
                    {formatDate(session?.user?.created_at, currentLocale())}
                  </dd>
                </div>
              </dl>

              <div className="border-t border-navy-100 pt-4 dark:border-navy-800">
                <Button variant="outline" size="sm" onClick={() => setConfirmLogout(true)}>
                  <LogOut className="h-4 w-4" />
                  {t("common.signOut")}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("settings.security")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-3">
              <p className="text-sm leading-6 muted">{t("settings.securityNote")}</p>

              <div className="border-t border-navy-100 pt-4 dark:border-navy-800">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-navy-900 dark:text-white">
                    {t("settings.emailSignIn")}
                  </p>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                      session?.user?.otp_login_enabled
                        ? "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                        : "bg-navy-100 text-navy-600 dark:bg-navy-800 dark:text-navy-300",
                    )}
                  >
                    {session?.user?.otp_login_enabled ? "ON" : "OFF"}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 muted">
                  {session?.user?.otp_login_enabled
                    ? t("settings.emailSignInOn")
                    : t("settings.emailSignInOff")}
                </p>
                <p className="mt-1.5 text-xs font-medium text-navy-600 dark:text-navy-300">
                  {session?.user?.email_verified
                    ? t("settings.emailVerified")
                    : t("settings.emailNotVerified")}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => {
                    setSecurityError("");
                    setCurrentPassword("");
                    setSecurityOpen(true);
                  }}
                >
                  {session?.user?.otp_login_enabled
                    ? t("settings.disableEmailSignIn")
                    : t("settings.enableEmailSignIn")}
                </Button>
              </div>

              <a
                href={docsUrl}
                target="_blank"
                rel="noreferrer noopener"
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300"
              >
                {t("settings.apiDocs")}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </CardContent>
          </Card>
        </aside>
      </div>

      <Modal
        open={confirmLogout}
        onClose={() => setConfirmLogout(false)}
        title={t("settings.signOutTitle")}
        description={t("settings.signOutBody")}
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setConfirmLogout(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            >
              {t("common.signOut")}
            </Button>
          </>
        }
      >
        <p className="text-sm muted">{session?.user?.email}</p>
      </Modal>

      <Modal
        open={securityOpen}
        onClose={() => setSecurityOpen(false)}
        title={t("settings.securityModalTitle")}
        description={t("settings.securityModalBody")}
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setSecurityOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              onClick={async () => {
                setSecurityError("");
                setSecurityBusy(true);
                try {
                  await updateSecurity({
                    otp_login_enabled: !session?.user?.otp_login_enabled,
                    current_password: currentPassword,
                  });
                  toast.success(t("settings.securityUpdated"));
                  setSecurityOpen(false);
                  setCurrentPassword("");
                } catch (err) {
                  setSecurityError(
                    err.message === "NETWORK_ERROR"
                      ? t("errors.network")
                      : err.message || t("errors.generic"),
                  );
                } finally {
                  setSecurityBusy(false);
                }
              }}
              loading={securityBusy}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div>
          <Label htmlFor="current-password">{t("settings.currentPassword")}</Label>
          <Input
            id="current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            placeholder="********"
          />
          <FieldError>{securityError}</FieldError>
        </div>
      </Modal>
    </div>
  );
}
