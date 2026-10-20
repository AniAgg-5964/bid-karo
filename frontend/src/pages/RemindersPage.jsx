import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AlarmClock,
  BellRing,
  CalendarPlus,
  Check,
  FileClock,
  Mail,
  TriangleAlert,
  X,
} from "lucide-react";

import { api } from "../lib/api";
import { currentLocale } from "../i18n";
import { useToast } from "../contexts/ToastContext";
import { PageHeader } from "../components/ui/PageHeader";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Skeleton } from "../components/ui/Spinner";
import { cn, formatDate } from "../lib/utils";

const TYPE_ICONS = {
  deadline: AlarmClock,
  task: BellRing,
  document_expiry: FileClock,
};

const TYPE_TONES = {
  deadline: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  task: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  document_expiry: "bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
};

export function RemindersPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [emailConfigured, setEmailConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("pending");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("/reminders?limit=200");
      setItems(data.items || []);
      setEmailEnabled(Boolean(data.email_enabled));
      setEmailConfigured(Boolean(data.email_configured));
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

  const update = async (reminder, status) => {
    setBusyId(reminder.id);
    try {
      const updated = await api.patch(`/reminders/${reminder.id}`, { status });
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      toast.success(
        status === "acknowledged" ? t("reminders.acknowledged") : t("reminders.dismissed"),
      );
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    } finally {
      setBusyId(null);
    }
  };

  const exportCalendar = async () => {
    try {
      await api.download("/calendar.ics", "bidkaro-calendar.ics");
    } catch (err) {
      toast.error(
        err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
      );
    }
  };

  const pending = useMemo(
    () => items.filter((item) => item.status === "pending"),
    [items],
  );
  const visible = filter === "pending" ? pending : items;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("reminders.title")}
        description={t("reminders.subtitle")}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={load} loading={loading && Boolean(items.length)}>
              {t("common.refresh")}
            </Button>
            <Button size="sm" onClick={exportCalendar}>
              <CalendarPlus className="h-3.5 w-3.5" />
              {t("reminders.exportCalendar")}
            </Button>
          </>
        }
      />

      <div
        className={cn(
          "flex items-start gap-3 rounded-xl border p-4",
          !emailConfigured
            ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"
            : emailEnabled
              ? "border-teal-200 bg-teal-50 text-teal-900 dark:border-teal-900 dark:bg-teal-950/40 dark:text-teal-100"
              : "border-navy-200 bg-white text-navy-800 dark:border-navy-700 dark:bg-navy-900 dark:text-navy-100",
        )}
      >
        <Mail className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="text-sm font-semibold">{t("reminders.emailTitle")}</p>
          <p className="mt-0.5 text-sm leading-6">
            {!emailConfigured
              ? t("reminders.emailNotConfigured")
              : emailEnabled
                ? t("reminders.emailOn")
                : t("reminders.emailOff")}
          </p>
          {!emailConfigured ? (
            <p className="mt-1 text-xs font-medium">{t("reminders.emailAppMissing")}</p>
          ) : null}
        </div>
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

      <div className="flex flex-wrap items-center gap-2">
        {[
          ["pending", t("reminders.pending")],
          ["all", t("common.all")],
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
          {pending.length} {t("reminders.pending").toLowerCase()}
        </Badge>
      </div>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : visible.length ? (
        <div className="space-y-2">
          {visible.map((reminder) => {
            const Icon = TYPE_ICONS[reminder.type] || BellRing;
            return (
              <Card key={reminder.id}>
                <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <span
                      className={cn(
                        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                        TYPE_TONES[reminder.type] || TYPE_TONES.task,
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-navy-900 dark:text-white">
                        {reminder.title}
                      </p>
                      <p className="mt-1 text-sm leading-6 muted">{reminder.body}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <Badge tone="neutral">
                          {t(`reminders.types.${reminder.type}`, { defaultValue: reminder.type })}
                        </Badge>
                        <span className="inline-flex items-center gap-1 text-xs muted">
                          <AlarmClock className="h-3.5 w-3.5" />
                          {t("reminders.due", {
                            date: formatDate(reminder.due_at, currentLocale()),
                          })}
                        </span>
                        {reminder.lead_days ? (
                          <span className="text-xs muted">
                            {t("reminders.lead", { count: reminder.lead_days })}
                          </span>
                        ) : null}
                        <StatusBadge
                          status={reminder.status}
                          label={t(`status.${reminder.status}`, { defaultValue: reminder.status })}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <Link
                      to={reminder.href}
                      className="inline-flex items-center justify-center rounded-lg border border-navy-200 px-3 py-1.5 text-xs font-semibold text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
                    >
                      {t("reminders.open")}
                    </Link>
                    {reminder.status === "pending" ? (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busyId === reminder.id}
                          onClick={() => update(reminder, "acknowledged")}
                        >
                          <Check className="h-3.5 w-3.5" />
                          {t("reminders.acknowledge")}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={busyId === reminder.id}
                          onClick={() => update(reminder, "dismissed")}
                        >
                          <X className="h-3.5 w-3.5" />
                          {t("reminders.dismiss")}
                        </Button>
                      </>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={AlarmClock}
              title={t("reminders.emptyTitle")}
              description={t("reminders.emptyBody")}
            />
          </CardContent>
        </Card>
      )}

      <p className="rounded-xl border border-navy-100 bg-navy-50 px-3 py-3 text-xs leading-5 muted dark:border-navy-800 dark:bg-navy-800">
        {t("reminders.note")}
      </p>
    </div>
  );
}
