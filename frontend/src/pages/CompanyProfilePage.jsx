import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Building2, Save, Sparkles, Target, TrendingUp } from "lucide-react";

import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { companyToForm, formToPayload } from "../lib/companyForm";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Progress } from "../components/ui/Progress";
import {
  CompanyBasicsFields,
  CompanyCapabilityFields,
  CompanyPreferenceFields,
} from "../components/company/CompanyFields";

export function CompanyProfilePage() {
  const { t } = useTranslation();
  const toast = useToast();
  const { session, updateCompany } = useAuth();
  const [form, setForm] = useState(() => companyToForm(session?.company));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [completeness, setCompleteness] = useState(session?.company?.profile_completeness || 0);

  const onChange = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const onChangePreference = (field, value) =>
    setForm((current) => ({
      ...current,
      preferences: { ...current.preferences, [field]: value },
    }));

  const save = async (event) => {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const company = await api.patch("/companies/me", formToPayload(form));
      updateCompany(company);
      setCompleteness(company.profile_completeness);
      setForm(companyToForm(company));
      toast.success(t("company.saved"));
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-6">
      <PageHeader
        title={t("company.title")}
        description={t("company.subtitle")}
        actions={
          <Button type="submit" loading={saving}>
            <Save className="h-4 w-4" />
            {saving ? t("common.saving") : t("company.saveChanges")}
          </Button>
        }
      />

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1fr_300px]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("company.basics")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              <CompanyBasicsFields form={form} onChange={onChange} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("company.capabilities")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              <CompanyCapabilityFields form={form} onChange={onChange} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("company.preferences")}</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              <CompanyPreferenceFields form={form} onChangePreference={onChangePreference} />
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card className="xl:sticky xl:top-24">
            <CardHeader>
              <CardTitle>{t("company.completeness")}</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <div className="flex items-end justify-between">
                <p className="text-3xl font-semibold tracking-tight text-navy-900 dark:text-white">
                  {completeness}%
                </p>
                <TrendingUp className="h-5 w-5 text-teal-600" />
              </div>
              <Progress value={completeness} className="mt-3" label={t("company.completeness")} />
              <p className="mt-2 text-xs leading-5 muted">{t("company.completenessHint")}</p>
              {completeness < 100 ? (
                <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                  {t("company.missingFields")}
                </p>
              ) : null}
            </CardContent>
          </Card>
        </aside>
      </div>

      <div className="flex justify-end border-t border-navy-100 pt-4 dark:border-navy-800">
        <Button type="submit" loading={saving}>
          <Save className="h-4 w-4" />
          {saving ? t("common.saving") : t("company.saveChanges")}
        </Button>
      </div>
    </form>
  );
}
