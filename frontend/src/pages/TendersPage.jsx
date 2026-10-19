import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, CalendarClock, FileText, MapPin, Search, TriangleAlert } from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton } from "../components/ui/Spinner";
import { StatusBadge } from "../components/ui/Badge";
import { formatDate } from "../lib/utils";

export function TendersPage() {
  const { t } = useTranslation();
  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/tenders");
      setTenders(data.items || []);
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
        title={t("tenders.title")}
        description={t("tenders.subtitle")}
        actions={
          <Button variant="outline" size="sm" onClick={load} loading={loading && Boolean(tenders.length)}>
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
        <div className="space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : tenders.length ? (
        <div className="grid gap-3">
          {tenders.map((tender) => (
            <Card key={tender.id} className="transition hover:border-teal-200 hover:shadow-pop">
              <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-navy-100 text-navy-600 dark:bg-navy-800 dark:text-navy-300">
                    <FileText className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/app/tenders/${tender.id}`}
                        className="truncate text-sm font-semibold text-navy-900 hover:text-teal-700 dark:text-white dark:hover:text-teal-300"
                      >
                        {tender.title}
                      </Link>
                      <StatusBadge
                        status={tender.status}
                        label={t(`tenders.statuses.${tender.status}`, { defaultValue: tender.status })}
                      />
                    </div>
                    <p className="mt-1 truncate text-xs muted">
                      {[tender.authority, tender.reference_number].filter(Boolean).join(" · ") || "—"}
                    </p>
                    <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-navy-500 dark:text-navy-300">
                      <span className="inline-flex items-center gap-1">
                        <CalendarClock className="h-3.5 w-3.5" />
                        {tender.deadline ? formatDate(tender.deadline, currentLocale()) : "—"}
                      </span>
                      {tender.source_url ? (
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5" />
                          {t("tenders.source")}
                        </span>
                      ) : null}
                    </p>
                  </div>
                </div>
                <Link
                  to={`/app/tenders/${tender.id}`}
                  className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-lg border border-navy-200 px-3 py-2 text-xs font-semibold text-navy-700 transition hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-teal-950 sm:self-auto"
                >
                  {t("tenders.open")}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={Search}
              title={t("tenders.emptyTitle")}
              description={t("tenders.emptyBody")}
              action={
                <Link
                  to="/app/discover"
                  className="inline-flex items-center gap-2 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800"
                >
                  {t("dashboard.discoverCta")}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
