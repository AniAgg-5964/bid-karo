import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  FileText,
  FolderCheck,
  Gauge,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { useAuth } from "../contexts/AuthContext";
import { ActionInbox } from "../components/dashboard/ActionInbox";
import { PageHeader } from "../components/ui/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { EmptyState } from "../components/ui/EmptyState";
import { Progress } from "../components/ui/Progress";
import { Skeleton } from "../components/ui/Spinner";
import { StatusBadge } from "../components/ui/Badge";
import { cn, formatDate, greetingKey } from "../lib/utils";

const METRICS = [
  { key: "activeBids", dataKey: "active_bids", icon: Target, href: "/app/tenders", tone: "teal" },
  { key: "openTasks", dataKey: "open_tasks", icon: ClipboardList, href: "/app/checklist", tone: "amber" },
  {
    key: "upcomingDeadlines",
    dataKey: "upcoming_deadlines",
    icon: CalendarClock,
    href: "/app/checklist",
    tone: "red",
  },
  {
    key: "evidenceDocuments",
    dataKey: "evidence_documents",
    icon: FileText,
    href: "/app/documents",
    tone: "blue",
  },
];

const TONES = {
  teal: "bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  red: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  blue: "bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
};

const ACTION_TONES = {
  warning: "border-amber-200 bg-amber-50/60 dark:border-amber-900 dark:bg-amber-950/30",
  danger: "border-red-200 bg-red-50/60 dark:border-red-900 dark:bg-red-950/30",
  success: "border-teal-200 bg-teal-50/60 dark:border-teal-900 dark:bg-teal-950/30",
  info: "border-navy-100 bg-navy-50/60 dark:border-navy-800 dark:bg-navy-800/40",
};

function MetricStrip({ metrics, summary, loading }) {
  const { t } = useTranslation();
  return (
    <div className="surface grid divide-y divide-navy-100 sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        const value = summary?.metrics?.[metric.dataKey] ?? 0;
        return (
          <Link
            key={metric.key}
            to={metric.href}
            className="group flex items-center gap-3 px-4 py-3.5 transition hover:bg-navy-50/70 dark:divide-navy-800 dark:hover:bg-navy-800/50"
          >
            <span
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                TONES[metric.tone],
              )}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              {loading ? (
                <Skeleton className="h-5 w-10" />
              ) : (
                <span className="tabular block text-lg font-semibold leading-none text-navy-900 dark:text-white">
                  {value}
                </span>
              )}
              <span className="mt-1 block truncate text-xs font-medium text-navy-600 dark:text-navy-300">
                {t(`dashboard.metrics.${metric.key}`)}
              </span>
            </span>
            <ArrowRight
              className="h-3.5 w-3.5 shrink-0 text-navy-300 transition group-hover:translate-x-0.5 group-hover:text-teal-600"
              aria-hidden="true"
            />
          </Link>
        );
      })}
    </div>
  );
}

function TenderRow({ tender }) {
  const { t } = useTranslation();
  return (
    <li>
      <Link
        to={`/app/tenders/${tender.id}`}
        className="flex items-center gap-3 rounded-xl px-2 py-3 transition hover:bg-navy-50 dark:hover:bg-navy-800"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-navy-100 text-navy-600 dark:bg-navy-800 dark:text-navy-300">
          <FileText className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">{tender.title}</p>
          <p className="truncate text-xs muted">
            {[tender.authority, tender.reference_number].filter(Boolean).join(" · ") || t("tenders.source")}
          </p>
        </div>
        <div className="hidden text-right sm:block">
          <p className="text-xs font-medium text-navy-700 dark:text-navy-200">
            {tender.deadline ? formatDate(tender.deadline, currentLocale()) : "—"}
          </p>
          <StatusBadge status={tender.status} label={t(`tenders.statuses.${tender.status}`)} />
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-navy-300" />
      </Link>
    </li>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { session, refreshSession } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const data = await api.get("/dashboard/summary");
      setSummary(data);
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
  const greeting = t(`dashboard.${greetingKey()}`);
  const companyName = summary?.company_name || session?.company?.name;

  const refresh = async () => {
    await Promise.all([load(), refreshSession().catch(() => null)]);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={companyName}
        title={t("dashboard.greeting", { greeting, name })}
        description={t("dashboard.subtitle")}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={refresh} loading={loading && Boolean(summary)}>
              <RefreshCw className="h-3.5 w-3.5" />
              {t("common.refresh")}
            </Button>
            <Button size="sm" onClick={() => navigate("/app/discover")}>
              <Sparkles className="h-3.5 w-3.5" />
              {t("dashboard.discoverCta")}
            </Button>
          </>
        }
      />

      {error ? (
        <Card className="border-red-200 dark:border-red-900">
          <CardContent className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <TriangleAlert className="mt-0.5 h-5 w-5 text-red-600" />
              <div>
                <p className="text-sm font-semibold text-navy-900 dark:text-white">
                  {t("common.somethingWentWrong")}
                </p>
                <p className="mt-0.5 text-sm muted">{error}</p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={load}>
              {t("common.retry")}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <MetricStrip metrics={METRICS} summary={summary} loading={loading && !summary} />

      <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader
              action={
                <Link
                  to="/app/tenders"
                  className="text-xs font-semibold text-cobalt-700 hover:text-cobalt-900 dark:text-cobalt-300"
                >
                  {t("common.viewAll")}
                </Link>
              }
            >
              <CardTitle>{t("inbox.title")}</CardTitle>
              <p className="mt-1 text-sm muted">{t("inbox.subtitle")}</p>
            </CardHeader>
            <CardContent className="pt-4">
              <ActionInbox limit={8} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader
              action={
                <Link to="/app/tenders" className="text-xs font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300">
                  {t("common.viewAll")}
                </Link>
              }
            >
              <CardTitle>{t("dashboard.recentTenders")}</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              {loading && !summary ? (
                <div className="space-y-2">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                </div>
              ) : summary?.recent_tenders?.length ? (
                <ul className="divide-y divide-navy-100 dark:divide-navy-800">
                  {summary.recent_tenders.map((tender) => (
                    <TenderRow key={tender.id} tender={tender} />
                  ))}
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
                  className="py-8"
                />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("dashboard.profileStrength")}</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <div className="flex items-end justify-between">
                <p className="text-3xl font-semibold tracking-tight text-navy-900 dark:text-white">
                  {summary?.profile_completeness ?? session?.company?.profile_completeness ?? 0}%
                </p>
                <TrendingUp className="h-5 w-5 text-teal-600" />
              </div>
              <Progress
                value={summary?.profile_completeness ?? session?.company?.profile_completeness ?? 0}
                className="mt-3"
                label={t("dashboard.profileStrength")}
              />
              <p className="mt-2 text-xs leading-5 muted">{t("dashboard.profileHint")}</p>
              <Link
                to="/app/company"
                className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300"
              >
                {t("dashboard.completeProfile")}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("dashboard.upcomingDeadlines")}</CardTitle>
              <p className="mt-1 text-xs muted">{t("dashboard.next14Days")}</p>
            </CardHeader>
            <CardContent className="pt-2">
              {summary?.upcoming_deadlines?.length ? (
                <ul className="space-y-2">
                  {summary.upcoming_deadlines.map((deadline) => (
                    <li key={deadline.id}>
                      <Link
                        to={deadline.href}
                        className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-navy-50 dark:hover:bg-navy-800"
                      >
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-600 dark:bg-red-950 dark:text-red-300">
                          <CalendarClock className="h-4 w-4" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-navy-900 dark:text-white">
                            {deadline.title}
                          </p>
                          <p className="text-xs muted">{formatDate(deadline.due_at, currentLocale())}</p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="rounded-lg bg-navy-50 px-3 py-4 text-center text-xs muted dark:bg-navy-800">
                  {t("dashboard.noDeadlines")}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("dashboard.recentActivity")}</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              {summary?.recent_activity?.length ? (
                <ul className="space-y-3">
                  {summary.recent_activity.map((item) => (
                    <li key={item.id} className="flex items-start gap-3">
                      <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                        <FolderCheck className="h-3 w-3" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm text-navy-800 dark:text-navy-100">
                          {t(`activity.${item.action}`, { defaultValue: item.summary })}
                        </p>
                        <p className="text-xs muted">{formatDate(item.created_at, currentLocale())}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="rounded-lg bg-navy-50 px-3 py-4 text-center text-xs muted dark:bg-navy-800">
                  {t("dashboard.noActivity")}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
