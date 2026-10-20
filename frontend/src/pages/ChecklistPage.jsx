import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarClock, ClipboardCheck, ListChecks, TriangleAlert } from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Badge } from "../components/ui/Badge";
import { Skeleton } from "../components/ui/Spinner";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Field";
import { useToast } from "../contexts/ToastContext";
import { cn, formatDate } from "../lib/utils";

const OPEN_STATUSES = ["missing", "incomplete", "needs_verification", "in_progress"];
const TASK_STATUSES = [
  "missing",
  "incomplete",
  "needs_verification",
  "in_progress",
  "complete",
  "not_applicable",
];

export function ChecklistPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [busyId, setBusyId] = useState(null);

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

  const updateStatus = async (item, status) => {
    setBusyId(item.id);
    try {
      const updated = await api.patch(`/checklist/${item.id}`, { status });
      setItems((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setBusyId(null);
    }
  };

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
              <CardContent className="space-y-3 py-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                      <ListChecks className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-navy-900 dark:text-white">{item.title}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs muted">
                        {item.category ? (
                          <Badge tone="neutral">
                            {t(`tenders.requirements.categories.${item.category}`, {
                              defaultValue: item.category,
                            })}
                          </Badge>
                        ) : null}
                        <span className="inline-flex items-center gap-1.5">
                          <CalendarClock className="h-3.5 w-3.5" />
                          {item.due_at
                            ? formatDate(item.due_at, currentLocale())
                            : t("checklist.noDue")}
                        </span>
                        {item.tender_id ? (
                          <Link
                            to={`/app/tenders/${item.tender_id}?tab=tasks`}
                            className="font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300"
                          >
                            {t("tenders.open")}
                          </Link>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <Select
                    className="w-full sm:w-44"
                    value={item.status}
                    disabled={busyId === item.id}
                    onChange={(event) => updateStatus(item, event.target.value)}
                    aria-label={t("checklist.status")}
                  >
                    {TASK_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {t(`status.${status}`, { defaultValue: status })}
                      </option>
                    ))}
                  </Select>
                </div>

                {item.action ? (
                  <p className="text-sm leading-6 text-navy-700 dark:text-navy-200">{item.action}</p>
                ) : null}
                {item.acceptance_criteria ? (
                  <blockquote className="border-l-2 border-teal-300 bg-teal-50/50 px-3 py-2 text-xs leading-5 text-navy-800 dark:border-teal-700 dark:bg-teal-950/30 dark:text-navy-100">
                    {item.acceptance_criteria}
                  </blockquote>
                ) : null}
                <div className="grid gap-2 text-xs sm:grid-cols-3">
                  <div>
                    <p className="font-semibold text-navy-500 dark:text-navy-300">
                      {t("tenders.assessment.evidenceCheck")}
                    </p>
                    <p className="mt-0.5 text-navy-700 dark:text-navy-200">
                      {item.evidence_check || "-"}
                    </p>
                  </div>
                  <div>
                    <p className="font-semibold text-navy-500 dark:text-navy-300">
                      {t("tenders.assessment.issuer")}
                    </p>
                    <p className="mt-0.5 text-navy-700 dark:text-navy-200">{item.issuer || "-"}</p>
                  </div>
                  <div>
                    <p className="font-semibold text-navy-500 dark:text-navy-300">
                      {t("tenders.requirements.consequence")}
                    </p>
                    <p className="mt-0.5 text-navy-700 dark:text-navy-200">
                      {item.consequence || "-"}
                    </p>
                  </div>
                </div>
                <p className="text-xs muted">
                  {item.source_document_title || t("tenders.assessment.sourceDocument")}
                  {item.page_index
                    ? ` · ${t("tenders.requirements.page", { page: item.page_index })}`
                    : ""}
                  {item.clause_reference
                    ? ` · ${t("tenders.requirements.clause", { ref: item.clause_reference })}`
                    : ""}
                </p>
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
