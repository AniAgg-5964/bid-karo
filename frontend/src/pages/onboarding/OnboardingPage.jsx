import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  FileCheck2,
  LogOut,
  Plus,
  Rocket,
  Sparkles,
  UploadCloud,
} from "lucide-react";

import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { api } from "../../lib/api";
import { companyToForm, formToPayload } from "../../lib/companyForm";
import {
  CompanyBasicsFields,
  CompanyCapabilityFields,
  CompanyPreferenceFields,
} from "../../components/company/CompanyFields";
import { DocumentUploadModal } from "../../components/documents/DocumentUploadModal";
import { LanguageSwitch } from "../../components/LanguageSwitch";
import { Logo } from "../../components/Logo";
import { ThemeToggle } from "../../components/ThemeToggle";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Progress } from "../../components/ui/Progress";
import { cn, formatBytes } from "../../lib/utils";

const STEPS = ["company", "capabilities", "evidence", "review"];

export function OnboardingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const toast = useToast();
  const { session, updateCompany, logout } = useAuth();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(() => companyToForm(session.company));
  const [documents, setDocuments] = useState([]);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const stepKey = STEPS[step];
  const isLast = step === STEPS.length - 1;

  const loadDocuments = async () => {
    try {
      const data = await api.get("/documents?limit=100");
      setDocuments(data.items || []);
    } catch {
      // The evidence library is optional at this stage; surface errors on upload instead.
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const completeness = useMemo(() => session.company?.profile_completeness || 0, [session.company]);

  const onChange = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const onChangePreference = (field, value) =>
    setForm((current) => ({
      ...current,
      preferences: { ...current.preferences, [field]: value },
    }));

  const save = async (extra = {}) => {
    setError("");
    setSaving(true);
    try {
      const company = await api.patch("/companies/me", {
        ...formToPayload(form),
        ...extra,
      });
      updateCompany(company);
      return company;
    } catch (err) {
      const message = err.message === "NETWORK_ERROR" ? t("errors.network") : err.message;
      setError(message || t("onboarding.saveFailed"));
      throw err;
    } finally {
      setSaving(false);
    }
  };

  const goNext = async () => {
    if (step === 0 && !form.name.trim()) {
      setError(t("onboarding.saveFailed"));
      return;
    }
    try {
      await save();
      setStep((current) => Math.min(current + 1, STEPS.length - 1));
    } catch {
      // Error is displayed above the form.
    }
  };

  const finish = async () => {
    try {
      await save({ onboarding_completed: true });
      toast.success(t("onboarding.reviewSubtitle"));
      navigate("/app/dashboard", { replace: true });
    } catch {
      // Error is displayed above the form.
    }
  };

  const skip = async () => {
    try {
      await save({ onboarding_completed: true });
      navigate("/app/dashboard", { replace: true });
    } catch {
      // Error is displayed above the form.
    }
  };

  return (
    <div className="min-h-screen bg-mist dark:bg-navy-950">
      <header className="border-b border-navy-100 bg-white dark:border-navy-800 dark:bg-navy-900">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Logo />
          <div className="flex items-center gap-2">
            <LanguageSwitch compact />
            <ThemeToggle />
            <button
              type="button"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
              className="hidden items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-medium text-navy-500 hover:bg-navy-50 hover:text-navy-800 dark:hover:bg-navy-800 sm:inline-flex dark:text-navy-300"
            >
              <LogOut className="h-3.5 w-3.5" />
              {t("common.signOut")}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
        <div className="mb-8 max-w-2xl">
          <p className="eyebrow">{t("onboarding.kicker")}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-navy-900 dark:text-white sm:text-3xl">
            {t("onboarding.title")}
          </h1>
          <p className="mt-2 text-sm muted">{t("onboarding.subtitle")}</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
          <aside>
            <div className="surface p-4">
              <p className="mb-3 text-xs font-semibold text-navy-500 dark:text-navy-300">
                {t("onboarding.stepOf", { current: step + 1, total: STEPS.length })}
              </p>
              <Progress value={((step + 1) / STEPS.length) * 100} label={t("onboarding.completeness")} />
              <ol className="mt-5 space-y-1">
                {STEPS.map((key, index) => {
                  const active = index === step;
                  const complete = index < step;
                  return (
                    <li key={key}>
                      <button
                        type="button"
                        onClick={() => (complete ? setStep(index) : undefined)}
                        disabled={!complete && !active}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition",
                          active
                            ? "bg-teal-50 font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                            : complete
                              ? "text-navy-700 hover:bg-navy-50 dark:text-navy-200 dark:hover:bg-navy-800"
                              : "cursor-default text-navy-400",
                        )}
                      >
                        <span
                          className={cn(
                            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold",
                            active
                              ? "border-teal-600 bg-teal-600 text-white"
                              : complete
                                ? "border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-300"
                                : "border-navy-200 text-navy-400 dark:border-navy-700",
                          )}
                        >
                          {complete ? <Check className="h-3.5 w-3.5" /> : index + 1}
                        </span>
                        {t(`onboarding.steps.${key}`)}
                      </button>
                    </li>
                  );
                })}
              </ol>
            </div>

            <button
              type="button"
              onClick={skip}
              disabled={saving}
              className="mt-3 w-full rounded-lg px-3 py-2 text-xs font-medium text-navy-500 hover:bg-white hover:text-navy-800 dark:hover:bg-navy-900 dark:hover:text-white dark:text-navy-300"
            >
              {t("common.skip")}
            </button>
          </aside>

          <Card className="overflow-hidden">
            <div className="border-b border-navy-100 px-5 py-5 dark:border-navy-800 sm:px-7">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                  {stepKey === "company" ? (
                    <Building2 className="h-5 w-5" />
                  ) : stepKey === "capabilities" ? (
                    <Sparkles className="h-5 w-5" />
                  ) : stepKey === "evidence" ? (
                    <FileCheck2 className="h-5 w-5" />
                  ) : (
                    <Rocket className="h-5 w-5" />
                  )}
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-navy-900 dark:text-white">
                    {t(`onboarding.${stepKey}Title`)}
                  </h2>
                  <p className="mt-1 text-sm muted">{t(`onboarding.${stepKey}Subtitle`)}</p>
                </div>
              </div>
            </div>

            <div className="px-5 py-6 sm:px-7">
              {stepKey === "company" ? (
                <CompanyBasicsFields form={form} onChange={onChange} />
              ) : null}

              {stepKey === "capabilities" ? (
                <div className="space-y-7">
                  <CompanyCapabilityFields form={form} onChange={onChange} />
                  <div className="border-t border-navy-100 pt-6 dark:border-navy-800">
                    <h3 className="mb-4 text-sm font-semibold text-navy-900 dark:text-white">
                      {t("company.preferences")}
                    </h3>
                    <CompanyPreferenceFields form={form} onChangePreference={onChangePreference} />
                  </div>
                </div>
              ) : null}

              {stepKey === "evidence" ? (
                <div>
                  <div className="rounded-xl border border-dashed border-navy-200 px-5 py-7 text-center dark:border-navy-700">
                    <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                      <UploadCloud className="h-5 w-5" />
                    </div>
                    <p className="text-sm font-medium text-navy-800 dark:text-navy-100">
                      {documents.length
                        ? t("onboarding.uploaded", { count: documents.length })
                        : t("onboarding.noDocs")}
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-4"
                      onClick={() => setUploadOpen(true)}
                    >
                      <Plus className="h-3.5 w-3.5" />
                      {documents.length ? t("onboarding.addAnother") : t("onboarding.uploadFirst")}
                    </Button>
                  </div>

                  {documents.length ? (
                    <ul className="mt-4 divide-y divide-navy-100 rounded-xl border border-navy-100 dark:divide-navy-800 dark:border-navy-800">
                      {documents.slice(0, 5).map((document) => (
                        <li key={document.id} className="flex items-center gap-3 px-4 py-3">
                          <FileCheck2 className="h-4 w-4 text-teal-600" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-navy-900 dark:text-white">
                              {document.title}
                            </p>
                            <p className="text-xs muted">
                              {t(`documents.types.${document.document_type}`)} ·{" "}
                              {formatBytes(document.size_bytes)}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  <p className="mt-5 rounded-lg bg-navy-50 px-3 py-2.5 text-xs leading-5 muted dark:bg-navy-800">
                    {t("onboarding.evidenceNote")}
                  </p>
                </div>
              ) : null}

              {stepKey === "review" ? (
                <div className="space-y-5">
                  <div className="rounded-xl bg-navy-50 p-4 dark:bg-navy-800">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-navy-800 dark:text-navy-100">
                        {t("onboarding.completeness")}
                      </span>
                      <span className="font-bold text-teal-700 dark:text-teal-300">{completeness}%</span>
                    </div>
                    <Progress value={completeness} className="mt-2" label={t("onboarding.completeness")} />
                    {completeness < 100 ? (
                      <p className="mt-2 text-xs muted">{t("onboarding.missing")}</p>
                    ) : null}
                  </div>

                  <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("auth.companyName")}</dt>
                      <dd className="mt-0.5 font-medium text-navy-900 dark:text-white">{form.name || "—"}</dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("company.legalName")}</dt>
                      <dd className="mt-0.5 text-navy-800 dark:text-navy-100">{form.legal_name || "—"}</dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("company.sectors")}</dt>
                      <dd className="mt-0.5 text-navy-800 dark:text-navy-100">
                        {form.sectors.length ? form.sectors.join(", ") : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("company.regions")}</dt>
                      <dd className="mt-0.5 text-navy-800 dark:text-navy-100">
                        {form.regions.length ? form.regions.join(", ") : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("nav.documents")}</dt>
                      <dd className="mt-0.5 text-navy-800 dark:text-navy-100">{documents.length}</dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-navy-500 dark:text-navy-300">{t("company.products")}</dt>
                      <dd className="mt-0.5 text-navy-800 dark:text-navy-100">
                        {form.products_services.length ? form.products_services.join(", ") : "—"}
                      </dd>
                    </div>
                  </dl>

                  <p className="text-xs muted">{t("onboarding.subtitle")}</p>
                </div>
              ) : null}

              {error ? (
                <p className="mt-5 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
                  {error}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col-reverse gap-2 border-t border-navy-100 px-5 py-4 dark:border-navy-800 sm:flex-row sm:items-center sm:justify-between sm:px-7">
              <Button
                variant="ghost"
                onClick={() => setStep((current) => Math.max(current - 1, 0))}
                disabled={step === 0 || saving}
              >
                <ArrowLeft className="h-4 w-4" />
                {t("common.back")}
              </Button>
              <div className="flex items-center gap-2">
                {stepKey === "evidence" ? (
                  <Button variant="outline" onClick={goNext} disabled={saving}>
                    {t("common.skip")}
                  </Button>
                ) : null}
                {isLast ? (
                  <Button onClick={finish} loading={saving}>
                    {t("onboarding.enterDashboard")}
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button onClick={goNext} loading={saving}>
                    {t("common.next")}
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>
      </main>

      <DocumentUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => loadDocuments()}
      />
    </div>
  );
}
