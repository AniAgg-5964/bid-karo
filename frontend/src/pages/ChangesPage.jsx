import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BellRing, TriangleAlert } from "lucide-react";

import { api } from "../lib/api";
import { useToast } from "../contexts/ToastContext";
import { PageHeader } from "../components/ui/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton } from "../components/ui/Spinner";
import { ChangeRow } from "../components/tender/TenderChangesPanel";
import { cn } from "../lib/utils";

export function ChangesPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/changes?limit=200");
      setItems(data.items || []);
    } catch (err) {
      setError(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const review = async (change, reviewStatus) => {
    setBusyId(change.id);
    try {
      const updated = await api.patch(`/changes/${change.id}/review`, {
        review_status: reviewStatus,
      });
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
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
      setBusyId(null);
    }
  };

  const pending = items.filter((item) => item.review_status === "pending");
  const visible = filter === "pending" ? pending : items;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("changes.title")}
        description={t("changes.subtitle")}
        actions={
          <Button variant="outline" size="sm" onClick={load} loading={loading && Boolean(items.length)}>
            {t("common.refresh")}
          </Button>
        }
      />

      {error ? (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/40">
          <div className="flex items-start gap-2">
            <TriangleAlert className="mt-0.5 h-4 w-4 text-red-600" />
            <p className="text-sm text-red-700 dark:text-red-200">{error}</p>
          </div>
          <Button variant="outline" size="sm" onClick={load}>
            {t("common.retry")}
          </Button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {[
          ["all", t("changes.filterAll")],
          ["pending", t("changes.filterPending")],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setFilter(key)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-semibold transition",
              filter === key
                ? "bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                : "text-navy-500 hover:bg-navy-50 dark:hover:bg-navy-800",
            )}
          >
            {label}
          </button>
        ))}
        <Badge tone={pending.length ? "amber" : "neutral"}>
          {pending.length
            ? t("changes.pendingCount", { count: pending.length })
            : t("changes.noPending")}
        </Badge>
      </div>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : visible.length ? (
        <div className="space-y-2">
          {visible.map((item) => (
            <ChangeRow
              key={item.id}
              change={item}
              onReview={review}
              busy={busyId === item.id}
              showTender
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={BellRing}
              title={t("changes.emptyTitle")}
              description={t("changes.emptyBody")}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
