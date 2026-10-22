import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  BellRing,
  CalendarClock,
  CircleHelp,
  FileWarning,
  Flag,
  ShieldAlert,
} from "lucide-react";

import { api } from "../../lib/api";
import { currentLocale } from "../../i18n";
import { formatDateTime } from "../../lib/utils";
import { EmptyState } from "../ui/EmptyState";
import { Skeleton } from "../ui/Spinner";

const ICONS = {
  eligibility: ShieldAlert,
  evidence: FileWarning,
  change: Flag,
  deadline: CalendarClock,
  reminder: BellRing,
  source: CircleHelp,
};

const SEVERITY = {
  danger: "border-red-200 bg-red-50/70 dark:border-red-900 dark:bg-red-950/30",
  warning: "border-amber-200 bg-amber-50/70 dark:border-amber-900 dark:bg-amber-950/30",
  info: "border-navy-200 bg-white dark:border-navy-700 dark:bg-navy-900",
  success: "border-emerald-200 bg-emerald-50/70 dark:border-emerald-900 dark:bg-emerald-950/30",
};

const ACCENT = {
  danger: "text-red-700 dark:text-red-300",
  warning: "text-amber-700 dark:text-amber-300",
  info: "text-cobalt-700 dark:text-cobalt-300",
  success: "text-emerald-700 dark:text-emerald-300",
};

/**
 * The Action Inbox.
 *
 * Every item comes from the company's own records, through the API. There is
 * no fake urgency and no invented item: if the list is empty, the list is
 * empty.
 */
export function ActionInbox({ limit }) {
  const { t } = useTranslation();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api
      .get("/dashboard/inbox")
      .then((data) => {
        if (!active) return;
        setItems(data.items || []);
        setTotal(data.total || 0);
        setTruncated(Boolean(data.truncated));
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [t]);

  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        {error}
      </div>
    );
  }

  const shown = limit ? items.slice(0, limit) : items;

  if (!shown.length) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title={t("inbox.empty")}
        description={t("inbox.emptyBody")}
      />
    );
  }

  return (
    <div className="space-y-2">
      {truncated ? (
        <p className="pb-1 text-xs muted">
          {t("inbox.more", { shown: shown.length, total })}
        </p>
      ) : null}
      {shown.map((item) => {
        const Icon = ICONS[item.kind] || CircleHelp;
        return (
          <Link
            key={item.id}
            to={item.href}
            className={`flex items-start gap-3 rounded-xl border p-3 transition hover:border-navy-300 hover:shadow-card focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none dark:hover:border-navy-600 ${
              SEVERITY[item.severity] || SEVERITY.info
            }`}
          >
            <span
              className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/70 ${ACCENT[item.severity] || ACCENT.info} dark:bg-navy-900/70`}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="text-sm font-semibold text-navy-900 dark:text-white">
                  {item.title}
                </span>
                <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-navy-500 dark:text-navy-300">
                  {t(`inbox.kinds.${item.kind}`)}
                </span>
              </span>
              {item.description ? (
                <span className="mt-0.5 block text-xs leading-5 muted">{item.description}</span>
              ) : null}
              <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-navy-500 dark:text-navy-400">
                <span className="font-semibold text-cobalt-700 dark:text-cobalt-300">
                  {item.action_label}
                </span>
                {item.tender_title ? (
                  <span className="max-w-[16rem] truncate">{item.tender_title}</span>
                ) : null}
                {item.due_at ? (
                  <span>{formatDateTime(item.due_at, currentLocale())}</span>
                ) : null}
              </span>
            </span>
            <ArrowRight
              className="mt-1 h-4 w-4 shrink-0 text-navy-300 dark:text-navy-600"
              aria-hidden="true"
            />
          </Link>
        );
      })}
    </div>
  );
}
