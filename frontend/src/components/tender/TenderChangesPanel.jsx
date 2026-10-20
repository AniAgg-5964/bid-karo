import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  Camera,
  Check,
  History,
  RefreshCw,
  TriangleAlert,
  X,
} from "lucide-react";

import { api } from "../../lib/api";
import { currentLocale } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Skeleton } from "../ui/Spinner";
import { cn, formatDateTime } from "../../lib/utils";

function fieldLabel(field, t) {
  if (!field) return "—";
  const fallback = field.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  return t(`changes.fields.${field}`, { defaultValue: fallback });
}

function severityTone(severity) {
  if (severity === "warning") return "amber";
  if (severity === "danger") return "red";
  return "neutral";
}

export function ChangeRow({ change, onReview, busy, showTender = false }) {
  const { t } = useTranslation();
  return (
    <article className="rounded-xl border border-navy-100 p-4 dark:border-navy-800">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-navy-900 dark:text-white">{change.summary}</h3>
          {showTender && change.tender_id ? (
            <Link
              to={`/app/tenders/${change.tender_id}?tab=changes`}
              className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-teal-700 hover:underline dark:text-teal-300"
            >
              {change.tender_title || t("changes.tender")}
              <ArrowRight className="h-3 w-3" />
            </Link>
          ) : null}
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge tone={severityTone(change.severity)}>{fieldLabel(change.field, t)}</Badge>
            <Badge tone={change.review_status === "pending" ? "amber" : "neutral"}>
              {t(`status.${change.review_status}`, { defaultValue: change.review_status })}
            </Badge>
            <span className="text-xs muted">
              {formatDateTime(change.detected_at, currentLocale())}
            </span>
          </div>
        </div>
        {change.review_status === "pending" ? (
          <div className="flex shrink-0 gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onReview(change, "acknowledged")}
            >
              <Check className="h-3.5 w-3.5" />
              {t("changes.acknowledge")}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => onReview(change, "dismissed")}
            >
              <X className="h-3.5 w-3.5" />
              {t("changes.dismiss")}
            </Button>
          </div>
        ) : null}
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
        <div className="rounded-lg bg-navy-50 px-3 py-2 dark:bg-navy-800">
          <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
            {t("tenders.detail.changesPanel.from")}
          </p>
          <p className="mt-0.5 break-words text-xs text-navy-700 dark:text-navy-200">
            {change.old_value || "—"}
          </p>
        </div>
        <ArrowRight className="mx-auto h-4 w-4 text-navy-300" />
        <div className="rounded-lg bg-teal-50 px-3 py-2 dark:bg-teal-950/40">
          <p className="text-[10px] font-bold uppercase tracking-wide text-teal-700 dark:text-teal-300">
            {t("tenders.detail.changesPanel.to")}
          </p>
          <p className="mt-0.5 break-words text-xs text-navy-800 dark:text-navy-100">
            {change.new_value || "—"}
          </p>
        </div>
      </div>
      {change.source_url ? (
        <a
          href={change.source_url}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-teal-700 hover:underline dark:text-teal-300"
        >
          {t("tenders.requirements.source")}
          <ArrowRight className="h-3 w-3" />
        </a>
      ) : null}
    </article>
  );
}

export function TenderChangesPanel({ tenderId }) {
  const { t } = useTranslation();
  const toast = useToast();
  const [changes, setChanges] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reviewBusyId, setReviewBusyId] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [changeData, snapshotData] = await Promise.all([
        api.get(`/tenders/${tenderId}/changes`),
        api.get(`/tenders/${tenderId}/snapshots?limit=6`),
      ]);
      setChanges(changeData.items || []);
      setSnapshots(snapshotData.items || []);
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

  const capture = async () => {
    setBusy(true);
    try {
      const result = await api.post(`/tenders/${tenderId}/snapshots`, {});
      toast.success(
        result.created
          ? result.changes.length
            ? t("tenders.detail.changesPanel.captured")
            : t("tenders.detail.changesPanel.noChanges")
          : t("tenders.detail.changesPanel.noChanges"),
      );
      await load();
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setBusy(false);
    }
  };

  const recheck = async () => {
    setBusy(true);
    try {
      const result = await api.post(`/tenders/${tenderId}/refresh`, {});
      toast.success(
        result.changes.length
          ? t("tenders.detail.changesPanel.changeCount", { count: result.changes.length })
          : t("tenders.detail.changesPanel.noChanges"),
      );
      await load();
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR"
          ? t("errors.network")
          : err.message || t("tenders.detail.changesPanel.recheckFailed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const review = async (change, reviewStatus) => {
    setReviewBusyId(change.id);
    try {
      const updated = await api.patch(`/changes/${change.id}/review`, {
        review_status: reviewStatus,
      });
      setChanges((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      toast.success(
        reviewStatus === "acknowledged"
          ? t("changes.acknowledged")
          : t("changes.dismissed"),
      );
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setReviewBusyId(null);
    }
  };

  const pending = changes.filter((item) => item.review_status === "pending").length;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-teal-700" />
                <CardTitle>{t("tenders.detail.changesPanel.title")}</CardTitle>
              </div>
              <CardDescription>{t("tenders.detail.changesPanel.subtitle")}</CardDescription>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={capture} loading={busy}>
                <Camera className="h-3.5 w-3.5" />
                {t("tenders.detail.changesPanel.capture")}
              </Button>
              <Button size="sm" onClick={recheck} loading={busy}>
                <RefreshCw className="h-3.5 w-3.5" />
                {t("tenders.detail.changesPanel.recheck")}
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

          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={pending ? "amber" : "neutral"}>
              {pending
                ? t("changes.pendingCount", { count: pending })
                : t("changes.noPending")}
            </Badge>
            {snapshots[0] ? (
              <span className="text-xs muted">
                {t("tenders.detail.changesPanel.lastCaptured", {
                  date: formatDateTime(snapshots[0].captured_at, currentLocale()),
                })}
              </span>
            ) : null}
          </div>

          {loading ? (
            <div className="space-y-2">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : changes.length ? (
            changes.map((change) => (
              <ChangeRow
                key={change.id}
                change={change}
                onReview={review}
                busy={reviewBusyId === change.id}
              />
            ))
          ) : (
            <EmptyState
              icon={History}
              title={t("tenders.detail.changesPanel.emptyTitle")}
              description={
                snapshots.length
                  ? t("tenders.detail.changesPanel.noChanges")
                  : t("tenders.detail.changesPanel.emptyBody")
              }
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Camera className="h-4 w-4 text-teal-700" />
            <CardTitle>{t("tenders.detail.changesPanel.snapshots")}</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-3">
          {snapshots.length ? (
            <ol className="space-y-2">
              {snapshots.map((snapshot, index) => (
                <li
                  key={snapshot.id}
                  className={cn(
                    "flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5",
                    index === 0
                      ? "border-teal-200 bg-teal-50/60 dark:border-teal-900 dark:bg-teal-950/30"
                      : "border-navy-100 dark:border-navy-800",
                  )}
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-navy-900 dark:text-white">
                      {formatDateTime(snapshot.captured_at, currentLocale())}
                    </p>
                    <p className="text-xs muted">
                      {t("tenders.detail.changesPanel.snapshotMeta", {
                        count: snapshot.requirement_count,
                        hash: snapshot.content_hash.slice(0, 10),
                      })}
                    </p>
                  </div>
                  {snapshot.source_retrieved_at ? (
                    <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-navy-400">
                      {t("tenders.requirements.retrieved", {
                        date: formatDateTime(snapshot.source_retrieved_at, currentLocale()),
                      })}
                    </span>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : (
            <p className="rounded-lg bg-navy-50 px-3 py-4 text-center text-xs muted dark:bg-navy-800">
              {t("tenders.detail.changesPanel.noSnapshots")}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
