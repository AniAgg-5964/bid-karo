import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  CalendarClock,
  ExternalLink,
  FileText,
  Gauge,
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
import { Badge, StatusBadge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Select } from "../ui/Field";
import { Skeleton } from "../ui/Spinner";
import { cn, formatDate } from "../../lib/utils";

const TASK_STATUSES = [
  "missing",
  "incomplete",
  "needs_verification",
  "in_progress",
  "complete",
  "not_applicable",
];

function gateTone(gate) {
  if (gate === "pass") return "emerald";
  if (gate === "fail") return "red";
  return "amber";
}

function bandTone(band) {
  if (band === "strong") return "emerald";
  if (band === "moderate") return "teal";
  if (band === "weak") return "amber";
  return "neutral";
}

function GateBanner({ status, message }) {
  const { t } = useTranslation();
  const Icon = status === "pass" ? ShieldCheck : status === "fail" ? ShieldAlert : ShieldQuestion;
  const classes =
    status === "pass"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100"
      : status === "fail"
        ? "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-100"
        : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100";
  return (
    <div className={cn("flex items-start gap-3 rounded-xl border p-4", classes)}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div>
        <p className="text-sm font-semibold">
          {t(`tenders.assessment.gate.${status}`)}
        </p>
        <p className="mt-1 text-sm leading-6">{message}</p>
      </div>
    </div>
  );
}

function AssessmentSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

export function TenderScorePanel({ tenderId, onOpenTab }) {
  const { t } = useTranslation();
  const toast = useToast();
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
    return (
      <Card>
        <CardContent className="py-10">
          <EmptyState
            icon={AlertTriangle}
            title={t("tenders.assessment.errorTitle")}
            description={error || t("errors.generic")}
            action={<Button variant="outline" onClick={load}>{t("common.retry")}</Button>}
          />
        </CardContent>
      </Card>
    );
  }

  const { score, eligibility, counts } = data;
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-teal-700" />
            <CardTitle>{t("tenders.assessment.scoreTitle")}</CardTitle>
          </div>
          <CardDescription>{t("tenders.assessment.scoreSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5 pt-3">
          <GateBanner status={eligibility.status} message={eligibility.message} />

          <div className="grid gap-5 lg:grid-cols-[220px_1fr] lg:items-center">
            <div className="rounded-2xl bg-navy-50 p-5 text-center dark:bg-navy-800">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-navy-400">
                {t("tenders.assessment.softScore")}
              </p>
              <p className="mt-2 text-5xl font-semibold tracking-tight text-navy-900 dark:text-white">
                {score.value}
                <span className="text-lg text-navy-400">/100</span>
              </p>
              <Badge tone={bandTone(score.band)} className="mt-2">
                {t(`tenders.assessment.bands.${score.band}`)}
              </Badge>
              <p className="mt-3 text-xs leading-5 muted">{score.explanation}</p>
            </div>

            <div className="space-y-4">
              {score.dimensions.map((dimension) => (
                <div key={dimension.key}>
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <p className="font-semibold text-navy-800 dark:text-navy-100">
                      {t(`tenders.assessment.dimensions.${dimension.key}`, {
                        defaultValue: dimension.label,
                      })}
                      <span className="ml-1.5 font-normal text-navy-400">
                        {dimension.weight}%
                      </span>
                    </p>
                    <span className="font-semibold text-navy-700 dark:text-navy-200">
                      {dimension.score}/100
                    </span>
                  </div>
                  <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-navy-100 dark:bg-navy-800">
                    <div
                      className="h-full rounded-full bg-teal-500"
                      style={{ width: `${Math.min(dimension.score, 100)}%` }}
                    />
                  </div>
                  <p className="mt-1 text-xs leading-5 muted">{dimension.reason}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-4">
            {[
              ["requirements", counts.total],
              ["verified", counts.verified],
              ["gating", counts.mandatory_gating],
              ["openTasks", counts.checklist_open],
            ].map(([key, value]) => (
              <div key={key} className="rounded-xl bg-navy-50 p-3 dark:bg-navy-800">
                <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                  {t(`tenders.assessment.counts.${key}`)}
                </p>
                <p className="mt-1 text-lg font-semibold text-navy-900 dark:text-white">{value}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={load} loading={loading}>
          <RefreshCw className="h-4 w-4" />
          {t("common.refresh")}
        </Button>
        <Button variant="subtle" onClick={() => onOpenTab?.("eligibility")}>
          <ShieldCheck className="h-4 w-4" />
          {t("tenders.assessment.openEligibility")}
        </Button>
        <Button variant="subtle" onClick={() => onOpenTab?.("tasks")}>
          <ListChecks className="h-4 w-4" />
          {t("tenders.assessment.openTasks")}
        </Button>
      </div>
    </div>
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
    return (
      <Card>
        <CardContent className="py-10">
          <EmptyState
            icon={AlertTriangle}
            title={t("tenders.assessment.errorTitle")}
            description={error || t("errors.generic")}
            action={<Button variant="outline" onClick={load}>{t("common.retry")}</Button>}
          />
        </CardContent>
      </Card>
    );
  }

  const { eligibility } = data;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-teal-700" />
          <CardTitle>{t("tenders.assessment.eligibilityTitle")}</CardTitle>
        </div>
        <CardDescription>{t("tenders.assessment.eligibilitySubtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-3">
        <GateBanner status={eligibility.status} message={eligibility.message} />

        <div className="grid gap-2 sm:grid-cols-3">
          {[
            ["pass", eligibility.pass_count, "text-emerald-700 dark:text-emerald-300"],
            ["fail", eligibility.fail_count, "text-red-700 dark:text-red-300"],
            ["unknown", eligibility.unknown_count, "text-amber-700 dark:text-amber-300"],
          ].map(([key, value, tone]) => (
            <div key={key} className="rounded-xl bg-navy-50 p-3 dark:bg-navy-800">
              <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                {t(`tenders.assessment.gate.${key}`)}
              </p>
              <p className={cn("mt-1 text-2xl font-semibold", tone)}>{value}</p>
            </div>
          ))}
        </div>

        {eligibility.items.length ? (
          <div className="space-y-3">
            {eligibility.items.map((item) => (
              <article key={item.requirement_id} className="rounded-xl border border-navy-100 p-4 dark:border-navy-800">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-navy-900 dark:text-white">{item.title}</h3>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone={gateTone(item.gate)}>
                        {t(`tenders.assessment.gate.${item.gate}`)}
                      </Badge>
                      <Badge tone="neutral">{t(`tenders.requirements.categories.${item.category}`)}</Badge>
                      <Badge tone="amber">{t(`tenders.requirements.mandatoryValues.${item.mandatory}`)}</Badge>
                    </div>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => onOpenTab?.("requirements")}>
                    {t("tenders.assessment.reviewEvidence")}
                  </Button>
                </div>
                <p className="mt-3 text-sm leading-6 text-navy-700 dark:text-navy-200">{item.reason}</p>
                {item.evidence_document_title ? (
                  <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-navy-700 dark:text-navy-200">
                    <FileText className="h-3.5 w-3.5" />
                    {item.evidence_document_title}
                  </p>
                ) : null}
                {item.profile_hints.length ? (
                  <ul className="mt-2 space-y-1">
                    {item.profile_hints.map((hint) => (
                      <li key={hint} className="text-xs leading-5 text-teal-800 dark:text-teal-200">
                        {hint}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <blockquote className="mt-3 border-l-2 border-teal-300 bg-teal-50/50 px-3 py-2 text-xs leading-5 text-navy-800 dark:border-teal-700 dark:bg-teal-950/30 dark:text-navy-100">
                  {item.excerpt}
                </blockquote>
                <p className="mt-2 text-xs muted">
                  {item.document_title || t("tenders.assessment.sourceDocument")} · {t("tenders.requirements.page", { page: item.page_index })}
                  {item.clause_reference ? ` · ${t("tenders.requirements.clause", { ref: item.clause_reference })}` : ""}
                </p>
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
      </CardContent>
    </Card>
  );
}

export function TenderTasksPanel({ tenderId, complianceOnly = false }) {
  const { t } = useTranslation();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get(`/tenders/${tenderId}/checklist`);
      setItems(data.items || []);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [tenderId, t]);

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

  const generate = async () => {
    setGenerating(true);
    try {
      const data = await api.post(`/tenders/${tenderId}/checklist/generate`, {});
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
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-teal-700" />
              <CardTitle>
                {complianceOnly
                  ? t("tenders.assessment.complianceTitle")
                  : t("tenders.assessment.tasksTitle")}
              </CardTitle>
            </div>
            <CardDescription>
              {complianceOnly
                ? t("tenders.assessment.complianceSubtitle")
                : t("tenders.assessment.tasksSubtitle")}
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={generate} loading={generating}>
            <RefreshCw className="h-3.5 w-3.5" />
            {t("tenders.assessment.generate")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-3">
        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : visible.length ? (
          visible.map((task) => (
            <article key={task.id} className="rounded-xl border border-navy-100 p-4 dark:border-navy-800">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-navy-900 dark:text-white">{task.title}</h3>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <StatusBadge
                      status={task.status}
                      label={t(`status.${task.status}`, { defaultValue: task.status })}
                    />
                    {task.category ? (
                      <Badge tone="neutral">
                        {t(`tenders.requirements.categories.${task.category}`, {
                          defaultValue: task.category,
                        })}
                      </Badge>
                    ) : null}
                    {task.due_at ? (
                      <span className="inline-flex items-center gap-1 text-xs muted">
                        <CalendarClock className="h-3.5 w-3.5" />
                        {formatDate(task.due_at, currentLocale())}
                      </span>
                    ) : null}
                  </div>
                </div>
                <Select
                  className="w-full sm:w-44"
                  value={task.status}
                  onChange={(event) => update(task, { status: event.target.value })}
                  disabled={busyId === task.id}
                  aria-label={t("checklist.status")}
                >
                  {TASK_STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {t(`status.${status}`, { defaultValue: status })}
                    </option>
                  ))}
                </Select>
              </div>

              {task.action ? (
                <p className="mt-3 text-sm leading-6 text-navy-700 dark:text-navy-200">{task.action}</p>
              ) : null}
              {task.acceptance_criteria ? (
                <blockquote className="mt-2 border-l-2 border-teal-300 bg-teal-50/50 px-3 py-2 text-xs leading-5 text-navy-800 dark:border-teal-700 dark:bg-teal-950/30 dark:text-navy-100">
                  {task.acceptance_criteria}
                </blockquote>
              ) : null}
              <dl className="mt-2 grid gap-1.5 text-xs sm:grid-cols-2">
                <div>
                  <dt className="font-semibold text-navy-500 dark:text-navy-300">
                    {t("tenders.assessment.evidenceCheck")}
                  </dt>
                  <dd className="text-navy-700 dark:text-navy-200">{task.evidence_check || "-"}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-navy-500 dark:text-navy-300">
                    {t("tenders.assessment.issuer")}
                  </dt>
                  <dd className="text-navy-700 dark:text-navy-200">{task.issuer || "-"}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-navy-500 dark:text-navy-300">
                    {t("tenders.assessment.trigger")}
                  </dt>
                  <dd className="text-navy-700 dark:text-navy-200">
                    {task.deadline_text || task.trigger || "-"}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold text-navy-500 dark:text-navy-300">
                    {t("tenders.requirements.consequence")}
                  </dt>
                  <dd className="text-navy-700 dark:text-navy-200">{task.consequence || "-"}</dd>
                </div>
              </dl>
              <p className="mt-2 text-xs muted">
                {task.source_document_title || t("tenders.assessment.sourceDocument")}
                {task.page_index ? ` · ${t("tenders.requirements.page", { page: task.page_index })}` : ""}
                {task.clause_reference
                  ? ` · ${t("tenders.requirements.clause", { ref: task.clause_reference })}`
                  : ""}
              </p>
            </article>
          ))
        ) : (
          <EmptyState
            icon={ListChecks}
            title={t("tenders.assessment.noTasksTitle")}
            description={t("tenders.assessment.noTasksBody")}
            action={
              <Button variant="outline" onClick={generate} loading={generating}>
                {t("tenders.assessment.generate")}
              </Button>
            }
          />
        )}
      </CardContent>
    </Card>
  );
}

export function TenderLegalPanel({ tenderId }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
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

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Scale className="h-4 w-4 text-teal-700" />
          <CardTitle>{t("tenders.assessment.legalTitle")}</CardTitle>
        </div>
        <CardDescription>{t("tenders.assessment.legalSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 pt-3">
        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        ) : null}
        {data?.items?.length ? (
          <>
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              {data.disclaimer}
            </div>
            {data.items.map((item) => (
              <article key={item.requirement_id} className="rounded-xl border border-navy-100 p-4 dark:border-navy-800">
                <div className="flex flex-wrap items-center gap-1.5">
                  <h3 className="text-sm font-semibold text-navy-900 dark:text-white">{item.title}</h3>
                  <Badge tone="neutral">{t(`tenders.requirements.categories.${item.category}`)}</Badge>
                  <StatusBadge
                    status={item.verification_status}
                    label={t(`tenders.requirements.verification.${item.verification_status}`)}
                  />
                </div>
                <p className="mt-2 text-sm leading-6 text-navy-700 dark:text-navy-200">{item.obligation}</p>
                <blockquote className="mt-2 border-l-2 border-teal-300 bg-teal-50/50 px-3 py-2 text-xs leading-5 text-navy-800 dark:border-teal-700 dark:bg-teal-950/30 dark:text-navy-100">
                  {item.excerpt}
                </blockquote>
                {item.deadline_text ? (
                  <p className="mt-2 text-xs text-navy-700 dark:text-navy-200">
                    <span className="font-semibold">{t("tenders.requirements.deadline")}:</span>{" "}
                    {item.deadline_text}
                  </p>
                ) : null}
                {item.consequence_text ? (
                  <p className="mt-1 text-xs text-red-700 dark:text-red-300">
                    <span className="font-semibold">{t("tenders.requirements.consequence")}:</span>{" "}
                    {item.consequence_text}
                  </p>
                ) : null}
                <p className="mt-2 text-xs muted">
                  {item.document_title || t("tenders.assessment.sourceDocument")} ·{" "}
                  {t("tenders.requirements.page", { page: item.page_index })}
                  {item.clause_reference
                    ? ` · ${t("tenders.requirements.clause", { ref: item.clause_reference })}`
                    : ""}
                </p>
                {item.source_url ? (
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-teal-700 hover:underline dark:text-teal-300"
                  >
                    {t("tenders.requirements.source")}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : null}
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
      </CardContent>
    </Card>
  );
}
