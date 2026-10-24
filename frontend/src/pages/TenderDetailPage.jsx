import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowLeft,
  CalendarClock,
  CalendarPlus,
  ExternalLink,
  FileText,
  Share2,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { useToast } from "../contexts/ToastContext";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Spinner";
import { Tabs } from "../components/ui/Tabs";
import { KebabMenu } from "../components/ui/Menu";
import { TenderDocumentsPanel } from "../components/tender/TenderDocumentsPanel";
import { TenderRequirementsPanel } from "../components/tender/TenderRequirementsPanel";
import { TenderChangesPanel } from "../components/tender/TenderChangesPanel";
import { TenderRecommendPanel } from "../components/tender/TenderRecommendPanel";
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
  "recommend",
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
        <Skeleton className="h-6 w-52" />
        <Skeleton className="h-24 w-full" />
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
                className="inline-flex items-center gap-2 rounded-lg border border-navy-200 px-4 py-2 text-sm font-semibold text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
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

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      toast.success(t("tenders.detail.shareCopied"));
    } catch {
      toast.error(t("errors.generic"));
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex min-w-0 items-center gap-1.5 text-[12px]">
        <Link
          to="/app/tenders"
          className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap font-medium text-navy-500 hover:text-navy-800 dark:text-navy-300 dark:hover:text-white"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("tenders.detail.breadcrumb")}
        </Link>
        <span className="text-navy-300">/</span>
        <span className="truncate text-navy-400">{tender.reference_number || tender.title}</span>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1
              title={tender.title}
              className="line-clamp-3 text-[21px] font-bold leading-[1.35] tracking-[-0.01em] text-navy-900 dark:text-white sm:text-[23px]"
            >
              {tender.title}
            </h1>
            {tender.is_sample ? <Badge tone="amber">{t("tenders.sampleBadge")}</Badge> : null}
          </div>
          {tender.authority || tender.reference_number ? (
            <p className="mt-1 text-[13px] muted">
              {[tender.authority, tender.reference_number].filter(Boolean).join(" · ")}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Button onClick={downloadCalendar}>
            <CalendarPlus className="h-4 w-4" />
            {t("tenders.detail.trackTender")}
          </Button>
          <Button variant="outline" onClick={share}>
            <Share2 className="h-4 w-4" />
            {t("tenders.detail.share")}
          </Button>
          <KebabMenu
            label={t("tenders.detail.moreActions")}
            items={[
              tender.source_url
                ? {
                    label: t("tenders.source"),
                    icon: ExternalLink,
                    onClick: () => window.open(tender.source_url, "_blank", "noopener,noreferrer"),
                  }
                : null,
              {
                label: t("common.exportCalendar"),
                icon: CalendarPlus,
                onClick: downloadCalendar,
              },
            ]}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px]">
        <span className="inline-flex items-center gap-1.5 font-medium text-teal-700 dark:text-teal-300">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-600" />
          {t(`tenders.statuses.${tender.status}`, { defaultValue: tender.status })}
        </span>
        {tender.reference_number ? <span className="chip">{tender.reference_number}</span> : null}
        {tender.deadline ? (
          <span className="inline-flex items-center gap-1.5 text-navy-500 dark:text-navy-300">
            <CalendarClock className="h-3.5 w-3.5 text-navy-400" />
            {t("tenders.deadline")}:{" "}
            <span className="font-medium text-navy-700 dark:text-navy-100">
              {formatDate(tender.deadline, currentLocale())}
            </span>
          </span>
        ) : null}
        <span className="inline-flex items-center gap-1.5 text-navy-500 dark:text-navy-300">
          <FileText className="h-3.5 w-3.5 text-navy-400" />
          {tender.document_count ?? 0} {t("dashboard.documents")}
        </span>
        {tender.source_url ? (
          <a
            href={tender.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 font-medium text-teal-700 hover:underline dark:text-teal-300"
          >
            {t("tenders.source")}
            <ExternalLink className="h-3 w-3" />
          </a>
        ) : null}
      </div>

      <div className="rounded-xl border border-navy-100 bg-white px-5 pt-3 dark:border-navy-800 dark:bg-navy-900">
        <Tabs
          ariaLabel={t("tenders.detail.sections")}
          value={activeTab}
          onChange={openTab}
          items={TABS.map((tab) => ({
            key: tab,
            label: t(`tenders.detail.${tab}`),
          }))}
        />
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
                  {t("tenders.detail.summaryLabel")}
                </p>
                <p className="mt-1 text-[13px] leading-6 text-navy-700 dark:text-navy-200">
                  {tender.description || t("tenders.noSummary")}
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg bg-navy-50 p-3 dark:bg-navy-800">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                    {t("tenders.detail.documentsLabel")}
                  </p>
                  <p className="mt-1 text-lg font-semibold text-navy-900 dark:text-white">
                    {tender.document_count ?? 0}
                  </p>
                </div>
                <div className="rounded-lg bg-navy-50 p-3 dark:bg-navy-800">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                    {t("tenders.savedLabel")}
                  </p>
                  <p className="mt-1 text-[13px] font-medium text-navy-900 dark:text-white">
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
              <div className="rounded-lg border border-dashed border-navy-200 p-4 dark:border-navy-700">
                <ShieldCheck className="h-5 w-5 text-teal-600" />
                <p className="mt-2 text-[13px] leading-6 muted">
                  {tender.source_url
                    ? t("tenders.detail.sourceBody")
                    : t(
                        tender.is_sample
                          ? "tenders.detail.sourceSample"
                          : "tenders.detail.sourceNotRecorded",
                      )}
                </p>
                {tender.source_url ? (
                  <a
                    href={tender.source_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="mt-2 inline-flex items-center gap-1 break-all text-xs font-semibold text-teal-700 hover:underline dark:text-teal-300"
                  >
                    {t("tenders.detail.sourceLink")}
                    <ExternalLink className="h-3 w-3 shrink-0" />
                  </a>
                ) : null}
                {tender.source_retrieved_at ? (
                  <p className="mt-3 text-xs font-medium text-navy-700 dark:text-navy-200">
                    {t("tenders.requirements.retrieved", {
                      date: formatDateTime(tender.source_retrieved_at, currentLocale()),
                    })}
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
      ) : activeTab === "recommend" ? (
        <TenderRecommendPanel tenderId={tenderId} />
      ) : (
        <Card>
          <CardContent className="py-10">
            <EmptyState
              icon={FileText}
              title={t("tenders.detail.unavailableTitle")}
              description={t("tenders.detail.unavailableBody")}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
