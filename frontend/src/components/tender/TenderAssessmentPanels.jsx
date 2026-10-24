import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  CalendarClock,
  Check,
  CheckCircle2,
  Circle,
  CircleAlert,
  Clock3,
  ExternalLink,
  FileText,
  ListChecks,
  RefreshCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
} from "lucide-react";

import { api } from "../../lib/api";
import { currentLocale } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { KebabMenu } from "../ui/Menu";
import { Modal } from "../ui/Modal";
import { Progress } from "../ui/Progress";
import { ScoreRing, scoreTone } from "../ui/ScoreRing";
import { PillTabs } from "../ui/Tabs";
import { Skeleton } from "../ui/Spinner";
import { cn, formatDate, formatDateTime } from "../../lib/utils";

const TASK_STATUSES = [
  "missing",
  "incomplete",
  "needs_verification",
  "in_progress",
  "complete",
  "not_applicable",
];

function gateTone(gate) {
  if (gate === "pass") return "green";
  if (gate === "fail") return "red";
  return "amber";
}

function bandTone(band) {
  if (band === "strong") return "green";
  if (band === "moderate") return "amber";
  if (band === "weak") return "amber";
  return "neutral";
}

function AssessmentSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

function ErrorCard({ error, onRetry, title }) {
  const { t } = useTranslation();
  return (
    <Card>
      <div className="py-10">
        <EmptyState
          icon={AlertTriangle}
          title={title}
          description={error || t("errors.generic")}
          action={
            <Button variant="outline" onClick={onRetry}>
              {t("common.retry")}
            </Button>
          }
        />
      </div>
    </Card>
  );
}

export function TenderScorePanel({ tenderId, onOpenTab }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.get(`/tenders/${tenderId}/assessment`));
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [tenderId, t]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <AssessmentSkeleton />;
  if (error || !data) {
    return <ErrorCard error={error} onRetry={load} title={t("tenders.assessment.errorTitle")} />;
  }

  const { score, eligibility, counts } = data;

  return (
    <Card>
      <div className="px-5 pt-5">
        <h2 className="text-[15px] font-semibold text-navy-900 dark:text-white">
          {t("tenders.assessment.scoreTitle")}
        </h2>
        <p className="mt-1 text-[12.5px] leading-5 muted">{t("tenders.assessment.scoreSubtitle")}</p>
      </div>

      <div className="grid gap-8 px-5 py-6 lg:grid-cols-[240px_1fr] lg:items-center">
        <div className="flex flex-col items-center text-center">
          <ScoreRing
            value={score.value}
            size={148}
            stroke={11}
            tone={bandTone(score.band)}
            suffix="/100"
            ariaLabel={t("tenders.assessment.softScore")}
          />
          <p
            className={cn(
              "mt-4 text-[14px] font-semibold",
              score.band === "strong"
                ? "text-teal-700 dark:text-teal-300"
                : score.band === "weak"
                  ? "text-red-600 dark:text-red-300"
                  : "text-amber-600 dark:text-amber-300",
            )}
          >
            {t(`tenders.assessment.bands.${score.band}`)}
          </p>
          <p className="mt-0.5 text-[11.5px] text-navy-400">
            {t("tenders.assessment.forProfile", { defaultValue: "for your business profile" })}
          </p>
        </div>

        <div>
          <p className="text-[12px] font-semibold text-navy-800 dark:text-navy-100">
            {t("tenders.assessment.scoreComponents", { defaultValue: "Score components" })}
          </p>
          <div className="mt-3 space-y-3">
            {score.dimensions.map((dimension) => (
              <div key={dimension.key}>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[12px] font-medium text-navy-700 dark:text-navy-200">
                    {t(`tenders.assessment.dimensions.${dimension.key}`, {
                      defaultValue: dimension.label,
                    })}
                  </p>
                  <span className="text-[11.5px] font-semibold tabular-nums text-navy-700 dark:text-navy-100">
                    {dimension.score}
                    <span className="font-normal text-navy-400">/100</span>
                  </span>
                </div>
                <Progress
                  value={dimension.score}
                  tone={scoreTone(dimension.score) === "red" ? "amber" : "teal"}
                  className="mt-1.5"
                />
                {dimension.reason ? (
                  <p className="mt-1 text-[11px] leading-4 text-navy-400">{dimension.reason}</p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-navy-100 px-5 py-3.5 dark:border-navy-800">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {[
            ["requirements", counts.total],
            ["verified", counts.verified],
            ["gating", counts.mandatory_gating],
            ["openTasks", counts.checklist_open],
          ].map(([key, value]) => (
            <span key={key} className="text-[11px] text-navy-500 dark:text-navy-300">
              {t(`tenders.assessment.counts.${key}`)}:{" "}
              <span className="font-semibold text-navy-800 dark:text-navy-100">{value}</span>
            </span>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" onClick={load} loading={loading}>
            <RefreshCw className="h-3.5 w-3.5" />
            {t("common.refresh")}
          </Button>
          <Button variant="outline" size="sm" onClick={() => onOpenTab?.("eligibility")}>
            <ShieldCheck className="h-3.5 w-3.5" />
            {t("tenders.assessment.openEligibility")}
          </Button>
          <Button variant="outline" size="sm" onClick={() => onOpenTab?.("tasks")}>
            <ListChecks className="h-3.5 w-3.5" />
            {t("tenders.assessment.openTasks")}
          </Button>
        </div>
      </div>
    </Card>
  );
}

export function TenderEligibilityPanel({ tenderId, onOpenTab }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api.get(`/tenders/${tenderId}/assessment`));
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [tenderId, t]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <AssessmentSkeleton />;
  if (error || !data) {
    return <ErrorCard error={error} onRetry={load} title={t("tenders.assessment.errorTitle")} />;
  }

  const { eligibility } = data;
  const total = eligibility.items.length;
  const percent = total ? Math.round((eligibility.pass_count / total) * 100) : 0;
  const gate =
    eligibility.status === "pass"
      ? {
          Icon: ShieldCheck,
          panel: "border-teal-200 bg-teal-50 dark:border-teal-900 dark:bg-teal-900/30",
          icon: "text-teal-600 dark:text-teal-300",
          title: "text-teal-900 dark:text-teal-100",
          body: "text-teal-800 dark:text-teal-200",
        }
      : eligibility.status === "fail"
        ? {
            Icon: ShieldAlert,
            panel: "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/40",
            icon: "text-red-500",
            title: "text-red-900 dark:text-red-100",
            body: "text-red-700 dark:text-red-200",
          }
        : {
            Icon: ShieldQuestion,
            panel: "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/40",
            icon: "text-amber-500",
            title: "text-amber-900 dark:text-amber-100",
            body: "text-amber-800 dark:text-amber-200",
          };

  return (
    <Card>
      <div className="px-5 pt-5">
        <h2 className="text-[15px] font-semibold text-navy-900 dark:text-white">
          {t("tenders.assessment.eligibilityTitle")}
        </h2>
        <p className="mt-1 text-[12.5px] leading-5 muted">
          {t("tenders.assessment.eligibilitySubtitle")}
        </p>
      </div>

      <div className="grid gap-8 px-5 py-6 lg:grid-cols-[260px_1fr] lg:items-center">
        <div className="flex items-center gap-5">
          <ScoreRing
            value={percent}
            display={eligibility.pass_count}
            suffix={`/${total}`}
            tone={eligibility.status === "pass" ? "green" : eligibility.status === "fail" ? "red" : "amber"}
            size={104}
            stroke={8}
            ariaLabel={`${eligibility.pass_count} of ${total}`}
          />
          <div className="space-y-2.5">
            <p className="inline-flex items-center gap-2 text-[12px] font-medium text-navy-700 dark:text-navy-200">
              <span className="h-2 w-2 rounded-full bg-teal-600" />
              {eligibility.pass_count} {t("tenders.assessment.verified", { defaultValue: "Verified" })}
            </p>
            <p className="inline-flex items-center gap-2 text-[12px] font-medium text-navy-700 dark:text-navy-200">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              {eligibility.unknown_count}{" "}
              {t("tenders.assessment.unknownShort", { defaultValue: "Unknown" })}
            </p>
            <p className="inline-flex items-center gap-2 text-[12px] font-medium text-navy-700 dark:text-navy-200">
              <span className="h-2 w-2 rounded-full bg-navy-300" />
              {eligibility.fail_count} {t("tenders.assessment.failed", { defaultValue: "Failed" })}
            </p>
          </div>
        </div>

        <div className={cn("flex items-start gap-3 rounded-lg border p-4", gate.panel)}>
          <gate.Icon className={cn("mt-0.5 h-5 w-5 shrink-0", gate.icon)} />
          <div>
            <p className={cn("text-[13px] font-semibold", gate.title)}>
              {t(`tenders.assessment.gate.${eligibility.status}`)}
            </p>
            <p className={cn("mt-1 text-[12.5px] leading-5", gate.body)}>{eligibility.message}</p>
            <button
              type="button"
              onClick={() => document.getElementById("eligibility-criteria")?.scrollIntoView({ behavior: "smooth", block: "start" })}
              className="mt-2 inline-flex items-center gap-1 text-[12px] font-semibold text-teal-700 hover:text-teal-900 dark:text-teal-300"
            >
              {t("tenders.assessment.viewMandatory", { defaultValue: "View mandatory criteria" })}
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>

      <div id="eligibility-criteria" className="border-t border-navy-100 px-5 py-5 dark:border-navy-800">
        {eligibility.items.length ? (
          <div className="space-y-2">
            {eligibility.items.map((item) => (
              <article
                key={item.requirement_id}
                className="rounded-lg border border-navy-100 px-4 py-3.5 dark:border-navy-800"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <h3 className="text-[13px] font-semibold text-navy-900 dark:text-white">{item.title}</h3>
                      <Badge tone={gateTone(item.gate)}>
                        {t(`tenders.assessment.gate.${item.gate}`)}
                      </Badge>
                      <Badge tone="neutral">{t(`tenders.requirements.categories.${item.category}`)}</Badge>
                      {item.mandatory === "yes" ? (
                        <Badge tone="amber">{t("tenders.requirements.mandatoryValues.yes")}</Badge>
                      ) : null}
                    </div>
                    <p className="mt-1.5 text-[12.5px] leading-5 text-navy-600 dark:text-navy-300">
                      {item.reason}
                    </p>
                    {item.evidence_document_title ? (
                      <p className="mt-1 inline-flex items-center gap-1.5 text-[11px] font-medium text-navy-600 dark:text-navy-300">
                        <FileText className="h-3.5 w-3.5" />
                        {item.evidence_document_title}
                      </p>
                    ) : null}
                    {item.profile_hints.length ? (
                      <ul className="mt-1 space-y-0.5">
                        {item.profile_hints.map((hint) => (
                          <li key={hint} className="text-[11px] leading-4 text-teal-700 dark:text-teal-300">
                            {hint}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <blockquote className="mt-2 border-l-2 border-teal-300 bg-teal-50/40 px-3 py-1.5 text-[11.5px] leading-5 text-navy-700 dark:border-teal-700 dark:bg-teal-900/20 dark:text-navy-200">
                      {item.excerpt}
                    </blockquote>
                    <p className="mt-1.5 text-[11px] text-navy-400">
                      {item.document_title || t("tenders.assessment.sourceDocument")} ·{" "}
                      {t("tenders.requirements.pageShort", { page: item.page_index })}
                      {item.clause_reference
                        ? ` · ${t("tenders.requirements.clause", { ref: item.clause_reference })}`
                        : ""}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="shrink-0"
                    onClick={() => onOpenTab?.("requirements")}
                  >
                    {t("tenders.assessment.reviewEvidenceShort", { defaultValue: "Review" })}
                  </Button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={ShieldQuestion}
            title={t("tenders.assessment.noEligibilityTitle")}
            description={t("tenders.assessment.noEligibilityBody")}
          />
        )}
      </div>
    </Card>
  );
}

function taskBucket(status) {
  if (status === "complete") return "complete";
  if (status === "in_progress") return "in_progress";
  return "not_started";
}

export function TenderTasksPanel({ tenderId, complianceOnly = false, phase = null }) {
  const { t } = useTranslation();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [filter, setFilter] = useState("all");
  const [detail, setDetail] = useState(null);
  const isPostAward = phase === "post_award";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = phase ? `?phase=${phase}` : "";
      const data = await api.get(`/tenders/${tenderId}/checklist${query}`);
      setItems(data.items || []);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [tenderId, t, phase]);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(
    () =>
      complianceOnly
        ? items.filter((item) => ["submission", "compliance"].includes(item.category))
        : items,
    [items, complianceOnly],
  );

  const counts = useMemo(() => {
    const base = { all: visible.length, complete: 0, in_progress: 0, not_started: 0 };
    visible.forEach((task) => {
      base[taskBucket(task.status)] += 1;
    });
    return base;
  }, [visible]);

  const filtered = filter === "all" ? visible : visible.filter((task) => taskBucket(task.status) === filter);
  const done = counts.complete;
  const percent = counts.all ? Math.round((done / counts.all) * 100) : 0;

  const generate = async () => {
    setGenerating(true);
    try {
      const endpoint = isPostAward
        ? `/tenders/${tenderId}/obligations/generate`
        : `/tenders/${tenderId}/checklist/generate`;
      const data = await api.post(endpoint, {});
      toast.success(data.message);
      await load();
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setGenerating(false);
    }
  };

  const update = async (task, changes) => {
    setBusyId(task.id);
    try {
      const updated = await api.patch(`/checklist/${task.id}`, changes);
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      if (detail?.id === updated.id) setDetail(updated);
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setBusyId(null);
    }
  };

  const title = isPostAward
    ? t("tenders.assessment.obligationsTitle")
    : complianceOnly
      ? t("tenders.assessment.complianceTitle")
      : t("tenders.assessment.tasksTitle");
  const subtitle = isPostAward
    ? t("tenders.assessment.obligationsSubtitle")
    : complianceOnly
      ? t("tenders.assessment.complianceSubtitle")
      : t("tenders.assessment.tasksSubtitle");

  return (
    <Card>
      <div className="flex flex-col gap-3 px-5 pt-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-[15px] font-semibold text-navy-900 dark:text-white">{title}</h2>
          <p className="mt-1 text-[12.5px] leading-5 muted">{subtitle}</p>
        </div>
        <Button variant="outline" size="sm" onClick={generate} loading={generating}>
          <RefreshCw className="h-3.5 w-3.5" />
          {isPostAward
            ? t("tenders.assessment.generateObligations")
            : t("tenders.assessment.generate")}
        </Button>
      </div>

      <div className="px-5 pt-5">
        <div className="flex items-center gap-3">
          <p className="shrink-0 text-[12px] font-medium text-navy-600 dark:text-navy-300">
            {t("tenders.assessment.checklistProgress", { done, total: counts.all })}
          </p>
          <Progress value={percent} className="flex-1" />
          <span className="w-9 shrink-0 text-right text-[11px] font-semibold text-navy-500 dark:text-navy-300">
            {percent}%
          </span>
        </div>

        <div className="mt-4">
          <PillTabs
            value={filter}
            onChange={setFilter}
            items={[
              { key: "all", label: t("tenders.assessment.allTasks"), count: counts.all },
              {
                key: "complete",
                label: t("tenders.assessment.completed"),
                count: counts.complete,
                icon: CheckCircle2,
                tone: "green",
              },
              {
                key: "in_progress",
                label: t("tenders.assessment.inProgress"),
                count: counts.in_progress,
                icon: Clock3,
                tone: "amber",
              },
              {
                key: "not_started",
                label: t("tenders.assessment.notStarted"),
                count: counts.not_started,
                icon: Circle,
              },
            ]}
          />
        </div>
      </div>

      {error ? (
        <div className="mx-5 mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="mt-3">
        {loading ? (
          <div className="space-y-2 px-5 pb-5">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : filtered.length ? (
          <ul className="divide-y divide-navy-100 border-t border-navy-100 dark:divide-navy-800 dark:border-navy-800">
            {filtered.map((task) => {
              const bucket = taskBucket(task.status);
              return (
                <li key={task.id} className="flex items-center gap-3 px-5 py-3.5">
                  <button
                    type="button"
                    disabled={busyId === task.id}
                    onClick={() => update(task, { status: bucket === "complete" ? "incomplete" : "complete" })}
                    className="shrink-0"
                    aria-label={t("checklist.status")}
                    title={t("checklist.status")}
                  >
                    {bucket === "complete" ? (
                      <CheckCircle2 className="h-5 w-5 text-teal-600" />
                    ) : bucket === "in_progress" ? (
                      <Clock3 className="h-5 w-5 text-blue-500" />
                    ) : (
                      <span className="block h-5 w-5 rounded-full border-2 border-navy-200 dark:border-navy-600" />
                    )}
                  </button>

                  <div className="min-w-0 flex-1">
                    <p
                      className={cn(
                        "truncate text-[13px] font-semibold text-navy-900 dark:text-white",
                        bucket === "complete" && "text-navy-500 dark:text-navy-300",
                      )}
                    >
                      {task.title}
                    </p>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-navy-400">
                      <span>{t(`status.${task.status}`, { defaultValue: task.status })}</span>
                      {task.category ? (
                        <span>{t(`tenders.requirements.categories.${task.category}`, { defaultValue: task.category })}</span>
                      ) : null}
                      {task.due_at ? (
                        <span className="inline-flex items-center gap-1">
                          <CalendarClock className="h-3 w-3" />
                          {formatDate(task.due_at, currentLocale())}
                        </span>
                      ) : null}
                      {task.phase === "post_award" && task.trigger_type ? (
                        <span>
                          {t(`tenders.assessment.triggerTypes.${task.trigger_type}`, {
                            defaultValue: task.trigger_type.replace(/_/g, " "),
                          })}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    className="shrink-0"
                    onClick={() => setDetail(task)}
                  >
                    {bucket === "complete"
                      ? t("tenders.assessment.view", { defaultValue: "View" })
                      : bucket === "in_progress"
                        ? t("tenders.assessment.continueAction", { defaultValue: "Continue" })
                        : t("tenders.assessment.start", { defaultValue: "Start" })}
                  </Button>

                  <KebabMenu
                    label={t("common.actions")}
                    items={TASK_STATUSES.filter((status) => status !== task.status).map((status) => ({
                      label: t(`status.${status}`, { defaultValue: status }),
                      onClick: () => update(task, { status }),
                      disabled: busyId === task.id,
                    }))}
                  />
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="px-5 pb-5">
            <EmptyState
              icon={ListChecks}
              title={isPostAward ? t("tenders.assessment.noObligationsTitle") : t("tenders.assessment.noTasksTitle")}
              description={isPostAward ? t("tenders.assessment.noObligationsBody") : t("tenders.assessment.noTasksBody")}
              action={
                <Button variant="outline" onClick={generate} loading={generating}>
                  {isPostAward ? t("tenders.assessment.generateObligations") : t("tenders.assessment.generate")}
                </Button>
              }
            />
          </div>
        )}
      </div>

      <Modal
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        title={detail?.title || ""}
        description={detail ? t(`status.${detail.status}`, { defaultValue: detail.status }) : ""}
        size="lg"
        footer={
          detail ? (
            <div className="flex w-full flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                {detail.status !== "in_progress" && detail.status !== "complete" ? (
                  <Button variant="outline" onClick={() => update(detail, { status: "in_progress" })} loading={busyId === detail.id}>
                    {t("tenders.assessment.start", { defaultValue: "Start" })}
                  </Button>
                ) : null}
                {detail.status !== "complete" ? (
                  <Button onClick={() => update(detail, { status: "complete" })} loading={busyId === detail.id}>
                    <Check className="h-4 w-4" />
                    {t("tenders.assessment.completed")}
                  </Button>
                ) : (
                  <Button variant="outline" onClick={() => update(detail, { status: "in_progress" })} loading={busyId === detail.id}>
                    {t("tenders.assessment.inProgress")}
                  </Button>
                )}
              </div>
              <Button variant="ghost" onClick={() => setDetail(null)}>
                {t("common.close")}
              </Button>
            </div>
          ) : null
        }
      >
        {detail ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge tone={gateTone(detail.status === "complete" ? "pass" : "unknown")}>
                {t(`status.${detail.status}`, { defaultValue: detail.status })}
              </Badge>
              {detail.category ? (
                <Badge tone="neutral">
                  {t(`tenders.requirements.categories.${detail.category}`, { defaultValue: detail.category })}
                </Badge>
              ) : null}
              {detail.due_at ? (
                <span className="inline-flex items-center gap-1 text-xs muted">
                  <CalendarClock className="h-3.5 w-3.5" />
                  {formatDate(detail.due_at, currentLocale())}
                </span>
              ) : null}
            </div>

            {detail.action ? (
              <p className="text-[13px] leading-6 text-navy-700 dark:text-navy-200">{detail.action}</p>
            ) : null}

            {detail.acceptance_criteria ? (
              <blockquote className="border-l-2 border-teal-300 bg-teal-50/40 px-3 py-2 text-[12px] leading-5 text-navy-700 dark:border-teal-700 dark:bg-teal-900/20 dark:text-navy-200">
                {detail.acceptance_criteria}
              </blockquote>
            ) : null}

            <dl className="grid gap-3 text-[12px] sm:grid-cols-2">
              <div>
                <dt className="font-semibold text-navy-500 dark:text-navy-300">{t("tenders.assessment.evidenceCheck")}</dt>
                <dd className="mt-0.5 text-navy-700 dark:text-navy-200">{detail.evidence_check || "-"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-navy-500 dark:text-navy-300">{t("tenders.assessment.issuer")}</dt>
                <dd className="mt-0.5 text-navy-700 dark:text-navy-200">{detail.issuer || "-"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-navy-500 dark:text-navy-300">{t("tenders.assessment.trigger")}</dt>
                <dd className="mt-0.5 text-navy-700 dark:text-navy-200">{detail.deadline_text || detail.trigger || "-"}</dd>
              </div>
              <div>
                <dt className="font-semibold text-navy-500 dark:text-navy-300">{t("tenders.requirements.consequence")}</dt>
                <dd className="mt-0.5 text-navy-700 dark:text-navy-200">{detail.consequence || "-"}</dd>
              </div>
            </dl>

            <p className="text-[11px] text-navy-400">
              {detail.source_document_title || t("tenders.assessment.sourceDocument")}
              {detail.page_index ? ` · ${t("tenders.requirements.pageShort", { page: detail.page_index })}` : ""}
              {detail.clause_reference
                ? ` · ${t("tenders.requirements.clause", { ref: detail.clause_reference })}`
                : ""}
              {detail.source_retrieved_at
                ? ` · ${t("tenders.requirements.retrieved", {
                    date: formatDateTime(detail.source_retrieved_at, currentLocale()),
                  })}`
                : ""}
            </p>
            {detail.source_url ? (
              <a
                href={detail.source_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 text-xs font-semibold text-teal-700 hover:underline dark:text-teal-300"
              >
                {t("tenders.requirements.source")}
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </Card>
  );
}

export function TenderLegalPanel({ tenderId }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    api
      .get(`/analysis/tenders/${tenderId}/legal-sources`)
      .then((response) => {
        if (active) setSources(response.items || []);
      })
      .catch(() => {
        if (active) setSources([]);
      });
    api
      .get(`/tenders/${tenderId}/legal`)
      .then((response) => {
        if (active) setData(response);
      })
      .catch((err) => {
        if (active) setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [tenderId, t]);

  if (loading) return <AssessmentSkeleton />;

  const sourcesFor = (requirementId) => sources.filter((source) => source.requirement_id === requirementId);

  return (
    <Card>
      <div className="px-5 pt-5">
        <h2 className="text-[15px] font-semibold text-navy-900 dark:text-white">
          {t("tenders.assessment.legalTitle")}
        </h2>
        <p className="mt-1 text-[12.5px] leading-5 muted">{t("tenders.assessment.legalSubtitle")}</p>
        {data?.disclaimer ? (
          <p className="mt-1 text-[11px] leading-5 text-navy-400">{data.disclaimer}</p>
        ) : null}
      </div>

      <div className="space-y-3 px-5 py-5">
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {data?.items?.length ? (
          <>
            {data.items.map((item) => (
              <article
                key={item.requirement_id}
                className="rounded-lg border border-navy-100 px-4 py-4 dark:border-navy-800"
              >
                <div className="flex items-start gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300">
                    <Scale className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <h3 className="text-[13px] font-semibold text-navy-900 dark:text-white">{item.title}</h3>
                      <Badge tone="neutral">{t(`tenders.requirements.categories.${item.category}`)}</Badge>
                      <span
                        className={cn(
                          "ml-auto inline-flex items-center gap-1 text-[11px] font-medium",
                          item.verification_status === "verified"
                            ? "text-teal-600 dark:text-teal-300"
                            : "text-amber-600",
                        )}
                      >
                        {item.verification_status === "verified" ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : (
                          <CircleAlert className="h-3.5 w-3.5" />
                        )}
                        {t(`tenders.requirements.verification.${item.verification_status}`)}
                      </span>
                    </div>

                    <p className="mt-2 text-[12.5px] leading-5 text-navy-600 dark:text-navy-300">{item.obligation}</p>
                    <blockquote className="mt-2 border-l-2 border-teal-300 bg-teal-50/40 px-3 py-1.5 text-[11.5px] leading-5 text-navy-700 dark:border-teal-700 dark:bg-teal-900/20 dark:text-navy-200">
                      {item.excerpt}
                    </blockquote>

                    {item.deadline_text ? (
                      <p className="mt-1.5 text-[11px] text-navy-600 dark:text-navy-300">
                        <span className="font-semibold">{t("tenders.requirements.deadline")}:</span>{" "}
                        {item.deadline_text}
                      </p>
                    ) : null}
                    {item.consequence_text ? (
                      <p className="mt-1 text-[11px] text-red-600 dark:text-red-300">
                        <span className="font-semibold">{t("tenders.requirements.consequence")}:</span>{" "}
                        {item.consequence_text}
                      </p>
                    ) : null}

                    <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[11px] text-navy-400">
                        {item.document_title || t("tenders.assessment.sourceDocument")} ·{" "}
                        {t("tenders.requirements.pageShort", { page: item.page_index })}
                        {item.clause_reference
                          ? ` · ${t("tenders.requirements.clause", { ref: item.clause_reference })}`
                          : ""}
                      </p>
                      {item.source_url ? (
                        <a
                          href={item.source_url}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="inline-flex items-center gap-1 rounded-md border border-navy-200 px-2.5 py-1 text-[11px] font-semibold text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
                        >
                          {t("tenders.requirements.viewSource", { defaultValue: "View source" })}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : null}
                    </div>

                    {sourcesFor(item.requirement_id).length ? (
                      <div className="mt-3 space-y-2 rounded-lg border border-navy-100 bg-navy-50/60 p-3 dark:border-navy-800 dark:bg-navy-800/50">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-navy-500">
                          {t("tenders.recommend.legalSources")}
                        </p>
                        {sourcesFor(item.requirement_id).map((source) => (
                          <div key={source.id} className="border-l-2 border-teal-300 pl-2">
                            <blockquote className="text-[11.5px] leading-5 text-navy-700 dark:text-navy-200">
                              {source.quote}
                            </blockquote>
                            <p className="mt-1 text-[10.5px] muted">
                              {t("tenders.recommend.legalRead")}:{" "}
                              {formatDateTime(source.retrieved_at, currentLocale())} · {source.source_class}
                            </p>
                            {source.gap ? (
                              <p className="mt-1 text-[10.5px] text-amber-800 dark:text-amber-200">{source.gap}</p>
                            ) : null}
                            {source.must_hold?.length ? (
                              <p className="mt-1 text-[10.5px] text-navy-600 dark:text-navy-300">
                                <span className="font-semibold">{t("tenders.recommend.legalMustHold")}:</span>{" "}
                                {source.must_hold.join("; ")}
                              </p>
                            ) : null}
                            {source.next_action ? (
                              <p className="mt-1 text-[10.5px] text-navy-600 dark:text-navy-300">
                                <span className="font-semibold">{t("tenders.recommend.legalNext")}:</span>{" "}
                                {source.next_action}
                              </p>
                            ) : null}
                            <a
                              href={source.source_url}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="mt-1 inline-flex items-center gap-1 text-[10.5px] font-semibold text-teal-700 hover:underline dark:text-teal-300"
                            >
                              {t("tenders.requirements.source")}
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </article>
            ))}
          </>
        ) : (
          <EmptyState
            icon={Scale}
            title={t("tenders.assessment.noLegalTitle")}
            description={t("tenders.assessment.noLegalBody")}
          />
        )}
      </div>
    </Card>
  );
}
