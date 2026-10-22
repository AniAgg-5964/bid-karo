import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ExternalLink,
  FileText,
  Loader2,
  PanelRightClose,
  ShieldCheck,
  ShieldQuestion,
  TriangleAlert,
  X,
} from "lucide-react";

import { api } from "../../lib/api";
import { splitAroundExcerpt } from "../../lib/excerpt";
import { requirementTrust } from "../../lib/trust";
import { currentLocale } from "../../i18n";
import { formatDateTime } from "../../lib/utils";
import { Button } from "../ui/Button";
import { ProvenanceBadge } from "../ui/ProvenanceBadge";
import { Skeleton } from "../ui/Spinner";

/**
 * The Evidence Dock.
 *
 * It opens the real source of a requirement: the stored page of the stored
 * document, with the cited words highlighted where they actually appear. It
 * never claims that a citation was opened when it could not be, and it says
 * plainly when the text on screen is the tender's own words and when it is
 * our reading of them.
 */
export function EvidenceDock({ open, onClose, requirement, tenderId, documentTitle }) {
  const { t } = useTranslation();
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notFound, setNotFound] = useState(false);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open || !requirement) {
      setPage(null);
      setError("");
      setNotFound(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError("");
    setNotFound(false);
    setPage(null);

    api
      .get(`/tender-documents/${requirement.document_id}/pages/${requirement.page_index}`)
      .then((data) => {
        if (active) setPage(data);
      })
      .catch((err) => {
        if (!active) return;
        if (err.status === 404) {
          setNotFound(true);
        } else {
          setError(
            err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"),
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [open, requirement?.id, requirement?.document_id, requirement?.page_index, t]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const trust = requirement ? requirementTrust(requirement) : null;
  const parts = page && requirement ? splitAroundExcerpt(page.text, requirement.excerpt) : null;
  const citedFound = Boolean(parts?.found);

  /*
    One panel, two shapes. On a small screen it is a full-screen sheet; on a
    wide screen it sits beside the content. It is one element, not two, so a
    screen reader never reads the same thing twice.
  */
  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-navy-950/45 backdrop-blur-[2px] lg:hidden"
        aria-label={t("dock.close")}
        onClick={onClose}
      />
      <aside
        className="fixed inset-0 z-50 flex w-full flex-col bg-white animate-dock-in-mobile lg:inset-y-0 lg:left-auto lg:right-0 lg:z-40 lg:w-[min(460px,42vw)] lg:border-l lg:border-navy-100 lg:shadow-dock lg:animate-dock-in dark:bg-navy-900 dark:lg:border-navy-800"
        role="dialog"
        aria-modal="true"
        aria-label={t("dock.title")}
      >
        <DockHeader
          title={requirement?.title}
          subtitle={documentTitle || requirement?.document_title}
          onClose={onClose}
          closeRef={closeRef}
        />
        <DockBody
          requirement={requirement}
          tenderId={tenderId}
          page={page}
          loading={loading}
          error={error}
          notFound={notFound}
          parts={parts}
          citedFound={citedFound}
          trust={trust}
        />
      </aside>
    </>
  );
}

function DockHeader({ title, subtitle, onClose, closeRef }) {
  const { t } = useTranslation();
  return (
    <header className="flex items-start gap-3 border-b border-navy-100 px-5 py-4 dark:border-navy-800">
      <div className="min-w-0 flex-1">
        <p className="eyebrow">{t("dock.title")}</p>
        <h2 className="mt-1 truncate text-sm font-semibold text-navy-900 dark:text-white">
          {title || t("dock.noRequirement")}
        </h2>
        {subtitle ? (
          <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs muted">
            <FileText className="h-3 w-3 shrink-0" aria-hidden="true" />
            <span className="truncate">{subtitle}</span>
          </p>
        ) : null}
      </div>
      <button
        ref={closeRef}
        type="button"
        onClick={onClose}
        className="rounded-lg p-1.5 text-navy-500 transition hover:bg-navy-100 hover:text-navy-900 focus-visible:ring-2 focus-visible:ring-teal-600 dark:hover:bg-navy-800 dark:hover:text-white"
        aria-label={t("dock.close")}
        title={t("dock.close")}
      >
        <PanelRightClose className="h-4 w-4" aria-hidden="true" />
      </button>
    </header>
  );
}

function DockBody({
  requirement,
  tenderId,
  page,
  loading,
  error,
  notFound,
  parts,
  citedFound,
  trust,
}) {
  const { t } = useTranslation();

  if (!requirement) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm muted">
        {t("dock.noRequirement")}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 space-y-3 overflow-y-auto p-5">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-28 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <TriangleAlert className="h-7 w-7 text-amber-600" aria-hidden="true" />
        <p className="text-sm font-semibold text-navy-900 dark:text-white">
          {t("dock.sourceUnavailable")}
        </p>
        <p className="max-w-xs text-xs leading-5 muted">{t("dock.sourceUnavailableBody")}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-5">
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-5 overflow-y-auto p-5">
      {/* What this panel is showing, said plainly. */}
      <section className="space-y-2">
        <p className="eyebrow">{t("dock.citedWording")}</p>
        <blockquote className="excerpt">{requirement.excerpt}</blockquote>
        {trust ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <ProvenanceBadge
              state={trust.state}
              tone={trust.tone}
              icon={trust.icon}
              label={t(`trust.states.${trust.state}`)}
            />
            {requirement.text_source === "ocr" ? (
              <ProvenanceBadge
                state="unverified"
                tone="review"
                icon="shield-question"
                label={t("trust.ocrSource")}
              />
            ) : null}
          </div>
        ) : null}
      </section>

      {/* Where it came from. */}
      <section className="surface-quiet space-y-2 p-3.5">
        <p className="eyebrow">{t("dock.source")}</p>
        <dl className="space-y-1.5 text-xs">
          <MetaRow label={t("dock.document")} value={requirement.document_title || "—"} />
          <MetaRow
            label={t("dock.page")}
            value={
              requirement.printed_page && requirement.printed_page !== String(requirement.page_index)
                ? `${requirement.page_index} (${t("tenders.requirements.printed", { label: requirement.printed_page })})`
                : String(requirement.page_index)
            }
          />
          {requirement.clause_reference ? (
            <MetaRow label={t("dock.clause")} value={requirement.clause_reference} />
          ) : null}
          {requirement.document_retrieved_at ? (
            <MetaRow
              label={t("dock.retrieved")}
              value={formatDateTime(requirement.document_retrieved_at, currentLocale())}
            />
          ) : null}
          {requirement.source_url ? (
            <div className="pt-0.5">
              <dt className="font-semibold text-navy-700 dark:text-navy-200">{t("dock.sourceUrl")}</dt>
              <dd className="mt-0.5">
                <a
                  href={requirement.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex items-center gap-1 break-all font-medium text-cobalt-700 hover:underline dark:text-cobalt-300"
                >
                  {requirement.source_url}
                  <ExternalLink className="h-3 w-3 shrink-0" aria-hidden="true" />
                </a>
              </dd>
            </div>
          ) : null}
        </dl>
      </section>

      {/* The page itself. */}
      <section className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p className="eyebrow">{t("dock.pageText")}</p>
          {page?.text_source === "ocr" ? (
            <ProvenanceBadge
              state="unverified"
              tone="review"
              icon="shield-question"
              label={t("trust.ocrSource")}
              size="sm"
            />
          ) : (
            <ProvenanceBadge
              state="source_verified"
              tone="verified"
              icon="shield-check"
              label={t("trust.exactSourceText")}
              size="sm"
            />
          )}
        </div>

        {citedFound ? (
          <div className="surface-quiet max-h-[46vh] overflow-y-auto p-3.5">
            <p className="whitespace-pre-wrap text-[13px] leading-6 text-navy-800 dark:text-navy-100">
              {parts.before}
              <mark className="cited">{parts.cited}</mark>
              {parts.after}
            </p>
          </div>
        ) : (
          <div className="surface-quiet max-h-[46vh] overflow-y-auto p-3.5">
            <p className="mb-2 flex items-start gap-1.5 rounded-lg bg-amber-50 px-2.5 py-2 text-[11px] leading-5 text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
              <ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {t("dock.citedNotFound")}
            </p>
            <p className="whitespace-pre-wrap text-[13px] leading-6 text-navy-800 dark:text-navy-100">
              {page?.text || t("tenders.documentsPanel.pageNoText")}
            </p>
          </div>
        )}
      </section>

      {/* The way to the whole document. */}
      <section className="space-y-2">
        <p className="eyebrow">{t("dock.next")}</p>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              window.location.href = `/app/tenders/${tenderId}?tab=documents&document=${requirement.document_id}`;
            }}
          >
            <FileText className="h-3.5 w-3.5" />
            {t("dock.openDocument")}
          </Button>
          {requirement.source_url ? (
            <a
              href={requirement.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-navy-200 bg-white px-3 text-xs font-semibold text-navy-700 transition hover:border-navy-300 hover:bg-navy-50 dark:border-navy-700 dark:bg-navy-900 dark:text-navy-100 dark:hover:bg-navy-800"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {t("tenders.requirements.source")}
            </a>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function MetaRow({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 font-semibold text-navy-600 dark:text-navy-300">{label}</dt>
      <dd className="min-w-0 truncate text-right text-navy-900 dark:text-navy-100" title={String(value)}>
        {value}
      </dd>
    </div>
  );
}
