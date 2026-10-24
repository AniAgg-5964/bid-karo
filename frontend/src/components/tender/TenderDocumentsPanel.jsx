import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  Download,
  Eye,
  FileText,
  Link2,
  Package,
  Plus,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";

import { api } from "../../lib/api";
import { formatBytes, formatDateTime } from "../../lib/utils";
import { currentLocale } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { FieldError, Input, Label, Select } from "../ui/Field";
import { KebabMenu } from "../ui/Menu";
import { Modal } from "../ui/Modal";
import { PillTabs } from "../ui/Tabs";
import { Skeleton } from "../ui/Spinner";

const KINDS = ["main", "corrigendum", "boq", "form", "other"];
const MAX_BYTES = 25 * 1024 * 1024;

export function TenderDocumentsPanel({ tenderId, isSample = false, onExtracted }) {
  const { t } = useTranslation();
  const toast = useToast();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [kindFilter, setKindFilter] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [kind, setKind] = useState("main");
  const [title, setTitle] = useState("");
  const [formError, setFormError] = useState("");
  const [uploading, setUploading] = useState(false);

  const [showFetch, setShowFetch] = useState(false);
  const [url, setUrl] = useState("");
  const [urlKind, setUrlKind] = useState("main");
  const [urlBusy, setUrlBusy] = useState(false);
  const [urlError, setUrlError] = useState("");

  const [extractingId, setExtractingId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const [pagesDoc, setPagesDoc] = useState(null);
  const [pages, setPages] = useState([]);
  const [pagesLoading, setPagesLoading] = useState(false);
  const [selectedPage, setSelectedPage] = useState(null);
  const [pageLoading, setPageLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get(`/tenders/${tenderId}/documents`);
      setDocuments(data.items || []);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenderId]);

  useEffect(() => {
    if (!addOpen) {
      setFile(null);
      setKind("main");
      setTitle("");
      setFormError("");
      setUploading(false);
    }
  }, [addOpen]);

  const chooseFile = (candidate) => {
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".pdf")) {
      setFormError(t("tenders.documentsPanel.pdfOnly"));
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setFormError(t("tenders.documentsPanel.tooLarge"));
      return;
    }
    setFormError("");
    setFile(candidate);
    setTitle((current) => current || candidate.name.replace(/\.[^.]+$/, ""));
  };

  const upload = async (event) => {
    event.preventDefault();
    if (!file) {
      setFormError(t("tenders.documentsPanel.chooseFile"));
      return;
    }
    setFormError("");
    setUploading(true);
    try {
      const data = new FormData();
      data.append("file", file);
      data.append("kind", kind);
      if (title.trim()) data.append("title", title.trim());
      const document = await api.postForm(`/tenders/${tenderId}/documents`, data);
      toast.success(
        document.status === "extracted"
          ? t("tenders.documentsPanel.uploadedToast")
          : t("tenders.documentsPanel.uploadedNoTextToast"),
      );
      setAddOpen(false);
      await load();
    } catch (err) {
      setFormError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setUploading(false);
    }
  };

  const fetchFromUrl = async () => {
    if (!url.trim()) return;
    setUrlError("");
    setUrlBusy(true);
    try {
      const document = await api.post(`/tenders/${tenderId}/documents/fetch`, {
        url: url.trim(),
        kind: urlKind,
      });
      toast.success(
        document.status === "extracted"
          ? t("tenders.documentsPanel.uploadedToast")
          : t("tenders.documentsPanel.uploadedNoTextToast"),
      );
      setUrl("");
      await load();
    } catch (err) {
      setUrlError(
        err.message === "NETWORK_ERROR"
          ? t("errors.network")
          : err.message || t("tenders.documentsPanel.fetchBlocked"),
      );
    } finally {
      setUrlBusy(false);
    }
  };

  const extract = async (document) => {
    setExtractingId(document.id);
    try {
      const result = await api.post(`/tender-documents/${document.id}/extract`, {});
      if (result.status === "completed") toast.success(result.message);
      else toast.info(result.message);
      onExtracted?.();
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setExtractingId(null);
    }
  };

  const remove = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api.delete(`/tender-documents/${deleteTarget.id}`);
      toast.success(t("tenders.documentsPanel.deletedToast"));
      setDeleteTarget(null);
      await load();
      onExtracted?.();
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setDeleting(false);
    }
  };

  const openPages = (document) => {
    setPagesDoc(document);
    setPages([]);
    setSelectedPage(null);
  };

  useEffect(() => {
    if (!pagesDoc) return undefined;
    let active = true;
    setPagesLoading(true);
    api
      .get(`/tender-documents/${pagesDoc.id}/pages`)
      .then((data) => {
        if (!active) return;
        setPages(data.items || []);
        if (data.items?.length) {
          const first = data.items.find((page) => page.has_text) || data.items[0];
          openPage(first.page_index, active);
        }
      })
      .catch((err) => {
        if (active) toast.error(err.message || t("errors.generic"));
      })
      .finally(() => {
        if (active) setPagesLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagesDoc]);

  const openPage = async (pageIndex, stillActive) => {
    if (!pagesDoc) return;
    setPageLoading(true);
    try {
      const page = await api.get(`/tender-documents/${pagesDoc.id}/pages/${pageIndex}`);
      if (stillActive === false) return;
      setSelectedPage(page);
    } catch (err) {
      toast.error(err.message || t("errors.generic"));
    } finally {
      setPageLoading(false);
    }
  };

  const statusLabel = (status) =>
    t(`tenders.documentsPanel.statuses.${status}`, { defaultValue: status });

  const packages = documents.filter((document) => document.is_container);
  const standalone = documents.filter(
    (document) => !document.is_container && !document.parent_document_id,
  );

  const counts = useMemo(() => {
    const base = { all: standalone.length, main: 0, corrigendum: 0, form: 0, other: 0 };
    standalone.forEach((document) => {
      if (Object.prototype.hasOwnProperty.call(base, document.kind)) base[document.kind] += 1;
      else base.other += 1;
    });
    return base;
  }, [standalone]);

  const filtered = kindFilter ? standalone.filter((document) => document.kind === kindFilter) : standalone;
  const showPackages = !kindFilter && packages.length;
  const tabs = [
    {
      key: "",
      label: t("tenders.documentsPanel.allDocuments", { defaultValue: "All documents" }),
      count: counts.all,
    },
    { key: "main", label: t("tenders.documentsPanel.mainTenderTab"), count: counts.main },
    { key: "corrigendum", label: t("tenders.documentsPanel.addenda"), count: counts.corrigendum },
    { key: "form", label: t("tenders.documentsPanel.forms"), count: counts.form },
    { key: "other", label: t("tenders.documentsPanel.otherTab"), count: counts.other },
  ];

  return (
    <Card>
      <div className="flex flex-col gap-3 px-5 pb-4 pt-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-[15px] font-semibold text-navy-900 dark:text-white">
            {t("tenders.documentsPanel.title")}
          </h2>
          <p className="mt-1 text-[12.5px] leading-5 muted">{t("tenders.documentsPanel.subtitle")}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setShowFetch((value) => !value)}>
            <Link2 className="h-3.5 w-3.5" />
            {t("tenders.documentsPanel.fetchLink")}
          </Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" />
            {t("tenders.documentsPanel.addPdf")}
          </Button>
        </div>
      </div>

      <div className="space-y-4 px-5 pb-5">
        {isSample ? (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-[12px] text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{t("tenders.documentsPanel.sampleNote")}</p>
          </div>
        ) : null}

        {error ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={load}>
              {t("common.retry")}
            </Button>
          </div>
        ) : null}

        {showFetch ? (
          <div className="rounded-lg border border-dashed border-navy-200 p-3 dark:border-navy-700">
            <div className="flex items-center gap-2 text-[12px] font-semibold text-navy-700 dark:text-navy-200">
              <Link2 className="h-3.5 w-3.5" />
              {t("tenders.documentsPanel.urlTitle")}
            </div>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <Input
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder={t("tenders.documentsPanel.urlPlaceholder")}
                aria-label={t("tenders.documentsPanel.urlTitle")}
                className="h-9 flex-1 py-1.5 text-[13px]"
              />
              <Select
                value={urlKind}
                onChange={(event) => setUrlKind(event.target.value)}
                aria-label={t("tenders.documentsPanel.kind")}
                className="h-9 py-1.5 text-[13px] sm:w-44"
              >
                {KINDS.map((value) => (
                  <option key={value} value={value}>
                    {t(`tenders.documentsPanel.kinds.${value}`)}
                  </option>
                ))}
              </Select>
              <Button variant="outline" size="sm" onClick={fetchFromUrl} loading={urlBusy} disabled={!url.trim()}>
                {urlBusy ? t("tenders.documentsPanel.fetching") : t("tenders.documentsPanel.fetch")}
              </Button>
            </div>
            <p className="mt-2 text-[11px] muted">{t("tenders.documentsPanel.urlHelp")}</p>
            <FieldError>{urlError}</FieldError>
          </div>
        ) : null}

        {!loading ? (
          <PillTabs
            items={tabs}
            value={kindFilter}
            onChange={setKindFilter}
            ariaLabel={t("tenders.documentsPanel.kind")}
          />
        ) : null}

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : showPackages || filtered.length ? (
          <div className="space-y-2">
            {showPackages
              ? packages.map((pkg) => (
                  <div
                    key={pkg.id}
                    className="rounded-lg border border-navy-200 bg-navy-50/40 p-4 dark:border-navy-700 dark:bg-navy-900/40"
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300">
                        <Package className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">
                          {pkg.title}
                        </p>
                        <p className="text-xs muted">
                          {t("tenders.documentsPanel.packageFiles", {
                            count: pkg.package_summary?.stored ?? 0,
                            total: pkg.package_summary?.total ?? 0,
                          })}
                        </p>
                      </div>
                      <Badge tone="teal">{t("tenders.documentsPanel.kinds.package")}</Badge>
                    </div>
                    {pkg.package_summary?.skipped_files?.length ? (
                      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
                        <p className="font-semibold">
                          {t("tenders.documentsPanel.packageSkipped", {
                            count: pkg.package_summary.skipped_files.length,
                          })}
                        </p>
                        <ul className="mt-1 space-y-0.5">
                          {pkg.package_summary.skipped_files.map((member) => (
                            <li key={member.path}>
                              <span className="font-medium">{member.path}</span> - {member.reason}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <div className="mt-3 space-y-2">
                      {(pkg.package_summary?.members || []).map((member) => (
                        <div
                          key={member.path}
                          className="rounded-lg border border-navy-100 bg-white p-3 dark:border-navy-800 dark:bg-navy-900"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate text-sm font-medium text-navy-900 dark:text-white">
                              {member.title}
                            </p>
                            {member.status ? <Badge tone="neutral">{statusLabel(member.status)}</Badge> : null}
                            <Badge tone="neutral">
                              {t(`tenders.documentsPanel.kinds.${member.kind}`)}
                            </Badge>
                            <span className="text-[11px] muted">{member.path}</span>
                          </div>
                          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs muted">
                            <span>{t("tenders.documentsPanel.pages", { count: member.page_count || 0 })}</span>
                            <span>{formatBytes(member.size_bytes || 0)}</span>
                          </p>
                          {member.reason ? (
                            <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">{member.reason}</p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              : null}

            {filtered.map((document) => (
              <div
                key={document.id}
                className="flex flex-col gap-3 rounded-lg border border-navy-100 px-4 py-3.5 transition hover:border-navy-200 dark:border-navy-800 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-600 dark:bg-sky-900/40 dark:text-sky-300">
                    <FileText className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-[13px] font-semibold text-navy-900 dark:text-white">
                        {document.title}
                      </p>
                      <span
                        className={
                          document.status === "extracted"
                            ? "inline-flex items-center gap-1 text-[11px] font-medium text-teal-700 dark:text-teal-300"
                            : "inline-flex items-center gap-1 text-[11px] font-medium text-amber-600"
                        }
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-current" />
                        {statusLabel(document.status)}
                      </span>
                      {document.ocr_page_count > 0 ? (
                        <Badge tone="amber">
                          {t("tenders.documentsPanel.ocrPages", { count: document.ocr_page_count })}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-0.5 text-[11px] muted">
                      {t(`tenders.documentsPanel.kinds.${document.kind}`)} ·{" "}
                      {t("tenders.documentsPanel.pages", { count: document.page_count })} ·{" "}
                      {formatBytes(document.size_bytes)} ·{" "}
                      {formatDateTime(document.retrieved_at, currentLocale())}
                    </p>
                    {document.status === "no_text_layer" ? (
                      <p className="mt-1.5 rounded bg-amber-50 px-2 py-1 text-[11px] text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                        {t("tenders.documentsPanel.noTextHelp")}
                      </p>
                    ) : null}
                    {document.status === "failed" && document.error ? (
                      <p className="mt-1.5 rounded bg-red-50 px-2 py-1 text-[11px] text-red-700 dark:bg-red-950/40 dark:text-red-200">
                        {document.error}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap items-center gap-1 sm:justify-end">
                  <Button variant="ghost" size="sm" onClick={() => openPages(document)}>
                    <Eye className="h-3.5 w-3.5" />
                    {t("tenders.documentsPanel.viewPages")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      api.download(
                        `/tender-documents/${document.id}/download`,
                        document.original_filename,
                      )
                    }
                  >
                    <Download className="h-3.5 w-3.5" />
                    {t("tenders.documentsPanel.download")}
                  </Button>
                  <KebabMenu
                    label={t("common.actions")}
                    items={[
                      {
                        label:
                          extractingId === document.id
                            ? t("tenders.documentsPanel.extracting")
                            : t("tenders.documentsPanel.extract"),
                        icon: Sparkles,
                        onClick: () => extract(document),
                        disabled: document.status !== "extracted" || extractingId === document.id,
                      },
                      {
                        label: t("tenders.documentsPanel.delete"),
                        icon: Trash2,
                        danger: true,
                        onClick: () => setDeleteTarget(document),
                      },
                    ]}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={UploadCloud}
            title={t("tenders.documentsPanel.emptyTitle")}
            description={t("tenders.documentsPanel.emptyBody")}
            action={
              <Button size="sm" onClick={() => setAddOpen(true)}>
                <Plus className="h-4 w-4" />
                {t("tenders.documentsPanel.addPdf")}
              </Button>
            }
          />
        )}
      </div>

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t("tenders.documentsPanel.addTitle")}
        description={t("tenders.documentsPanel.addSubtitle")}
        footer={
          <>
            <Button variant="outline" onClick={() => setAddOpen(false)} disabled={uploading}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" form="tender-document-form" loading={uploading}>
              {uploading
                ? t("tenders.documentsPanel.uploading")
                : t("tenders.documentsPanel.upload")}
            </Button>
          </>
        }
      >
        <form id="tender-document-form" onSubmit={upload} className="space-y-4">
          {file ? (
            <div className="flex items-center gap-3 rounded-lg border border-teal-200 bg-teal-50/60 p-3 dark:border-teal-800 dark:bg-teal-900/30">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-teal-700 dark:bg-navy-900 dark:text-teal-300">
                <FileText className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">{file.name}</p>
                <p className="text-xs muted">{formatBytes(file.size)}</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setFile(null)}>
                {t("common.remove")}
              </Button>
            </div>
          ) : (
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-navy-200 bg-navy-50/50 px-6 py-8 text-center transition hover:border-teal-400 dark:border-navy-700 dark:bg-navy-800/40">
              <span className="mb-2 flex h-11 w-11 items-center justify-center rounded-lg bg-white text-teal-700 shadow-sm dark:bg-navy-900 dark:text-teal-300">
                <UploadCloud className="h-5 w-5" />
              </span>
              <span className="text-sm font-medium text-navy-800 dark:text-navy-100">
                {t("tenders.documentsPanel.drop")}
              </span>
              <span className="mt-1 text-xs muted">{t("tenders.documentsPanel.supported")}</span>
              <input
                type="file"
                accept="application/pdf,.pdf,.zip,application/zip,image/png,image/jpeg"
                className="hidden"
                onChange={(event) => chooseFile(event.target.files?.[0])}
              />
            </label>
          )}

          <FieldError>{formError}</FieldError>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="tender-document-title">{t("tenders.documentsPanel.titleLabel")}</Label>
              <Input
                id="tender-document-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="tender-document-kind">{t("tenders.documentsPanel.kind")}</Label>
              <Select
                id="tender-document-kind"
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                {KINDS.map((value) => (
                  <option key={value} value={value}>
                    {t(`tenders.documentsPanel.kinds.${value}`)}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(pagesDoc)}
        onClose={() => setPagesDoc(null)}
        title={t("tenders.documentsPanel.pagesTitle")}
        description={t("tenders.documentsPanel.pagesSubtitle")}
        size="lg"
        footer={
          <Button variant="outline" onClick={() => setPagesDoc(null)}>
            {t("common.close")}
          </Button>
        }
      >
        {pagesLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <div className="grid gap-4 sm:grid-cols-[9rem_1fr]">
            <div className="flex max-h-64 flex-wrap gap-1 overflow-y-auto sm:max-h-[26rem] sm:flex-col">
              {pages.map((page) => (
                <button
                  key={page.page_index}
                  type="button"
                  onClick={() => openPage(page.page_index)}
                  className={
                    selectedPage?.page_index === page.page_index
                      ? "rounded-md bg-teal-50 px-2.5 py-1.5 text-left text-xs font-semibold text-teal-800 dark:bg-teal-900/40 dark:text-teal-200"
                      : "rounded-md px-2.5 py-1.5 text-left text-xs font-medium text-navy-600 hover:bg-navy-50 dark:text-navy-300 dark:hover:bg-navy-800"
                  }
                >
                  {t("tenders.documentsPanel.page", { number: page.page_index })}
                  {page.printed_label && page.printed_label !== String(page.page_index) ? (
                    <span className="ml-1 text-[10px] opacity-70">({page.printed_label})</span>
                  ) : null}
                  {page.text_source === "ocr" ? (
                    <span className="ml-1 text-[10px] font-bold text-amber-600">OCR</span>
                  ) : !page.has_text ? (
                    <span className="ml-1 text-[10px] text-amber-600">!</span>
                  ) : null}
                </button>
              ))}
            </div>
            <div className="min-w-0">
              {pageLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : selectedPage ? (
                <div>
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs muted">
                    <span>{t("tenders.documentsPanel.page", { number: selectedPage.page_index })}</span>
                    {selectedPage.printed_label &&
                    selectedPage.printed_label !== String(selectedPage.page_index) ? (
                      <span>
                        {t("tenders.documentsPanel.printedPage", { label: selectedPage.printed_label })}
                      </span>
                    ) : null}
                  </div>
                  {selectedPage.text_source === "ocr" ? (
                    <p className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                      {t("tenders.documentsPanel.ocrPageNote")}
                    </p>
                  ) : null}
                  {selectedPage.has_text ? (
                    <pre className="max-h-[26rem] overflow-auto whitespace-pre-wrap rounded-lg bg-navy-50 p-3 text-xs leading-5 text-navy-800 dark:bg-navy-950 dark:text-navy-100">
                      {selectedPage.text}
                    </pre>
                  ) : (
                    <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                      {t("tenders.documentsPanel.pageNoText")}
                    </p>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title={t("tenders.documentsPanel.deleteTitle")}
        footer={
          <>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting}>
              {t("common.cancel")}
            </Button>
            <Button variant="danger" onClick={remove} loading={deleting}>
              {t("common.delete")}
            </Button>
          </>
        }
      >
        <p className="text-sm leading-6 muted">{t("tenders.documentsPanel.deleteBody")}</p>
      </Modal>
    </Card>
  );
}
