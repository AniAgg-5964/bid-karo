import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarClock, ClipboardCheck, ListChecks, TriangleAlert } from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Spinner";
import { Button } from "../components/ui/Button";
import { cn, formatDate } from "../lib/utils";

const OPEN_STATUSES = ["missing", "incomplete", "needs_verification", "in_progress"];

export function ChecklistPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/checklist");
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

  const visible = useMemo(
    () => (filter === "open" ? items.filter((item) => OPEN_STATUSES.includes(item.status)) : items),
    [items, filter],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("checklist.title")}
        description={t("checklist.subtitle")}
        actions={
          <Button variant="outline" size="sm" onClick={load} loading={loading && Boolean(items.length)}>
            {t("common.refresh")}
          </Button>
        }
      />

      <div className="flex items-center gap-1 rounded-xl border border-navy-100 bg-white p-1 dark:border-navy-800 dark:bg-navy-900 sm:w-fit">
        {["all", "open"].map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setFilter(key)}
            className={cn(
              "rounded-lg px-3.5 py-2 text-xs font-semibold capitalize transition",
              filter === key
                ? "bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                : "text-navy-500 hover:bg-navy-50 hover:text-navy-800 dark:hover:bg-navy-800 dark:hover:text-white",
            )}
          >
            {t(`checklist.${key}`)}
          </button>
        ))}
      </div>

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
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : visible.length ? (
        <div className="space-y-2">
          {visible.map((item) => (
            <Card key={item.id}>
              <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                    <ListChecks className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-navy-900 dark:text-white">{item.title}</p>
                    <p className="mt-1 flex items-center gap-1.5 text-xs muted">
                      <CalendarClock className="h-3.5 w-3.5" />
                      {item.due_at
                        ? formatDate(item.due_at, currentLocale())
                        : t("checklist.noDue")}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge
                    status={item.status}
                    label={t(`status.${item.status}`, { defaultValue: item.status })}
                  />
                  {item.tender_id ? (
                    <Link
                      to={`/app/tenders/${item.tender_id}?tab=tasks`}
                      className="text-xs font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300"
                    >
                      {t("tenders.open")}
                    </Link>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={ClipboardCheck}
              title={t("checklist.emptyTitle")}
              description={t("checklist.emptyBody")}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
