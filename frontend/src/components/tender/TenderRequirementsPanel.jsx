import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Check,
  ExternalLink,
  Eye,
  FileText,
  Flag,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  X,
} from "lucide-react";

import { api } from "../../lib/api";
import {
  MANDATORY_VALUES,
  REQUIREMENT_CATEGORIES,
  VERIFICATION_STATUSES,
  categoryTone,
  requirementQuery,
} from "../../lib/requirements";
import { cn, formatDateTime } from "../../lib/utils";
import { currentLocale } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { Badge, StatusBadge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Select } from "../ui/Field";
import { Modal } from "../ui/Modal";
import { Skeleton } from "../ui/Spinner";

function SummaryTile({ label, value, tone = "text-navy-900 dark:text-white" }) {
  return (
    <div className="rounded-xl bg-navy-50 p-3 dark:bg-navy-800">
      <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold", tone)}>{value}</p>
    </div>
  );
}

export function TenderRequirementsPanel({ tenderId, refreshKey = 0 }) {
  const { t } = useTranslation();
  const toast = useToast();

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState({ total: 0, verified: 0, unverified: 0, documents: 0 });
  const [filters, setFilters] = useState({ category: "", verification_status: "", mandatory: "" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const [pageModal, setPageModal] = useState(null);
  const [pageText, setPageText] = useState(null);
  const [pageLoading, setPageLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      api.get(`/tenders/${tenderId}/requirements${requirementQuery(filters)}`),
      api.get(`/tenders/${tenderId}/requirements/summary`),
    ])
      .then(([list, counts]) => {
        if (!active) return;
        setItems(list.items || []);
        setTotal(list.total || 0);
        setSummary(counts);
      })
      .catch((err) => {
        if (active) {
          setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenderId, refreshKey, filters.category, filters.verification_status, filters.mandatory]);

  const updateFilter = (field) => (event) =>
    setFilters((current) => ({ ...current, [field]: event.target.value }));

  const review = async (requirement, verificationStatus) => {
    setBusyId(requirement.id);
    try {
      const updated = await api.patch(`/requirements/${requirement.id}`, {
        verification_status: verificationStatus,
      });
      setItems((current) => {
        if (
          filters.verification_status &&
          updated.verification_status !== filters.verification_status
        ) {
          return current.filter((item) => item.id !== updated.id);
        }
        return current.map((item) => (item.id === updated.id ? updated : item));
      });
      if (
        filters.verification_status &&
        updated.verification_status !== filters.verification_status
      ) {
        setTotal((current) => Math.max(current - 1, 0));
      }
      const counts = await api.get(`/tenders/${tenderId}/requirements/summary`);
      setSummary(counts);
      if (verificationStatus === "verified") toast.success(t("tenders.requirements.confirmedToast"));
      else if (verificationStatus === "rejected") toast.info(t("tenders.requirements.rejectedToast"));
      else toast.info(t("tenders.requirements.flaggedToast"));
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setBusyId(null);
    }
  };

  const viewPage = async (requirement) => {
    setPageModal(requirement);
    setPageText(null);
    setPageLoading(true);
    try {
      const page = await api.get(
        `/tender-documents/${requirement.document_id}/pages/${requirement.page_index}`,
      );
      setPageText(page);
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setPageLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("tenders.requirements.title")}</CardTitle>
        <CardDescription>{t("tenders.requirements.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-2">
        <div className="grid gap-2 sm:grid-cols-4">
          <SummaryTile label={t("tenders.requirements.summary.total")} value={summary.total} />
          <SummaryTile
            label={t("tenders.requirements.summary.verified")}
            value={summary.verified}
            tone="text-emerald-700 dark:text-emerald-300"
          />
          <SummaryTile
            label={t("tenders.requirements.summary.unverified")}
            value={summary.unverified}
            tone="text-amber-700 dark:text-amber-300"
          />
          <SummaryTile label={t("tenders.requirements.summary.documents")} value={summary.documents} />
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          <Select
            value={filters.category}
            onChange={updateFilter("category")}
            aria-label={t("tenders.requirements.filters.category")}
          >
            <option value="">{t("tenders.requirements.filters.allCategories")}</option>
            {REQUIREMENT_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {t(`tenders.requirements.categories.${category}`)}
              </option>
            ))}
          </Select>
          <Select
            value={filters.verification_status}
            onChange={updateFilter("verification_status")}
            aria-label={t("tenders.requirements.filters.verification")}
          >
            <option value="">{t("tenders.requirements.filters.allVerification")}</option>
            {VERIFICATION_STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`tenders.requirements.verification.${status}`)}
              </option>
            ))}
          </Select>
          <Select
            value={filters.mandatory}
            onChange={updateFilter("mandatory")}
            aria-label={t("tenders.requirements.filters.mandatory")}
          >
            <option value="">{t("tenders.requirements.filters.allMandatory")}</option>
            {MANDATORY_VALUES.map((value) => (
              <option key={value} value={value}>
                {t(`tenders.requirements.mandatoryValues.${value}`)}
              </option>
            ))}
          </Select>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : items.length ? (
          <div className="space-y-3">
            {items.map((requirement) => (
              <article
                key={requirement.id}
                className="rounded-xl border border-navy-100 p-4 dark:border-navy-800"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-navy-900 dark:text-white">
                      {requirement.title}
                    </h3>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone={categoryTone(requirement.category)}>
                        {t(`tenders.requirements.categories.${requirement.category}`)}
                      </Badge>
                      <StatusBadge
                        status={requirement.verification_status}
                        label={t(
                          `tenders.requirements.verification.${requirement.verification_status}`,
                        )}
                      />
                      <Badge tone={requirement.mandatory === "yes" ? "amber" : "neutral"}>
                        {t(`tenders.requirements.mandatoryValues.${requirement.mandatory}`)}
                      </Badge>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-1.5">
                    <Button size="sm" variant="outline" onClick={() => viewPage(requirement)}>
                      <Eye className="h-3.5 w-3.5" />
                      {t("tenders.requirements.viewPage")}
                    </Button>
                    {requirement.verification_status !== "verified" ? (
                      <Button
                        size="sm"
                        variant="subtle"
                        onClick={() => review(requirement, "verified")}
                        loading={busyId === requirement.id}
                      >
                        <Check className="h-3.5 w-3.5" />
                        {t("tenders.requirements.confirm")}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => review(requirement, "needs_review")}
                        loading={busyId === requirement.id}
                      >
                        <Flag className="h-3.5 w-3.5" />
                        {t("tenders.requirements.flag")}
                      </Button>
                    )}
                    {requirement.verification_status !== "rejected" ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => review(requirement, "rejected")}
                        loading={busyId === requirement.id}
                        aria-label={t("tenders.requirements.reject")}
                        title={t("tenders.requirements.reject")}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    ) : null}
                  </div>
                </div>

                <blockquote className="mt-3 border-l-2 border-teal-300 bg-teal-50/50 px-3 py-2 text-sm leading-6 text-navy-800 dark:border-teal-700 dark:bg-teal-950/30 dark:text-navy-100">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-teal-700 dark:text-teal-300">
                    {t("tenders.requirements.excerpt")}
                  </p>
                  <p className="whitespace-pre-wrap">{requirement.excerpt}</p>
                </blockquote>

                {requirement.obligation && requirement.obligation !== requirement.excerpt ? (
                  <div className="mt-2">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-navy-400">
                      {t("tenders.requirements.interpretation")}
                    </p>
                    <p className="mt-1 text-sm leading-6 muted">{requirement.obligation}</p>
                  </div>
                ) : null}

                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs muted">
                  {requirement.document_title ? (
                    <span className="inline-flex max-w-full items-center gap-1">
                      <FileText className="h-3 w-3 shrink-0" />
                      <span className="truncate">{requirement.document_title}</span>
                    </span>
                  ) : null}
                  {requirement.document_retrieved_at ? (
                    <span>
                      {t("tenders.requirements.retrieved", {
                        date: formatDateTime(
                          requirement.document_retrieved_at,
                          currentLocale(),
                        ),
                      })}
                    </span>
                  ) : null}
                  <span>
                    {t("tenders.requirements.page", { page: requirement.page_index })}
                  </span>
                  {requirement.printed_page &&
                  requirement.printed_page !== String(requirement.page_index) ? (
                    <span>
                      {t("tenders.requirements.printed", { label: requirement.printed_page })}
                    </span>
                  ) : null}
                  {requirement.clause_reference ? (
                    <span>
                      {t("tenders.requirements.clause", { ref: requirement.clause_reference })}
                    </span>
                  ) : null}
                  {requirement.form_reference ? (
                    <span>
                      {t("tenders.requirements.form", { ref: requirement.form_reference })}
                    </span>
                  ) : null}
                  {requirement.source_url ? (
                    <a
                      href={requirement.source_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1 font-medium text-teal-700 hover:underline dark:text-teal-300"
                    >
                      {t("tenders.requirements.source")}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>

                {requirement.deadline_text ? (
                  <p className="mt-2 text-xs text-navy-700 dark:text-navy-200">
                    <span className="font-semibold">{t("tenders.requirements.deadline")}:</span>{" "}
                    {requirement.deadline_text}
                  </p>
                ) : null}
                {requirement.consequence_text ? (
                  <p className="mt-1 text-xs text-navy-700 dark:text-navy-200">
                    <span className="font-semibold">{t("tenders.requirements.consequence")}:</span>{" "}
                    {requirement.consequence_text}
                  </p>
                ) : null}

                {requirement.verification_status === "unverified" &&
                requirement.verification_notes ? (
                  <p className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                    {t("tenders.requirements.unverifiedNote", {
                      reason: requirement.verification_notes,
                    })}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Sparkles}
            title={t("tenders.requirements.emptyTitle")}
            description={
              summary.documents
                ? t("tenders.requirements.emptyFiltered")
                : t("tenders.requirements.emptyBody")
            }
          />
        )}

        {!loading && filters.category === "" && filters.verification_status === "" && filters.mandatory === "" && total > items.length ? (
          <p className="text-center text-xs muted">
            {t("tenders.requirements.showing", { shown: items.length, total })}
          </p>
        ) : null}
      </CardContent>

      <Modal
        open={Boolean(pageModal)}
        onClose={() => setPageModal(null)}
        title={t("tenders.requirements.pageModalTitle")}
        description={
          pageModal
            ? `${pageModal.title} · ${t("tenders.requirements.page", {
                page: pageModal.page_index,
              })}`
            : ""
        }
        size="lg"
        footer={
          <Button variant="outline" onClick={() => setPageModal(null)}>
            {t("common.close")}
          </Button>
        }
      >
        {pageLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : pageText ? (
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs muted">
              {pageText.has_text ? (
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              ) : (
                <ShieldQuestion className="h-3.5 w-3.5 text-amber-600" />
              )}
              <span>
                {t("tenders.requirements.page", { page: pageText.page_index })}
              </span>
              {pageText.printed_label && pageText.printed_label !== String(pageText.page_index) ? (
                <span>
                  {t("tenders.requirements.printed", { label: pageText.printed_label })}
                </span>
              ) : null}
            </div>
            <pre className="max-h-[30rem] overflow-auto whitespace-pre-wrap rounded-xl bg-navy-50 p-3 text-xs leading-5 text-navy-800 dark:bg-navy-950 dark:text-navy-100">
              {pageText.text || t("tenders.documentsPanel.pageNoText")}
            </pre>
          </div>
        ) : null}
      </Modal>
    </Card>
  );
}
