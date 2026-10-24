import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Check,
  ExternalLink,
  FileSearch,
  ListChecks,
  Scale,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import { api } from "../../lib/api";
import { currentLocale } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { Badge, StatusBadge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Skeleton } from "../ui/Spinner";
import { cn, formatDateTime } from "../../lib/utils";

const GROUNDING_TONE = {
  grounded: "teal",
  verified: "teal",
  unverified: "amber",
  needs_review: "amber",
  rejected: "neutral",
};

function JobSteps({ job }) {
  const { t } = useTranslation();
  if (!job) return null;
  return (
    <div className="rounded-xl border border-navy-100 bg-white p-4 dark:border-navy-800 dark:bg-navy-900">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-navy-900 dark:text-white">
          {t("tenders.recommend.jobTitle")}
        </p>
        <StatusBadge
          status={job.status}
          label={t(`tenders.recommend.jobStatus.${job.status}`, { defaultValue: job.status })}
        />
      </div>
      <ul className="mt-3 space-y-1.5">
        {(job.steps || []).map((step) => (
          <li key={step.key} className="flex items-start gap-2 text-xs">
            <span
              className={cn(
                "mt-0.5 h-2 w-2 shrink-0 rounded-full",
                step.status === "done"
                  ? "bg-teal-600"
                  : step.status === "failed"
                    ? "bg-red-500"
                    : step.status === "skipped"
                      ? "bg-navy-300 dark:bg-navy-700"
                      : "bg-amber-500",
              )}
            />
            <span className="min-w-0">
              <span className="font-medium text-navy-800 dark:text-navy-100">{step.label}</span>
              <span className="ml-2 text-muted">
                {t(`tenders.recommend.stepStatus.${step.status}`, { defaultValue: step.status })}
              </span>
              {step.error ? (
                <span className="mt-0.5 block text-amber-700 dark:text-amber-300">{step.error}</span>
              ) : null}
              {step.summary && Object.keys(step.summary).length ? (
                <span className="mt-0.5 block text-muted">
                  {Object.entries(step.summary)
                    .map(
                      ([key, value]) =>
                        `${key}: ${
                          value && typeof value === "object"
                            ? Object.entries(value)
                                .map(([inner, innerValue]) => `${inner} ${innerValue}`)
                                .join(", ")
                            : value
                        }`,
                    )
                    .join(" · ")}
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TenderRecommendPanel({ tenderId }) {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const locale = i18n.language === "hi" ? "hi-IN" : "en-IN";
  const [job, setJob] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [showUngrounded, setShowUngrounded] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [jobResponse, recResponse] = await Promise.all([
        api.get(`/analysis/tenders/${tenderId}`),
        api.get(`/analysis/tenders/${tenderId}/recommendations`),
      ]);
      setJob(jobResponse || null);
      setRecommendations(recResponse.items || []);
    } catch (err) {
      setError(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setLoading(false);
    }
  }, [tenderId, t]);

  useEffect(() => {
    load();
  }, [load]);

  const grounded = useMemo(
    () => recommendations.filter((item) => item.grounding_status === "grounded"),
    [recommendations],
  );
  const ungrounded = useMemo(
    () => recommendations.filter((item) => item.grounding_status !== "grounded"),
    [recommendations],
  );

  const start = async () => {
    setStarting(true);
    try {
      const started = await api.post(`/analysis/tenders/${tenderId}`, {});
      setJob(started);
      toast.success(t("tenders.recommend.queued"));
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setStarting(false);
    }
  };

  const apply = async (item) => {
    setBusyId(item.id);
    try {
      await api.post(`/analysis/tenders/${tenderId}/recommendations/${item.id}/apply`, {});
      toast.success(t("tenders.recommend.applied"));
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle>{t("tenders.recommend.title")}</CardTitle>
              <CardDescription>{t("tenders.recommend.subtitle")}</CardDescription>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button size="sm" variant="outline" onClick={load} loading={loading}>
                {t("common.refresh")}
              </Button>
              <Button size="sm" onClick={start} loading={starting}>
                <Sparkles className="h-3.5 w-3.5" />
                {t("tenders.recommend.run")}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-3">
          {error ? (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </div>
          ) : null}
          {job ? <JobSteps job={job} /> : null}
          <p className="text-xs leading-5 muted">{t("tenders.recommend.note")}</p>
        </CardContent>
      </Card>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : grounded.length ? (
        <div className="space-y-3">
          {grounded.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-navy-100 bg-white p-4 dark:border-navy-800 dark:bg-navy-900"
            >
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-navy-900 dark:text-white">{item.title}</h3>
                <Badge tone={GROUNDING_TONE[item.grounding_status] || "neutral"}>
                  {t(`tenders.recommend.grounding.${item.grounding_status}`, {
                    defaultValue: item.grounding_status,
                  })}
                </Badge>
                <Badge tone="neutral">
                  {t(`tenders.recommend.kind.${item.kind}`, { defaultValue: item.kind })}
                </Badge>
              </div>
              <p className="mt-2 text-sm leading-6 text-navy-700 dark:text-navy-200">{item.claim}</p>
              {item.action ? (
                <div className="mt-3 rounded-lg bg-navy-50 p-3 dark:bg-navy-800">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-navy-400">
                    {t("tenders.recommend.action")}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-navy-800 dark:text-navy-100">{item.action}</p>
                  {item.acceptance_criteria ? (
                    <p className="mt-2 text-xs leading-5 muted">
                      <span className="font-semibold">{t("tenders.recommend.acceptance")}:</span>{" "}
                      {item.acceptance_criteria}
                    </p>
                  ) : null}
                  <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs muted">
                    {item.suggested_owner ? (
                      <span>
                        {t("tenders.recommend.owner")}: {item.suggested_owner}
                      </span>
                    ) : null}
                    {item.suggested_due_at ? (
                      <span>
                        {t("tenders.recommend.due")}:{" "}
                        {formatDateTime(item.suggested_due_at, locale)}
                      </span>
                    ) : null}
                    {item.requirement_refs?.length ? (
                      <span>
                        {t("tenders.recommend.clauses")}: {item.requirement_refs.join(", ")}
                      </span>
                    ) : null}
                  </p>
                </div>
              ) : null}
              {item.dropped_claims?.length ? (
                <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                  {t("tenders.recommend.dropped", { count: item.dropped_claims.length })}
                </p>
              ) : null}
              <div className="mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => apply(item)}
                  loading={busyId === item.id}
                >
                  <ListChecks className="h-3.5 w-3.5" />
                  {t("tenders.recommend.addToChecklist")}
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={FileSearch}
              title={t("tenders.recommend.emptyTitle")}
              description={t("tenders.recommend.emptyBody")}
            />
          </CardContent>
        </Card>
      )}

      {ungrounded.length ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle>{t("tenders.recommend.ungroundedTitle")}</CardTitle>
              <Badge tone="amber">{ungrounded.length}</Badge>
            </div>
            <CardDescription>{t("tenders.recommend.ungroundedBody")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 pt-3">
            <Button size="sm" variant="ghost" onClick={() => setShowUngrounded((value) => !value)}>
              {showUngrounded ? t("tenders.recommend.hideUngrounded") : t("tenders.recommend.showUngrounded")}
            </Button>
            {showUngrounded
              ? ungrounded.map((item) => (
                  <article
                    key={item.id}
                    className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 dark:border-amber-900 dark:bg-amber-950/30"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-navy-900 dark:text-white">{item.title}</p>
                      <Badge tone="amber">
                        {t(`tenders.recommend.grounding.${item.grounding_status}`, {
                          defaultValue: item.grounding_status,
                        })}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-navy-700 dark:text-navy-200">
                      {item.claim}
                    </p>
                    {item.grounding_note ? (
                      <p className="mt-1 text-xs text-amber-800 dark:text-amber-200">
                        {item.grounding_note}
                      </p>
                    ) : null}
                  </article>
                ))
              : null}
          </CardContent>
        </Card>
      ) : null}

      <p className="flex items-start gap-2 text-xs leading-5 muted">
        <Scale className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        {t("tenders.recommend.disclaimer")}
      </p>
    </div>
  );
}
