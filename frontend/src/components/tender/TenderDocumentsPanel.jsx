import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  Download,
  Eye,
  FileText,
  Link2,
  Plus,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";

import { api } from "../../lib/api";
import { formatBytes, formatDateTime } from "../../lib/utils";
import { currentLocale } from "../../i18n";
import { useToast } from "../../contexts/ToastContext";
import { Badge, StatusBadge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { FieldError, Input, Label, Select } from "../ui/Field";
import { Modal } from "../ui/Modal";
import { Skeleton } from "../ui/Spinner";

const KINDS = ["main", "corrigendum", "boq", "form", "other"];
const MAX_BYTES = 25 * 1024 * 1024;

export function TenderDocumentsPanel({ tenderId, isSample = false, onExtracted }) {
  const { t } = useTranslation();
  const toast = useToast();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [addOpen, setAddOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [kind, setKind] = useState("main");
  const [title, setTitle] = useState("");
  const [formError, setFormError] = useState("");
  const [uploading, setUploading] = useState(false);

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

  return (
    <Card>
      <CardHeader
        action={
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="h-4 w-4" />
            {t("tenders.documentsPanel.add")}
          </Button>
        }
      >
        <CardTitle>{t("tenders.documentsPanel.title")}</CardTitle>
        <CardDescription>{t("tenders.documentsPanel.subtitle")}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 pt-2">
        {isSample ? (
          <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{t("tenders.documentsPanel.sampleNote")}</p>
          </div>
        ) : null}

        {error ? (
          <div className="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={load}>
              {t("common.retry")}
            </Button>
          </div>
        ) : null}

        <div className="rounded-xl border border-dashed border-navy-200 p-3 dark:border-navy-700">
          <div className="flex items-center gap-2 text-xs font-semibold text-navy-700 dark:text-navy-200">
            <Link2 className="h-3.5 w-3.5" />
            {t("tenders.documentsPanel.urlTitle")}
          </div>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row">
            <Input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder={t("tenders.documentsPanel.urlPlaceholder")}
              aria-label={t("tenders.documentsPanel.urlTitle")}
              className="flex-1"
            />
            <Select
              value={urlKind}
              onChange={(event) => setUrlKind(event.target.value)}
              aria-label={t("tenders.documentsPanel.kind")}
              className="sm:w-44"
            >
              {KINDS.map((value) => (
                <option key={value} value={value}>
                  {t(`tenders.documentsPanel.kinds.${value}`)}
                </option>
              ))}
            </Select>
            <Button variant="outline" onClick={fetchFromUrl} loading={urlBusy} disabled={!url.trim()}>
              {urlBusy ? t("tenders.documentsPanel.fetching") : t("tenders.documentsPanel.fetch")}
            </Button>
          </div>
          <p className="mt-2 text-[11px] muted">{t("tenders.documentsPanel.urlHelp")}</p>
          <FieldError>{urlError}</FieldError>
        </div>

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : documents.length ? (
          <div className="space-y-3">
            {documents.map((document) => (
              <div
                key={document.id}
                className="rounded-xl border border-navy-100 p-4 dark:border-navy-800"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-navy-100 text-navy-600 dark:bg-navy-800 dark:text-navy-300">
                      <FileText className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">
                          {document.title}
                        </p>
                        <StatusBadge status={document.status} label={statusLabel(document.status)} />
                        <Badge tone="neutral">
                          {t(`tenders.documentsPanel.kinds.${document.kind}`)}
                        </Badge>
                      </div>
                      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs muted">
                        <span>
                          {t("tenders.documentsPanel.pages", { count: document.page_count })}
                        </span>
                        <span>
                          {t("tenders.documentsPanel.textPages", {
                            count: document.text_page_count,
                          })}
                        </span>
                        <span>{formatBytes(document.size_bytes)}</span>
                        <span>
                          {document.source === "downloaded"
                            ? t("tenders.documentsPanel.sourceDownloaded")
                            : t("tenders.documentsPanel.sourceUploaded")}
                        </span>
                        <span>{formatDateTime(document.retrieved_at, currentLocale())}</span>
                      </p>
                      {document.status === "no_text_layer" ? (
                        <p className="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                          {t("tenders.documentsPanel.noTextHelp")}
                        </p>
                      ) : null}
                      {document.status === "failed" && document.error ? (
                        <p className="mt-2 rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-200">
                          {document.error}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => openPages(document)}>
                      <Eye className="h-3.5 w-3.5" />
                      {t("tenders.documentsPanel.viewPages")}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
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
                    <Button
                      size="sm"
                      onClick={() => extract(document)}
                      loading={extractingId === document.id}
                      disabled={document.status !== "extracted"}
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      {extractingId === document.id
                        ? t("tenders.documentsPanel.extracting")
                        : t("tenders.documentsPanel.extract")}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setDeleteTarget(document)}
                      aria-label={t("tenders.documentsPanel.delete")}
                      title={t("tenders.documentsPanel.delete")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
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
                {t("tenders.documentsPanel.add")}
              </Button>
            }
          />
        )}
      </CardContent>

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
            <div className="flex items-center gap-3 rounded-xl border border-teal-200 bg-teal-50/60 p-3 dark:border-teal-800 dark:bg-teal-950/40">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-white text-teal-700 dark:bg-navy-900 dark:text-teal-300">
                <FileText className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">
                  {file.name}
                </p>
                <p className="text-xs muted">{formatBytes(file.size)}</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setFile(null)}>
                {t("common.remove")}
              </Button>
            </div>
          ) : (
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-navy-200 bg-navy-50/50 px-6 py-8 text-center transition hover:border-teal-400 dark:border-navy-700 dark:bg-navy-800/40">
              <span className="mb-2 flex h-11 w-11 items-center justify-center rounded-xl bg-white text-teal-700 shadow-sm dark:bg-navy-900 dark:text-teal-300">
                <UploadCloud className="h-5 w-5" />
              </span>
              <span className="text-sm font-medium text-navy-800 dark:text-navy-100">
                {t("tenders.documentsPanel.drop")}
              </span>
              <span className="mt-1 text-xs muted">
                {t("tenders.documentsPanel.supported")}
              </span>
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(event) => chooseFile(event.target.files?.[0])}
              />
            </label>
          )}

          <FieldError>{formError}</FieldError>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="tender-document-title">
                {t("tenders.documentsPanel.titleLabel")}
              </Label>
              <Input
                id="tender-document-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="tender-document-kind">
                {t("tenders.documentsPanel.kind")}
              </Label>
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
            <div className="flex max-h-64 flex-wrap gap-1.5 overflow-y-auto sm:max-h-[26rem] sm:flex-col">
              {pages.map((page) => (
                <button
                  key={page.page_index}
                  type="button"
                  onClick={() => openPage(page.page_index)}
                  className={
                    selectedPage?.page_index === page.page_index
                      ? "rounded-lg bg-teal-50 px-2.5 py-1.5 text-left text-xs font-semibold text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                      : "rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-navy-600 hover:bg-navy-50 dark:text-navy-300 dark:hover:bg-navy-800"
                  }
                >
                  {t("tenders.documentsPanel.page", { number: page.page_index })}
                  {page.printed_label && page.printed_label !== String(page.page_index) ? (
                    <span className="ml-1 text-[10px] opacity-70">({page.printed_label})</span>
                  ) : null}
                  {!page.has_text ? (
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
                    <span>
                      {t("tenders.documentsPanel.page", { number: selectedPage.page_index })}
                    </span>
                    {selectedPage.printed_label &&
                    selectedPage.printed_label !== String(selectedPage.page_index) ? (
                      <span>
                        {t("tenders.documentsPanel.printedPage", {
                          label: selectedPage.printed_label,
                        })}
                      </span>
                    ) : null}
                  </div>
                  {selectedPage.has_text ? (
                    <pre className="max-h-[26rem] overflow-auto whitespace-pre-wrap rounded-xl bg-navy-50 p-3 text-xs leading-5 text-navy-800 dark:bg-navy-950 dark:text-navy-100">
                      {selectedPage.text}
                    </pre>
                  ) : (
                    <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
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
