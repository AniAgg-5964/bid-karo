import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  CalendarClock,
  Download,
  FileText,
  Search,
  Trash2,
  TriangleAlert,
  Upload,
} from "lucide-react";

import { api } from "../lib/api";
import artEmptyEvidence from "../assets/art-empty-evidence.svg";
import { currentLocale } from "../i18n";
import { useToast } from "../contexts/ToastContext";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { Input, Select } from "../components/ui/Field";
import { Modal } from "../components/ui/Modal";
import { Skeleton } from "../components/ui/Spinner";
import { StatusBadge } from "../components/ui/Badge";
import { DocumentUploadModal } from "../components/documents/DocumentUploadModal";
import { cn, formatBytes, formatDate, isExpired } from "../lib/utils";

const TYPES = ["registration", "licence", "certification", "financial", "experience", "declaration", "other"];

export function DocumentsPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const [documents, setDocuments] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const firstLoad = useRef(true);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set("search", search.trim());
      if (type) params.set("document_type", type);
      params.set("limit", "100");
      const data = await api.get(`/documents?${params.toString()}`);
      setDocuments(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message || t("errors.generic"));
    } finally {
      setLoading(false);
      firstLoad.current = false;
    }
  }, [search, type, t]);

  useEffect(() => {
    const timer = window.setTimeout(load, firstLoad.current ? 0 : 220);
    return () => window.clearTimeout(timer);
  }, [load]);

  const hasFilters = Boolean(search.trim() || type);

  const download = async (document) => {
    try {
      await api.download(`/documents/${document.id}/download`, document.original_filename);
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message);
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await api.delete(`/documents/${pendingDelete.id}`);
      toast.success(t("documents.deleteSuccess"));
      setPendingDelete(null);
      await load();
    } catch (err) {
      toast.error(err.message === "NETWORK_ERROR" ? t("errors.network") : err.message);
    } finally {
      setDeleting(false);
    }
  };

  const empty = useMemo(() => {
    if (loading) return null;
    if (documents.length) return null;
    return hasFilters ? "filtered" : "empty";
  }, [loading, documents.length, hasFilters]);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("documents.title")}
        description={t("documents.subtitle")}
        actions={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="h-4 w-4" />
            {t("documents.upload")}
          </Button>
        }
      />

      <Card>
        <CardContent className="pb-0">
          <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-navy-400" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("documents.searchPlaceholder")}
                aria-label={t("documents.searchPlaceholder")}
                className="pl-9"
              />
            </div>
            <Select
              value={type}
              onChange={(event) => setType(event.target.value)}
              aria-label={t("documents.typeLabel")}
              className="sm:w-56"
            >
              <option value="">{t("documents.allTypes")}</option>
              {TYPES.map((item) => (
                <option key={item} value={item}>
                  {t(`documents.types.${item}`)}
                </option>
              ))}
            </Select>
            <p className="shrink-0 text-xs muted sm:ml-2">{t("documents.count", { count: total })}</p>
          </div>
        </CardContent>

        <CardContent className="pt-4">
          {error ? (
            <div className="flex flex-col items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/40 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-2">
                <TriangleAlert className="mt-0.5 h-4 w-4 text-red-600" />
                <p className="text-sm text-red-700 dark:text-red-200">{error}</p>
              </div>
              <Button variant="outline" size="sm" onClick={load}>
                {t("common.retry")}
              </Button>
            </div>
          ) : null}

          {loading && !documents.length ? (
            <div className="space-y-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : empty === "empty" ? (
            <EmptyState
              art={artEmptyEvidence}
              icon={FileText}
              title={t("documents.emptyTitle")}
              description={t("documents.emptyBody")}
              action={
                <Button variant="outline" size="sm" onClick={() => setUploadOpen(true)}>
                  <Upload className="h-3.5 w-3.5" />
                  {t("documents.upload")}
                </Button>
              }
            />
          ) : empty === "filtered" ? (
            <EmptyState icon={Search} title={t("documents.noResults")} />
          ) : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[680px] border-collapse text-left">
                  <thead>
                    <tr className="border-b border-navy-100 text-[11px] uppercase tracking-wide text-navy-500 dark:border-navy-800 dark:text-navy-300">
                      <th className="pb-2.5 font-semibold">{t("documents.columns.document")}</th>
                      <th className="pb-2.5 font-semibold">{t("documents.columns.type")}</th>
                      <th className="pb-2.5 font-semibold">{t("documents.columns.issuer")}</th>
                      <th className="pb-2.5 font-semibold">{t("documents.columns.validity")}</th>
                      <th className="pb-2.5 font-semibold">{t("documents.columns.status")}</th>
                      <th className="pb-2.5 text-right font-semibold">{t("common.actions")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-100 dark:divide-navy-800">
                    {documents.map((document) => {
                      const expired = isExpired(document.expiry_date);
                      return (
                        <tr key={document.id} className="group">
                          <td className="py-3 pr-4">
                            <div className="flex items-center gap-3">
                              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                                <FileText className="h-4 w-4" />
                              </span>
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">
                                  {document.title}
                                </p>
                                <p className="truncate text-xs muted">
                                  {document.original_filename} · {formatBytes(document.size_bytes)}
                                </p>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 pr-4 text-sm text-navy-700 dark:text-navy-200">
                            {t(`documents.types.${document.document_type}`, { defaultValue: document.document_type })}
                          </td>
                          <td className="py-3 pr-4 text-sm text-navy-700 dark:text-navy-200">
                            {document.issuer || "—"}
                          </td>
                          <td className="py-3 pr-4">
                            {document.expiry_date ? (
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1.5 text-xs",
                                  expired ? "font-medium text-red-600 dark:text-red-400" : "text-navy-600 dark:text-navy-300",
                                )}
                              >
                                <CalendarClock className="h-3.5 w-3.5" />
                                {expired
                                  ? t("documents.expired", { date: formatDate(document.expiry_date, currentLocale()) })
                                  : t("documents.expires", { date: formatDate(document.expiry_date, currentLocale()) })}
                              </span>
                            ) : (
                              <span className="text-xs muted">{t("documents.noExpiry")}</span>
                            )}
                          </td>
                          <td className="py-3 pr-4">
                            <StatusBadge
                              status={expired ? "expired" : document.verification_status}
                              label={
                                expired
                                  ? t("status.expired")
                                  : t(`status.${document.verification_status}`, {
                                      defaultValue: document.verification_status,
                                    })
                              }
                            />
                          </td>
                          <td className="py-3">
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => download(document)}
                                aria-label={t("common.download")}
                                title={t("common.download")}
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setPendingDelete(document)}
                                aria-label={t("common.delete")}
                                title={t("common.delete")}
                              >
                                <Trash2 className="h-4 w-4 text-red-600" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <ul className="space-y-2 md:hidden">
                {documents.map((document) => {
                  const expired = isExpired(document.expiry_date);
                  return (
                    <li
                      key={document.id}
                      className="rounded-xl border border-navy-100 p-3 dark:border-navy-800"
                    >
                      <div className="flex items-start gap-3">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
                          <FileText className="h-4 w-4" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold text-navy-900 dark:text-white">
                            {document.title}
                          </p>
                          <p className="truncate text-xs muted">
                            {t(`documents.types.${document.document_type}`, {
                              defaultValue: document.document_type,
                            })}{" "}
                            · {formatBytes(document.size_bytes)}
                          </p>
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <StatusBadge
                              status={expired ? "expired" : document.verification_status}
                              label={
                                expired
                                  ? t("status.expired")
                                  : t(`status.${document.verification_status}`, {
                                      defaultValue: document.verification_status,
                                    })
                              }
                            />
                            {document.expiry_date ? (
                              <span className={cn("text-[11px]", expired ? "text-red-600" : "muted")}>
                                {formatDate(document.expiry_date, currentLocale())}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </div>
                      <div className="mt-2 flex justify-end gap-1 border-t border-navy-100 pt-2 dark:border-navy-800">
                        <Button variant="ghost" size="sm" onClick={() => download(document)}>
                          <Download className="h-3.5 w-3.5" />
                          {t("common.download")}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setPendingDelete(document)}>
                          <Trash2 className="h-3.5 w-3.5 text-red-600" />
                          {t("common.delete")}
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </CardContent>
      </Card>

      <DocumentUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={load}
      />

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title={t("documents.deleteTitle")}
        description={t("documents.deleteBody")}
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setPendingDelete(null)} disabled={deleting}>
              {t("common.cancel")}
            </Button>
            <Button variant="danger" onClick={confirmDelete} loading={deleting}>
              {t("common.delete")}
            </Button>
          </>
        }
      >
        {pendingDelete ? (
          <div className="flex items-center gap-3 rounded-xl bg-navy-50 p-3 dark:bg-navy-800">
            <FileText className="h-5 w-5 text-navy-500" />
            <div>
              <p className="text-sm font-semibold text-navy-900 dark:text-white">{pendingDelete.title}</p>
              <p className="text-xs muted">{pendingDelete.original_filename}</p>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
