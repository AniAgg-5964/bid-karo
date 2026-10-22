import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, TriangleAlert } from "lucide-react";

import { api } from "../lib/api";
import { useToast } from "../contexts/ToastContext";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton } from "../components/ui/Spinner";
import { TenderDocumentsPanel } from "../components/tender/TenderDocumentsPanel";
import { TenderRequirementsPanel } from "../components/tender/TenderRequirementsPanel";
import { TenderChangesPanel } from "../components/tender/TenderChangesPanel";
import { TenderRecommendPanel } from "../components/tender/TenderRecommendPanel";
import { TenderContextHeader } from "../components/tender/TenderContextHeader";
import { WorkbenchTabs } from "../components/tender/WorkbenchTabs";
import {
  TenderEligibilityPanel,
  TenderLegalPanel,
  TenderScorePanel,
  TenderTasksPanel,
} from "../components/tender/TenderAssessmentPanels";

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
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-10 w-full" />
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
              <Link to="/app/tenders">
                <Button variant="outline">
                  <ArrowLeft className="h-4 w-4" />
                  {t("tenders.title")}
                </Button>
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
      <nav aria-label={t("tenders.detail.breadcrumb")} className="flex items-center gap-2 text-xs muted">
        <Link to="/app/tenders" className="hover:text-teal-700">
          {t("tenders.detail.breadcrumb")}
        </Link>
        <span aria-hidden="true">/</span>
        <span className="truncate">{tender.reference_number || tender.title}</span>
      </nav>

      <TenderContextHeader
        tender={tender}
        tenderId={tenderId}
        onDownloadCalendar={downloadCalendar}
      />

      <WorkbenchTabs active={activeTab} onChange={openTab} />

      {activeTab === "overview" ? (
        <TenderOverview tender={tender} tenderId={tenderId} onOpenTab={openTab} />
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
        <TenderChangesPanel tenderId={tenderId} tender={tender} />
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
              icon={TriangleAlert}
              title={t("tenders.detail.unavailableTitle")}
              description={t("tenders.detail.unavailableBody")}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* The overview: what the tender is, and what to do about it next. */
function TenderOverview({ tender, tenderId, onOpenTab }) {
  const { t } = useTranslation();

  return (
    <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
      <Card>
        <CardContent className="space-y-4 p-5 sm:p-6">
          <div>
            <p className="eyebrow">{t("tenders.detail.summaryLabel")}</p>
            <p className="mt-1.5 text-sm leading-6 text-navy-700 dark:text-navy-200">
              {tender.description || t("tenders.noSummary")}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="surface-quiet p-3.5">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-navy-400">
                {t("tenders.detail.documentsLabel")}
              </p>
              <p className="tabular mt-1 text-lg font-semibold text-navy-900 dark:text-white">
                {tender.document_count ?? 0}
              </p>
            </div>
            <div className="surface-quiet p-3.5">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-navy-400">
                {t("tenders.savedLabel")}
              </p>
              <p className="mt-1 text-sm font-medium text-navy-900 dark:text-white">
                {t("tenders.context.docsLabel")}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 border-t border-navy-100 pt-4 dark:border-navy-800">
            <Button variant="outline" size="sm" onClick={() => onOpenTab("requirements")}>
              {t("tenders.detail.requirements")}
            </Button>
            <Button variant="outline" size="sm" onClick={() => onOpenTab("eligibility")}>
              {t("tenders.detail.eligibility")}
            </Button>
            <Button variant="outline" size="sm" onClick={() => onOpenTab("documents")}>
              {t("tenders.detail.documents")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-5 sm:p-6">
          <p className="eyebrow">{t("tenders.detail.sourceTitle")}</p>
          {tender.source_url ? (
            <div className="space-y-2">
              <p className="text-sm leading-6 muted">{t("tenders.detail.sourceBody")}</p>
              <a
                href={tender.source_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 break-all text-xs font-semibold text-cobalt-700 hover:underline dark:text-cobalt-300"
              >
                {t("tenders.detail.sourceLink")}
              </a>
              {tender.source_retrieved_at ? (
                <p className="text-xs font-medium text-navy-700 dark:text-navy-200">
                  {t("tenders.requirements.retrieved", { date: tender.source_retrieved_at })}
                </p>
              ) : (
                <p className="text-xs font-medium text-amber-700 dark:text-amber-300">
                  {t("trust.source.neverChecked")}
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm leading-6 muted">
              {t(
                tender.is_sample
                  ? "tenders.detail.sourceSample"
                  : "tenders.detail.sourceNotRecorded",
              )}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
