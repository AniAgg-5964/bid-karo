import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  CalendarClock,
  CalendarPlus,
  ExternalLink,
  FileText,
  Globe,
  History,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
} from "lucide-react";

import { api } from "../../lib/api";
import { currentLocale } from "../../i18n";
import { formatDate, formatDateTime } from "../../lib/utils";
import { Button } from "../ui/Button";
import { ProvenanceBadge } from "../ui/ProvenanceBadge";
import { sourceFreshness } from "../../lib/trust";

/**
 * The tender context header.
 *
 * It answers, before anything else: what is this, who issued it, when is it
 * due, when did we last check the source, and what is the one thing that is
 * still unresolved. A value that the record does not carry is left out or
 * labelled as unavailable. It is never filled in.
 */
export function TenderContextHeader({ tender, tenderId, onDownloadCalendar }) {
  const { t } = useTranslation();
  const [assessment, setAssessment] = useState(null);
  const [loadingAssessment, setLoadingAssessment] = useState(false);

  const freshness = sourceFreshness(tender);

  useEffect(() => {
    if (!tenderId) return;
    let active = true;
    setLoadingAssessment(true);
    api
      .get(`/tenders/${tenderId}/assessment`)
      .then((data) => {
        if (active) setAssessment(data);
      })
      .catch(() => {
        // The header stays useful without the assessment.
        if (active) setAssessment(null);
      })
      .finally(() => {
        if (active) setLoadingAssessment(false);
      });
    return () => {
      active = false;
    };
  }, [tenderId]);

  const eligibility = assessment?.eligibility || null;
  const blocking =
    eligibility?.items?.find((item) => item.gate === "fail") ||
    eligibility?.items?.find((item) => item.gate === "unknown") ||
    null;

  return (
    <header className="surface overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_auto]">
        <div className="space-y-4 p-5 sm:p-6">
          <div className="flex items-start gap-3.5">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300">
              <FileText className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h1 className="text-xl font-semibold leading-snug tracking-tight text-navy-900 dark:text-white sm:text-2xl">
                {tender.title}
              </h1>
              <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm muted">
                {tender.authority ? (
                  <span className="inline-flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-navy-400" aria-hidden="true" />
                    {tender.authority}
                  </span>
                ) : null}
                {tender.reference_number ? (
                  <span className="tabular inline-flex items-center gap-1.5">
                    <span className="text-navy-400">·</span>
                    {tender.reference_number}
                  </span>
                ) : null}
              </p>
            </div>
          </div>

          {/* The decision context: the facts a reader needs first. */}
          <dl className="grid gap-x-6 gap-y-3 border-t border-navy-100 pt-4 sm:grid-cols-2 xl:grid-cols-4 dark:border-navy-800">
            <Fact
              icon={CalendarClock}
              label={t("tenders.deadline")}
              value={tender.deadline ? formatDate(tender.deadline, currentLocale()) : null}
              unavailableLabel={t("tenders.context.unavailable")}
            />
            <Fact
              icon={Globe}
              label={t("tenders.context.source")}
              value={
                tender.source_url ? (
                  <a
                    href={tender.source_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1 break-all font-medium text-cobalt-700 hover:underline dark:text-cobalt-300"
                  >
                    {t("tenders.context.openSource")}
                    <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                  </a>
                ) : null
              }
              unavailableLabel={t("tenders.context.noSource")}
            />
            <Fact
              icon={History}
              label={t("tenders.context.lastCheck")}
              value={
                tender.source_retrieved_at
                  ? formatDateTime(tender.source_retrieved_at, currentLocale())
                  : null
              }
              unavailableLabel={
                tender.source_url ? t("trust.source.neverChecked") : t("tenders.context.noSource")
              }
              badge={
                <ProvenanceBadge
                  state="source_referenced"
                  tone={freshness.tone}
                  icon={freshness.tone === "review" ? "shield-question" : "link"}
                  label={t(freshness.labelKey)}
                  size="sm"
                />
              }
            />
            <Fact
              icon={FileText}
              label={t("tenders.context.documents")}
              value={
                tender.document_count
                  ? t("tenders.context.documentCount", { count: tender.document_count })
                  : null
              }
              unavailableLabel={t("tenders.context.noDocuments")}
            />
          </dl>
        </div>

        {/* The one thing that still needs a person. */}
        <div className="flex flex-col justify-between gap-3 border-t border-navy-100 bg-stone-50/60 p-5 lg:w-[22rem] lg:border-l lg:border-t-0 dark:border-navy-800 dark:bg-navy-950/30">
          <div>
            <p className="eyebrow">{t("tenders.context.blocking")}</p>
            {loadingAssessment ? (
              <p className="mt-2 text-sm muted">{t("tenders.context.checking")}</p>
            ) : blocking ? (
              <div className="mt-2 space-y-2">
                <p className="text-sm font-semibold leading-5 text-navy-900 dark:text-white">
                  {blocking.title}
                </p>
                {blocking.reason ? (
                  <p className="text-xs leading-5 muted">{blocking.reason}</p>
                ) : null}
                <ProvenanceBadge
                  state={blocking.gate === "fail" ? "rejected" : "needs_review"}
                  tone={blocking.gate === "fail" ? "blocked" : "review"}
                  icon={blocking.gate === "fail" ? "shield-alert" : "shield-question"}
                  label={t(`tenders.eligibility.gates.${blocking.gate}`)}
                />
                <a
                  href={`/app/tenders/${tenderId}?tab=eligibility`}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-cobalt-700 hover:underline dark:text-cobalt-300"
                >
                  {t("tenders.context.reviewEvidence")}
                  <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              </div>
            ) : (
              <p className="mt-2 flex items-start gap-1.5 text-sm leading-5 text-navy-700 dark:text-navy-200">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
                {t("tenders.context.nothingBlocking")}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={onDownloadCalendar}>
              <CalendarPlus className="h-3.5 w-3.5" />
              {t("common.exportCalendar")}
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}

function Fact({ icon: Icon, label, value, unavailableLabel, badge }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-navy-500 dark:text-navy-300">
        <Icon className="h-3 w-3" aria-hidden="true" />
        {label}
      </dt>
      <dd className="mt-1 text-sm font-medium text-navy-900 dark:text-white">
        {value || (
          <span className="font-normal text-navy-400">{unavailableLabel || "—"}</span>
        )}
        {badge ? <div className="mt-1.5">{badge}</div> : null}
      </dd>
    </div>
  );
}
