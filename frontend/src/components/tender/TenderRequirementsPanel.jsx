import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CircleAlert,
  ExternalLink,
  Eye,
  FileText,
  Flag,
  Link2,
  Search,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";

import { api } from "../../lib/api";
import {
  MANDATORY_VALUES,
  REQUIREMENT_CATEGORIES,
  VERIFICATION_STATUSES,
  requirementQuery,
} from "../../lib/requirements";
import { cn, formatDate, formatDateTime } from "../../lib/utils";
import { currentLocale } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardContent } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Input, Select } from "../ui/Field";
import { KebabMenu } from "../ui/Menu";
import { Modal } from "../ui/Modal";
import { PillTabs } from "../ui/Tabs";
import { Skeleton } from "../ui/Spinner";

function StatusCell({ status, t }) {
  const meta =
    status === "verified"
      ? { Icon: CheckCircle2, className: "text-teal-600 dark:text-teal-300", key: "tenders.assessment.verified", fallback: "Verified" }
      : status === "needs_review"
        ? { Icon: AlertTriangle, className: "text-amber-500", key: "tenders.requirements.verification.needs_review", fallback: "Needs review" }
        : status === "rejected"
          ? { Icon: XCircle, className: "text-red-500", key: "tenders.requirements.verification.rejected", fallback: "Rejected" }
          : { Icon: CircleAlert, className: "text-navy-400", key: "tenders.requirements.notFound", fallback: "Not found" };
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[12px] font-medium", meta.className)}>
      <meta.Icon className="h-4 w-4 shrink-0" />
      {t(meta.key, { defaultValue: meta.fallback })}
    </span>
  );
}

export function TenderRequirementsPanel({ tenderId, refreshKey = 0 }) {
  const { t } = useTranslation();
  const toast = useToast();

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState({ total: 0, verified: 0, unverified: 0, needs_review: 0, documents: 0 });
  const [filters, setFilters] = useState({ category: "", verification_status: "", mandatory: "" });
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const [pageModal, setPageModal] = useState(null);
  const [pageText, setPageText] = useState(null);
  const [pageLoading, setPageLoading] = useState(false);

  const [evidenceModal, setEvidenceModal] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceNote, setEvidenceNote] = useState("");
  const [evidenceBusy, setEvidenceBusy] = useState(null);

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

  const visible = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return items;
    return items.filter((item) =>
      [item.title, item.excerpt, item.obligation, item.clause_reference]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term)),
    );
  }, [items, query]);

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

  const openEvidence = async (requirement) => {
    setEvidenceModal(requirement);
    setEvidenceData(null);
    setEvidenceNote("");
    setEvidenceLoading(true);
    try {
      const data = await api.get(
        `/tenders/${tenderId}/requirements/${requirement.id}/evidence`,
      );
      setEvidenceData(data);
      setEvidenceNote(data.note || "");
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setEvidenceLoading(false);
    }
  };

  const decideEvidence = async (candidate, status) => {
    if (!evidenceModal) return;
    setEvidenceBusy(candidate.document_id);
    try {
      const data = await api.post(
        `/tenders/${tenderId}/requirements/${evidenceModal.id}/evidence`,
        { document_id: candidate.document_id, status, note: evidenceNote || null },
      );
      setEvidenceData(data);
      setItems((current) =>
        current.map((item) =>
          item.id === evidenceModal.id
            ? {
                ...item,
                evidence_status: data.status,
                evidence_document_id: data.document_id,
                evidence_document_title: data.document_title,
              }
            : item,
        ),
      );
      if (status === "confirmed") toast.success(t("tenders.requirements.evidence.confirmedToast"));
      else if (status === "contradicted") toast.info(t("tenders.requirements.evidence.contradictedToast"));
      else toast.info(t("tenders.requirements.evidence.rejectedToast"));
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setEvidenceBusy(null);
    }
  };

  const statusPills = [
    { key: "", label: t("common.all"), count: summary.total },
    {
      key: "verified",
      label: t("tenders.assessment.verified", { defaultValue: "Verified" }),
      count: summary.verified,
      icon: CheckCircle2,
      tone: "green",
    },
    {
      key: "needs_review",
      label: t("tenders.requirements.verification.needs_review"),
      count: summary.needs_review || 0,
      icon: AlertTriangle,
      tone: "amber",
    },
    {
      key: "unverified",
      label: t("tenders.requirements.notFound", { defaultValue: "Not found" }),
      count: summary.unverified,
      icon: CircleAlert,
      tone: "neutral",
    },
  ];

  return (
    <Card>
      <CardContent className="p-0">
        <div className="flex flex-col gap-2.5 border-b border-navy-100 p-5 lg:flex-row lg:items-center dark:border-navy-800">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-300" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("tenders.requirements.searchPlaceholder")}
              aria-label={t("common.search")}
              className="h-9 rounded-lg border-navy-200 py-1.5 pl-9 text-[13px]"
            />
          </div>
          <div className="grid grid-cols-3 gap-2 lg:w-auto lg:shrink-0">
            <Select
              value={filters.category}
              onChange={updateFilter("category")}
              aria-label={t("tenders.requirements.filters.category")}
              className="h-9 rounded-lg border-navy-200 py-1.5 text-[12px]"
            >
              <option value="">{t("tenders.requirements.allSections")}</option>
              {REQUIREMENT_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {t(`tenders.requirements.categories.${category}`)}
                </option>
              ))}
            </Select>
            <Select
              value={filters.mandatory}
              onChange={updateFilter("mandatory")}
              aria-label={t("tenders.requirements.filters.mandatory")}
              className="h-9 rounded-lg border-navy-200 py-1.5 text-[12px]"
            >
              <option value="">{t("tenders.requirements.allTypes")}</option>
              {MANDATORY_VALUES.map((value) => (
                <option key={value} value={value}>
                  {t(`tenders.requirements.mandatoryValues.${value}`)}
                </option>
              ))}
            </Select>
            <Select
              value={filters.verification_status}
              onChange={updateFilter("verification_status")}
              aria-label={t("tenders.requirements.filters.verification")}
              className="h-9 rounded-lg border-navy-200 py-1.5 text-[12px]"
            >
              <option value="">{t("tenders.requirements.allStatuses")}</option>
              {VERIFICATION_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {t(`tenders.requirements.verification.${status}`)}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 px-5 pt-3.5">
          <PillTabs
            items={statusPills}
            value={filters.verification_status}
            onChange={(key) => setFilters((current) => ({ ...current, verification_status: key }))}
            ariaLabel={t("tenders.requirements.filters.verification")}
          />
        </div>

        {error ? (
          <div className="m-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="space-y-2 p-5">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : visible.length ? (
          <div className="table-scroll mt-2 overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left">
              <thead>
                <tr className="border-y border-navy-100 bg-navy-50/50 text-[11px] font-medium text-navy-500 dark:border-navy-800 dark:bg-navy-800/40 dark:text-navy-300">
                  <th scope="col" className="w-12 px-5 py-2.5 font-medium">#</th>
                  <th scope="col" className="px-3 py-2.5 font-medium">{t("tenders.requirements.requirement")}</th>
                  <th scope="col" className="w-32 px-3 py-2.5 font-medium">{t("tenders.requirements.type")}</th>
                  <th scope="col" className="w-36 px-3 py-2.5 font-medium">{t("common.status")}</th>
                  <th scope="col" className="w-44 px-3 py-2.5 font-medium">{t("tenders.requirements.source")}</th>
                  <th scope="col" className="w-32 px-5 py-2.5 text-right font-medium">{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((requirement, index) => {
                  const mandatory = requirement.mandatory === "yes";
                  return (
                    <tr
                      key={requirement.id}
                      className="border-b border-navy-100 align-top transition last:border-0 hover:bg-navy-50/50 dark:border-navy-800 dark:hover:bg-navy-800/30"
                    >
                      <td className="px-5 py-3.5 text-[12px] tabular-nums text-navy-400">
                        {index + 1}
                      </td>
                      <td className="px-3 py-3.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <p className="text-[13px] font-semibold leading-5 text-navy-900 dark:text-white">
                            {requirement.title}
                          </p>
                          {requirement.text_source === "ocr" ? (
                            <Badge tone="amber">{t("tenders.requirements.ocrBadge")}</Badge>
                          ) : null}
                          {requirement.evidence_status &&
                          requirement.evidence_status !== "none" ? (
                            <Badge tone={requirement.evidence_status === "confirmed" ? "green" : "neutral"}>
                              {t(`tenders.requirements.evidence.statuses.${requirement.evidence_status}`)}
                            </Badge>
                          ) : null}
                        </div>
                        <p className="mt-1 line-clamp-2 max-w-[560px] text-[12px] leading-5 text-navy-500 dark:text-navy-300">
                          {requirement.excerpt}
                        </p>
                      </td>
                      <td className="px-3 py-3.5">
                        <div className="flex flex-wrap gap-1">
                          <Badge tone="neutral">
                            {t(`tenders.requirements.categories.${requirement.category}`)}
                          </Badge>
                          {mandatory ? (
                            <Badge tone="amber">{t("tenders.requirements.mandatoryValues.yes")}</Badge>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-3.5">
                        <StatusCell status={requirement.verification_status} t={t} />
                      </td>
                      <td className="px-3 py-3.5">
                        <div className="flex items-start gap-2">
                          <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-navy-400" />
                          <div className="min-w-0">
                            {requirement.clause_reference ? (
                              <p className="truncate text-[12px] font-medium text-navy-700 dark:text-navy-200">
                                {t("tenders.requirements.clause", { ref: requirement.clause_reference })}
                              </p>
                            ) : null}
                            <p className="text-[11px] text-navy-500 dark:text-navy-300">
                              {t("tenders.requirements.pageShort", { page: requirement.page_index })}
                              {requirement.printed_page &&
                              requirement.printed_page !== String(requirement.page_index)
                                ? ` · ${t("tenders.requirements.printed", { label: requirement.printed_page })}`
                                : ""}
                            </p>
                            {requirement.form_reference ? (
                              <p className="truncate text-[11px] text-navy-400">
                                {t("tenders.requirements.form", { ref: requirement.form_reference })}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <Button size="sm" variant="outline" onClick={() => viewPage(requirement)}>
                            {t("tenders.assessment.view", { defaultValue: "View" })}
                          </Button>
                          <KebabMenu
                            label={t("common.actions")}
                            items={[
                              {
                                label: t("tenders.requirements.viewPage"),
                                icon: Eye,
                                onClick: () => viewPage(requirement),
                              },
                              {
                                label:
                                  requirement.evidence_status === "confirmed"
                                    ? t("tenders.requirements.evidence.review")
                                    : t("tenders.requirements.evidence.link"),
                                icon: Link2,
                                onClick: () => openEvidence(requirement),
                              },
                              requirement.verification_status !== "verified"
                                ? {
                                    label: t("tenders.requirements.confirm"),
                                    icon: Check,
                                    onClick: () => review(requirement, "verified"),
                                    disabled: busyId === requirement.id,
                                  }
                                : {
                                    label: t("tenders.requirements.flag"),
                                    icon: Flag,
                                    onClick: () => review(requirement, "needs_review"),
                                    disabled: busyId === requirement.id,
                                  },
                              requirement.verification_status !== "rejected"
                                ? {
                                    label: t("tenders.requirements.reject"),
                                    icon: X,
                                    danger: true,
                                    onClick: () => review(requirement, "rejected"),
                                    disabled: busyId === requirement.id,
                                  }
                                : null,
                              requirement.source_url
                                ? {
                                    label: t("tenders.requirements.source"),
                                    icon: ExternalLink,
                                    onClick: () =>
                                      window.open(requirement.source_url, "_blank", "noopener,noreferrer"),
                                  }
                                : null,
                            ]}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6">
            <EmptyState
              icon={Sparkles}
              title={t("tenders.requirements.emptyTitle")}
              description={
                summary.documents
                  ? t("tenders.requirements.emptyFiltered")
                  : t("tenders.requirements.emptyBody")
              }
            />
          </div>
        )}

        {!loading && visible.length ? (
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-navy-100 px-5 py-3 text-[11px] text-navy-400 dark:border-navy-800">
            <span>
              {t("tenders.requirements.showing", {
                shown: visible.length,
                total: query ? visible.length : total,
              })}
            </span>
            <span className="inline-flex items-center gap-1">
              <ShieldCheck className="h-3 w-3 text-teal-600" />
              {t("tenders.requirements.subtitle")}
            </span>
          </div>
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
            {pageText.text_source === "ocr" ? (
              <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                {t("tenders.requirements.ocrPageNote")}
              </div>
            ) : null}
            <div className="mb-2 flex items-center gap-2 text-xs muted">
              {pageText.has_text ? (
                <ShieldCheck className="h-3.5 w-3.5 text-teal-600" />
              ) : (
                <ShieldQuestion className="h-3.5 w-3.5 text-amber-600" />
              )}
              <span>{t("tenders.requirements.page", { page: pageText.page_index })}</span>
              {pageText.printed_label && pageText.printed_label !== String(pageText.page_index) ? (
                <span>{t("tenders.requirements.printed", { label: pageText.printed_label })}</span>
              ) : null}
            </div>
            <pre className="max-h-[30rem] overflow-auto whitespace-pre-wrap rounded-lg bg-navy-50 p-3 text-xs leading-5 text-navy-800 dark:bg-navy-950 dark:text-navy-100">
              {pageText.text || t("tenders.documentsPanel.pageNoText")}
            </pre>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(evidenceModal)}
        onClose={() => setEvidenceModal(null)}
        title={t("tenders.requirements.evidence.title")}
        description={evidenceModal?.title || ""}
        size="lg"
        footer={
          <Button variant="outline" onClick={() => setEvidenceModal(null)}>
            {t("common.close")}
          </Button>
        }
      >
        {evidenceLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : evidenceData ? (
          <div className="space-y-4">
            <p className="text-sm leading-6 muted">{t("tenders.requirements.evidence.help")}</p>

            {evidenceData.document_id ? (
              <div className="rounded-lg border border-teal-200 bg-teal-50 p-3 text-sm dark:border-teal-900 dark:bg-teal-950/40">
                <p className="font-semibold text-teal-900 dark:text-teal-100">
                  {t("tenders.requirements.evidence.current")}: {evidenceData.document_title}
                </p>
                <p className="mt-1 text-xs text-teal-800 dark:text-teal-200">
                  {t(`tenders.requirements.evidence.statuses.${evidenceData.status}`)}
                  {evidenceData.note ? ` · ${evidenceData.note}` : ""}
                </p>
              </div>
            ) : null}

            <div>
              <label htmlFor="evidence-note" className="text-xs font-semibold text-navy-700 dark:text-navy-200">
                {t("tenders.requirements.evidence.noteLabel")}
              </label>
              <textarea
                id="evidence-note"
                value={evidenceNote}
                onChange={(event) => setEvidenceNote(event.target.value)}
                rows={2}
                maxLength={1000}
                className="mt-1.5 w-full rounded-lg border border-navy-200 bg-white px-3 py-2 text-sm text-navy-900 outline-none transition focus:border-teal-400 focus:ring-2 focus:ring-teal-100 dark:border-navy-700 dark:bg-navy-900 dark:text-white dark:focus:ring-teal-900"
                placeholder={t("tenders.requirements.evidence.notePlaceholder")}
              />
            </div>

            {evidenceData.candidates.length ? (
              <div className="space-y-2">
                {evidenceData.candidates.map((candidate) => (
                  <article
                    key={candidate.document_id}
                    className="rounded-lg border border-navy-100 p-3 dark:border-navy-800"
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-navy-900 dark:text-white">
                          {candidate.title}
                        </p>
                        <p className="mt-0.5 text-xs muted">
                          {candidate.document_type}
                          {candidate.issuer ? ` · ${candidate.issuer}` : ""}
                          {candidate.expiry_date
                            ? ` · ${t("tenders.requirements.evidence.expires", {
                                date: formatDate(candidate.expiry_date, currentLocale()),
                              })}`
                            : ""}
                        </p>
                      </div>
                      <Badge tone={candidate.valid ? "teal" : "red"}>
                        {Math.round(candidate.score * 100)}%
                      </Badge>
                    </div>
                    {candidate.reasons.length ? (
                      <ul className="mt-2 space-y-0.5">
                        {candidate.reasons.map((reason) => (
                          <li key={reason} className="text-xs muted">
                            {reason}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {candidate.validity_note ? (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                        {candidate.validity_note}
                      </p>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <Button
                        size="sm"
                        variant="subtle"
                        onClick={() => decideEvidence(candidate, "confirmed")}
                        loading={evidenceBusy === candidate.document_id}
                        disabled={!candidate.valid}
                      >
                        <Check className="h-3.5 w-3.5" />
                        {t("tenders.requirements.evidence.confirm")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => decideEvidence(candidate, "contradicted")}
                        loading={evidenceBusy === candidate.document_id}
                      >
                        <ShieldQuestion className="h-3.5 w-3.5" />
                        {t("tenders.requirements.evidence.contradict")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => decideEvidence(candidate, "rejected")}
                        loading={evidenceBusy === candidate.document_id}
                      >
                        <X className="h-3.5 w-3.5" />
                        {t("tenders.requirements.evidence.reject")}
                      </Button>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={FileText}
                title={t("tenders.requirements.evidence.noCandidatesTitle")}
                description={t("tenders.requirements.evidence.noCandidatesBody")}
              />
            )}
          </div>
        ) : null}
      </Modal>
    </Card>
  );
}
