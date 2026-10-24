import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  CalendarClock,
  ClipboardList,
  FileText,
  Layers,
  ListChecks,
  Plus,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { useAuth } from "../contexts/AuthContext";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton } from "../components/ui/Spinner";
import { ScoreRing, scoreTone } from "../components/ui/ScoreRing";
import { cn, formatDate } from "../lib/utils";

const TONES = {
  teal: "bg-teal-50 text-teal-600 dark:bg-teal-900/40 dark:text-teal-300",
  blue: "bg-sky-50 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300",
  amber: "bg-amber-50 text-amber-600 dark:bg-amber-900/40 dark:text-amber-300",
  red: "bg-red-50 text-red-500 dark:bg-red-900/40 dark:text-red-300",
};

const ACTION_DOTS = {
  danger: "bg-red-500",
  warning: "bg-amber-400",
  info: "bg-sky-400",
  success: "bg-teal-500",
};

function StatCard({ icon: Icon, tone, helpTone = "green", value, label, help, loading, href }) {
  const helpClass =
    helpTone === "red"
      ? "text-red-500"
      : helpTone === "amber"
        ? "text-amber-600"
        : helpTone === "muted"
          ? "text-navy-400"
          : "text-teal-600";
  return (
    <Link
      to={href}
      className="surface flex min-w-0 items-center gap-4 px-5 py-4 transition hover:border-navy-200 hover:shadow-card"
    >
      <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-lg", TONES[tone])}>
        <Icon className="h-5 w-5" strokeWidth={1.9} aria-hidden="true" />
      </span>
      <div className="min-w-0">
        {loading ? (
          <Skeleton className="h-7 w-10" />
        ) : (
          <p className="text-[22px] font-bold leading-tight tracking-tight text-navy-900 dark:text-white">
            {value}
          </p>
        )}
        <p className="truncate text-[12px] font-semibold text-navy-800 dark:text-navy-100">{label}</p>
        <p className={cn("mt-0.5 truncate text-[11px] font-medium", helpClass)}>{help}</p>
      </div>
    </Link>
  );
}

function dueLabel(item, t, locale) {
  if (!item.due_at) return "";
  const due = new Date(item.due_at);
  if (Number.isNaN(due.getTime())) return "";
  const today = new Date();
  const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((startOfDay(due) - startOfDay(today)) / 86400000);
  if (days <= 0) return t("dashboard.dueToday");
  if (days === 1) return t("dashboard.dueInDays", { count: days });
  if (days < 7) return t("dashboard.dueInDays", { count: days });
  return formatDate(item.due_at, locale);
}

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { session } = useAuth();
  const [summary, setSummary] = useState(null);
  const [scores, setScores] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const data = await api.get("/dashboard/summary");
      setSummary(data);
      const recent = (data.recent_tenders || []).slice(0, 4);
      const results = await Promise.allSettled(
        recent.map((tender) => api.get(`/tenders/${tender.id}/assessment`)),
      );
      const next = {};
      results.forEach((result, index) => {
        if (result.status === "fulfilled" && result.value?.score) {
          next[recent[index].id] = result.value.score;
        }
      });
      setScores(next);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const name = (summary?.user_name || session?.user?.full_name || "").split(" ")[0];
  const metrics = summary?.metrics;
  const recent = summary?.recent_tenders || [];
  const tasks = memoDeadlines(summary?.upcoming_deadlines, t, currentLocale());
  const actions = summary?.priority_actions || [];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-[24px] font-bold tracking-[-0.01em] text-navy-900 dark:text-white sm:text-[27px]">
            {t("dashboard.welcomeBack", { name })}
          </h1>
          <p className="mt-1 text-[13px] muted">{t("dashboard.today")}</p>
        </div>
        <Button onClick={() => navigate("/app/discover")} className="self-start">
          <Plus className="h-4 w-4" />
          {t("dashboard.discoverCta")}
        </Button>
      </header>

      {error ? (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-red-900 dark:bg-red-950/40">
          <div className="flex items-start gap-2">
            <TriangleAlert className="mt-0.5 h-4 w-4 text-red-600" />
            <p className="text-sm text-red-700 dark:text-red-200">{error}</p>
          </div>
          <Button variant="outline" size="sm" onClick={load}>
            {t("common.retry")}
          </Button>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={Layers}
          tone="teal"
          helpTone="green"
          value={metrics?.active_bids ?? 0}
          label={t("dashboard.metrics.activeBids")}
          help={t("dashboard.metricsHelp.activeBids")}
          loading={loading && !summary}
          href="/app/tenders"
        />
        <StatCard
          icon={ListChecks}
          tone="blue"
          helpTone="muted"
          value={metrics?.open_tasks ?? 0}
          label={t("dashboard.metrics.openTasks")}
          help={t("dashboard.metricsHelp.openTasks")}
          loading={loading && !summary}
          href="/app/checklist"
        />
        <StatCard
          icon={CalendarClock}
          tone="amber"
          helpTone="red"
          value={metrics?.upcoming_deadlines ?? 0}
          label={t("dashboard.metrics.upcomingDeadlines")}
          help={t("dashboard.metricsHelp.upcomingDeadlines")}
          loading={loading && !summary}
          href="/app/checklist"
        />
        <StatCard
          icon={FileText}
          tone="red"
          helpTone="muted"
          value={metrics?.evidence_documents ?? 0}
          label={t("dashboard.metrics.evidenceDocuments")}
          help={t("dashboard.metricsHelp.evidenceDocuments")}
          loading={loading && !summary}
          href="/app/documents"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.9fr_1fr]">
        <Card className="min-w-0">
          <div className="flex items-center justify-between px-5 pb-1 pt-5">
            <h2 className="text-[15px] font-semibold text-navy-900 dark:text-white">
              {t("dashboard.recentTenders")}
            </h2>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={load}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-navy-300 transition hover:bg-navy-50 hover:text-navy-600 dark:hover:bg-navy-800"
                aria-label={t("common.refresh")}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
              </button>
              <Link to="/app/tenders" className="text-[12px] font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300">
                {t("common.viewAll")}
              </Link>
            </div>
          </div>

          {loading && !summary ? (
            <div className="space-y-3 px-5 py-4">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : recent.length ? (
            <ul className="divide-y divide-navy-100 dark:divide-navy-800">
              {recent.map((tender) => {
                const score = scores[tender.id];
                return (
                  <li key={tender.id}>
                    <Link
                      to={`/app/tenders/${tender.id}`}
                      className="flex items-center gap-3 px-5 py-3.5 transition hover:bg-navy-50/70 dark:hover:bg-navy-800/50"
                    >
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300">
                        <ClipboardList className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-semibold text-navy-900 dark:text-white">
                          {tender.title}
                        </p>
                        {tender.authority || tender.reference_number ? (
                          <p className="mt-0.5 truncate text-[11px] text-navy-400">
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
                          tone={score.band === "strong" ? "green" : score.band === "weak" ? "amber" : scoreTone(score.value)}
                          size={44}
                          stroke={4}
                          ariaLabel={t("tenders.assessment.softScore")}
                        />
                      ) : (
                        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-[3px] border-navy-100 text-[11px] font-semibold text-navy-300 dark:border-navy-800">
                          —
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState
              icon={FileText}
              title={t("dashboard.noTenders")}
              description={t("dashboard.noTendersHint")}
              action={
                <Button variant="outline" size="sm" onClick={() => navigate("/app/discover")}>
                  {t("dashboard.discoverCta")}
                </Button>
              }
              className="py-10"
            />
          )}
        </Card>

        <Card className="flex min-w-0 flex-col">
          <div className="flex items-center justify-between px-5 pb-1 pt-5">
            <h2 className="text-[15px] font-semibold text-navy-900 dark:text-white">
              {t("dashboard.myTasks")}
            </h2>
            <Link to="/app/checklist" className="text-[12px] font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300">
              {t("common.viewAll")}
            </Link>
          </div>

          {loading && !summary ? (
            <div className="space-y-3 px-5 py-4">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : tasks.length || actions.length ? (
            <div className="flex-1">
              {tasks.length ? (
                <ul className="divide-y divide-navy-100 dark:divide-navy-800">
                  {tasks.map((task) => (
                    <li key={`${task.id}-${task.due_at}`}>
                      <Link
                        to={task.href}
                        className="flex items-start gap-3 px-5 py-3.5 transition hover:bg-navy-50/70 dark:hover:bg-navy-800/50"
                      >
                        <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-navy-300 bg-white dark:border-navy-600 dark:bg-navy-800" />
                        <div className="min-w-0 flex-1">
                          <p className="line-clamp-2 text-[12.5px] font-semibold leading-5 text-navy-800 dark:text-navy-100">
                            {task.title}
                          </p>
                          <p className="mt-0.5 truncate text-[11px] capitalize text-navy-400">
                            {task.status
                              ? t(`tenders.statuses.${task.status}`, { defaultValue: task.status })
                              : ""}
                          </p>
                        </div>
                        <span
                          className={cn(
                            "shrink-0 pt-0.5 text-[11px] font-medium",
                            task.urgent ? "text-amber-600" : "text-navy-400",
                          )}
                        >
                          {task.label}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : null}

              {actions.length ? (
                <ul
                  className={cn(
                    "divide-y divide-navy-100 dark:divide-navy-800",
                    tasks.length && "border-t border-navy-100 dark:border-navy-800",
                  )}
                >
                  {actions.map((action) => (
                    <li key={action.key}>
                      <Link
                        to={action.href}
                        className="flex items-start gap-3 px-5 py-3 transition hover:bg-navy-50/70 dark:hover:bg-navy-800/50"
                      >
                        <span
                          className={cn(
                            "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                            ACTION_DOTS[action.tone] || ACTION_DOTS.info,
                          )}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="line-clamp-2 text-[12.5px] font-semibold leading-5 text-navy-800 dark:text-navy-100">
                            {action.title}
                          </p>
                          <p className="mt-0.5 line-clamp-1 text-[11px] text-navy-400">
                            {action.description}
                          </p>
                        </div>
                        <ArrowRight className="mt-1 h-3.5 w-3.5 shrink-0 text-navy-300" />
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <p className="m-5 rounded-lg bg-navy-50 px-3 py-6 text-center text-xs muted dark:bg-navy-800">
              {t("dashboard.noTasks")}
            </p>
          )}

          <div className="border-t border-navy-100 px-5 py-3 dark:border-navy-800">
            <div className="flex items-center justify-between text-[11px]">
              <span className="muted">{t("dashboard.profileStrength")}</span>
              <span className="font-semibold text-navy-700 dark:text-navy-200">
                {summary?.profile_completeness ?? 0}%
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-navy-100 dark:bg-navy-800">
              <div
                className="h-full rounded-full bg-teal-600"
                style={{ width: `${Math.min(summary?.profile_completeness ?? 0, 100)}%` }}
              />
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function memoDeadlines(deadlines = [], t, locale) {
  return (deadlines || []).map((item) => {
    const due = item.due_at ? new Date(item.due_at) : null;
    const urgent = Boolean(due && !Number.isNaN(due.getTime()) && due.getTime() - Date.now() < 3 * 86400000);
    return {
      ...item,
      label: dueLabel(item, t, locale),
      urgent,
    };
  });
}
