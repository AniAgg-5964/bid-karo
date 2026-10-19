import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BellRing, TriangleAlert } from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Spinner";
import { formatDate } from "../lib/utils";

export function ChangesPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/changes");
      setItems(data.items || []);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : items.length ? (
        <div className="space-y-2">
          {items.map((item) => (
            <Card key={item.id}>
              <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                    <BellRing className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-navy-900 dark:text-white">{item.summary}</p>
                    <p className="mt-1 text-xs muted">{formatDate(item.detected_at, currentLocale())}</p>
                  </div>
                </div>
                <StatusBadge
                  status={item.review_status}
                  label={t(`status.${item.review_status}`, { defaultValue: item.review_status })}
                />
              </CardContent>
            </Card>
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
