import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowLeft,
  CalendarClock,
  CalendarPlus,
  ExternalLink,
  FileText,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { useToast } from "../contexts/ToastContext";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Spinner";
import { TenderDocumentsPanel } from "../components/tender/TenderDocumentsPanel";
import { TenderRequirementsPanel } from "../components/tender/TenderRequirementsPanel";
import { TenderChangesPanel } from "../components/tender/TenderChangesPanel";
import {
  TenderEligibilityPanel,
  TenderLegalPanel,
  TenderScorePanel,
  TenderTasksPanel,
} from "../components/tender/TenderAssessmentPanels";
import { formatDate, formatDateTime } from "../lib/utils";

const TABS = [
  "overview",
  "requirements",
  "documents",
  "score",
  "eligibility",
  "compliance",
  "legal",
  "changes",
  "tasks",
  "obligations",
];

export function TenderDetailPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const { tenderId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = TABS.includes(searchParams.get("tab")) ? searchParams.get("tab") : "overview";
  const [tender, setTender] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [requirementsKey, setRequirementsKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api
      .get(`/tenders/${tenderId}`)
      .then((data) => {
        if (active) setTender(data);
      })
      .catch((err) => {
        if (active) setError(err.status === 404 ? "not_found" : err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [tenderId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-52" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !tender) {
    return (
      <Card>
        <CardContent className="py-12">
          <EmptyState
            icon={TriangleAlert}
            title={t("tenders.notFound")}
            description={error === "not_found" ? t("tenders.notFoundBody") : error}
            action={
              <Link
                to="/app/tenders"
                className="inline-flex items-center gap-2 rounded-xl border border-navy-200 px-4 py-2 text-sm font-semibold text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
              >
                <ArrowLeft className="h-4 w-4" />
                {t("tenders.title")}
              </Link>
            }
          />
        </CardContent>
      </Card>
    );
  }

  const openTab = (tab) => setSearchParams({ tab });

  const downloadCalendar = async () => {
    try {
      await api.download(`/tenders/${tenderId}/calendar.ics`, `bidkaro-tender-${tenderId}.ics`);
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-xs muted">
        <Link to="/app/tenders" className="hover:text-teal-700">
          {t("tenders.detail.breadcrumb")}
        </Link>
        <span>/</span>
        <span className="truncate">{tender.reference_number || tender.title}</span>
      </div>

      <Card>
        <CardContent className="space-y-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 items-start gap-4">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                <FileText className="h-6 w-6" />
              </span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-xl font-semibold tracking-tight text-navy-900 dark:text-white sm:text-2xl">
                    {tender.title}
                  </h1>
                  <StatusBadge
                    status={tender.status}
                    label={t(`tenders.statuses.${tender.status}`, { defaultValue: tender.status })}
                  />
                  {tender.is_sample ? (
                    <Badge tone="amber">{t("tenders.sampleBadge")}</Badge>
                  ) : null}
                </div>
                <p className="mt-1 text-sm muted">
                  {[tender.authority, tender.reference_number].filter(Boolean).join(" · ") || "—"}
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={downloadCalendar}>
                <CalendarPlus className="h-3.5 w-3.5" />
                {t("common.exportCalendar")}
              </Button>
              {tender.source_url ? (
                <a
                  href={tender.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-navy-200 px-3.5 py-2 text-xs font-semibold text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
                >
                  {t("tenders.source")}
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : null}
            </div>
          </div>

          <div className="grid gap-4 border-t border-navy-100 pt-4 dark:border-navy-800 sm:grid-cols-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">{t("tenders.authority")}</p>
              <p className="mt-1 text-sm font-medium text-navy-900 dark:text-white">{tender.authority || "—"}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">{t("tenders.reference")}</p>
              <p className="mt-1 text-sm font-medium text-navy-900 dark:text-white">
                {tender.reference_number || "—"}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">{t("tenders.deadline")}</p>
              <p className="mt-1 inline-flex items-center gap-1.5 text-sm font-medium text-navy-900 dark:text-white">
                <CalendarClock className="h-3.5 w-3.5 text-navy-400" />
                {tender.deadline ? formatDate(tender.deadline, currentLocale()) : "—"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-1 rounded-xl border border-navy-100 bg-white p-1 dark:border-navy-800 dark:bg-navy-900">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => openTab(tab)}
            className={
              activeTab === tab
                ? "shrink-0 rounded-lg bg-teal-50 px-3.5 py-2 text-xs font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                : "shrink-0 rounded-lg px-3.5 py-2 text-xs font-medium text-navy-500 hover:bg-navy-50 hover:text-navy-800 dark:hover:bg-navy-800 dark:hover:text-white"
            }
          >
            {t(`tenders.detail.${tab}`)}
          </button>
        ))}
      </div>

      {activeTab === "overview" ? (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <Card>
            <CardHeader>
              <CardTitle>{t("tenders.detail.keyInfo")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                  {t("dashboard.subtitle")}
                </p>
                <p className="mt-1 text-sm leading-6 text-navy-700 dark:text-navy-200">
                  {tender.description || t("tenders.noSummary")}
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-navy-50 p-3 dark:bg-navy-800">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                    {t("documents.title")}
                  </p>
                  <p className="mt-1 text-lg font-semibold text-navy-900 dark:text-white">
                    {tender.document_count ?? 0}
                  </p>
                </div>
                <div className="rounded-xl bg-navy-50 p-3 dark:bg-navy-800">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                    {t("tenders.savedLabel")}
                  </p>
                  <p className="mt-1 text-sm font-medium text-navy-900 dark:text-white">
                    {formatDateTime(tender.created_at, currentLocale())}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("tenders.detail.sourceTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="pt-3">
              <div className="rounded-xl border border-dashed border-navy-200 p-4 dark:border-navy-700">
                <ShieldCheck className="h-5 w-5 text-teal-700" />
                <p className="mt-2 text-sm leading-6 muted">{t("tenders.detail.sourceBody")}</p>
                {tender.source_retrieved_at ? (
                  <p className="mt-3 text-xs font-medium text-navy-700 dark:text-navy-200">
                    {formatDateTime(tender.source_retrieved_at, currentLocale())}
                  </p>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : activeTab === "documents" ? (
        <TenderDocumentsPanel
          tenderId={tenderId}
          isSample={Boolean(tender.is_sample)}
          onExtracted={() => setRequirementsKey((value) => value + 1)}
        />
      ) : activeTab === "requirements" ? (
        <TenderRequirementsPanel tenderId={tenderId} refreshKey={requirementsKey} />
      ) : activeTab === "score" ? (
        <TenderScorePanel tenderId={tenderId} onOpenTab={openTab} />
      ) : activeTab === "eligibility" ? (
        <TenderEligibilityPanel tenderId={tenderId} onOpenTab={openTab} />
      ) : activeTab === "compliance" ? (
        <TenderTasksPanel tenderId={tenderId} complianceOnly phase="pre_award" />
      ) : activeTab === "legal" ? (
        <TenderLegalPanel tenderId={tenderId} />
      ) : activeTab === "changes" ? (
        <TenderChangesPanel tenderId={tenderId} />
      ) : activeTab === "tasks" ? (
        <TenderTasksPanel tenderId={tenderId} phase="pre_award" />
      ) : activeTab === "obligations" ? (
        <TenderTasksPanel tenderId={tenderId} phase="post_award" />
      ) : (
        <Card>
          <CardContent className="py-10">
            <EmptyState
              icon={FileText}
              title={t("tenders.detail.pendingTitle")}
              description={t("tenders.detail.pendingBody")}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
