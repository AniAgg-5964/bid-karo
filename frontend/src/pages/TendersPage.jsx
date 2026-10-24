import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  CalendarClock,
  ClipboardList,
  FileText,
  Plus,
  Search,
  TriangleAlert,
} from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton } from "../components/ui/Spinner";
import { ScoreRing, scoreTone } from "../components/ui/ScoreRing";
import { formatDate } from "../lib/utils";

export function TendersPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [tenders, setTenders] = useState([]);
  const [scores, setScores] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/tenders");
      const items = data.items || [];
      setTenders(items);
      const sample = items.slice(0, 12);
      const results = await Promise.allSettled(
        sample.map((tender) => api.get(`/tenders/${tender.id}/assessment`)),
      );
      const next = {};
      results.forEach((result, index) => {
        if (result.status === "fulfilled" && result.value?.score) {
          next[sample[index].id] = result.value.score;
        }
      });
      setScores(next);
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

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return tenders;
    return tenders.filter((tender) =>
      [tender.title, tender.authority, tender.reference_number]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term)),
    );
  }, [tenders, query]);

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-[23px] font-bold tracking-[-0.01em] text-navy-900 dark:text-white sm:text-[26px]">
            {t("tenders.title")}
          </h1>
          <p className="mt-1 text-[13px] muted">{t("tenders.subtitle")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="md" onClick={load} loading={loading && Boolean(tenders.length)}>
            {t("common.refresh")}
          </Button>
          <Button onClick={() => navigate("/app/discover")}>
            <Plus className="h-4 w-4" />
            {t("dashboard.discoverCta")}
          </Button>
        </div>
      </header>

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

      <Card>
        <div className="flex flex-col gap-3 border-b border-navy-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between dark:border-navy-800">
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-300" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("common.globalSearch")}
              aria-label={t("common.search")}
              className="h-9 w-full rounded-lg border border-navy-200 bg-white pl-9 pr-3 text-[13px] text-navy-800 outline-none transition placeholder:text-navy-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/15 dark:border-navy-700 dark:bg-navy-900 dark:text-white"
            />
          </div>
          <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-navy-400">
            {t("tenders.countLabel", {
              count: visible.length,
              defaultValue: "{{count}} tenders",
            })}
          </span>
        </div>

        {loading ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : visible.length ? (
          <ul className="divide-y divide-navy-100 dark:divide-navy-800">
            {visible.map((tender) => {
              const score = scores[tender.id];
              return (
                <li key={tender.id}>
                  <Link
                    to={`/app/tenders/${tender.id}`}
                    className="flex items-center gap-4 px-5 py-4 transition hover:bg-navy-50/70 dark:hover:bg-navy-800/50"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300">
                      <ClipboardList className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13.5px] font-semibold text-navy-900 dark:text-white">
                        {tender.title}
                      </p>
                      {tender.authority || tender.reference_number ? (
                        <p className="mt-0.5 truncate text-[11.5px] text-navy-400">
                          {[tender.authority, tender.reference_number].filter(Boolean).join(" · ")}
                        </p>
                      ) : null}
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="chip chip-green capitalize">
                          {t(`tenders.statuses.${tender.status}`, { defaultValue: tender.status })}
                        </span>
                        {tender.deadline ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-navy-500 dark:text-navy-300">
                            <CalendarClock className="h-3 w-3" />
                            {formatDate(tender.deadline, currentLocale())}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    {score ? (
                      <ScoreRing
                        value={score.value}
                        tone={scoreTone(score.value)}
                        size={48}
                        stroke={4}
                        ariaLabel={t("tenders.assessment.softScore")}
                      />
                    ) : null}
                    <ArrowRight className="hidden h-4 w-4 shrink-0 text-navy-300 sm:block" />
                  </Link>
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyState
            icon={query ? Search : FileText}
            title={query ? t("tenders.emptyTitle") : t("tenders.emptyTitle")}
            description={query ? t("tenders.emptyBody") : t("tenders.emptyBody")}
            action={
              <Link
                to="/app/discover"
                className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
              >
                {t("dashboard.discoverCta")}
                <ArrowRight className="h-4 w-4" />
              </Link>
            }
            className="py-12"
          />
        )}
      </Card>
    </div>
  );
}
