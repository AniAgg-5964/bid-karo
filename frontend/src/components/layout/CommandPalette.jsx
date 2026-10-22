import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  Building2,
  ClipboardCheck,
  CornerDownLeft,
  FileText,
  Loader2,
  Search,
  Settings,
  Compass,
  LayoutDashboard,
} from "lucide-react";

import { api } from "../../lib/api";
import { cn } from "../../lib/utils";

const DESTINATIONS = [
  { key: "dashboard", to: "/app/dashboard", icon: LayoutDashboard, group: "nav" },
  { key: "discover", to: "/app/discover", icon: Compass, group: "nav" },
  { key: "tenders", to: "/app/tenders", icon: FileText, group: "nav" },
  { key: "checklist", to: "/app/checklist", icon: ClipboardCheck, group: "nav" },
  { key: "documents", to: "/app/documents", icon: FileText, group: "nav" },
  { key: "changes", to: "/app/changes", icon: FileText, group: "nav" },
  { key: "company", to: "/app/company", icon: Building2, group: "nav" },
  { key: "settings", to: "/app/settings", icon: Settings, group: "nav" },
];

/**
 * The command palette.
 *
 * It searches the company's own records through the API, so the results are
 * the records the user is allowed to see. Nothing is faked and nothing is
 * shown that the API did not return.
 */
export function CommandPalette({ open = false, onClose: onCloseProp }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [records, setRecords] = useState({ tenders: [], documents: [], tasks: [] });
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const close = useCallback(() => {
    onCloseProp?.();
    setQuery("");
    setActive(0);
  }, [onCloseProp]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(timer);
  }, [open]);

  // The records are fetched once, when the palette opens, and filtered as
  // the user types.
  useEffect(() => {
    if (!open) return;
    let activeRequest = true;
    setLoading(true);
    Promise.all([
      api.get("/tenders").catch(() => ({ items: [] })),
      api.get("/documents?limit=50").catch(() => ({ items: [] })),
      api.get("/checklist").catch(() => ({ items: [] })),
    ])
      .then(([tenders, documents, checklist]) => {
        if (!activeRequest) return;
        setRecords({
          tenders: tenders?.items || [],
          documents: documents?.items || [],
          tasks: checklist?.items || [],
        });
      })
      .finally(() => {
        if (activeRequest) setLoading(false);
      });
    return () => {
      activeRequest = false;
    };
  }, [open]);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matches = (value) => !needle || String(value || "").toLowerCase().includes(needle);

    const destinations = DESTINATIONS.filter((item) => matches(t(`nav.${item.key}`))).map(
      (item) => ({
        id: `nav-${item.key}`,
        kind: "nav",
        title: t(`nav.${item.key}`),
        hint: t("palette.destination"),
        to: item.to,
        icon: item.icon,
      }),
    );

    const tenders = records.tenders
      .filter((item) => matches(item.title) || matches(item.reference_number) || matches(item.authority))
      .slice(0, 6)
      .map((item) => ({
        id: `tender-${item.id}`,
        kind: "tender",
        title: item.title,
        hint: [item.reference_number, item.authority].filter(Boolean).join(" · "),
        to: `/app/tenders/${item.id}`,
        icon: FileText,
      }));

    const documents = records.documents
      .filter((item) => matches(item.title) || matches(item.document_type))
      .slice(0, 5)
      .map((item) => ({
        id: `document-${item.id}`,
        kind: "document",
        title: item.title,
        hint: item.document_type,
        to: "/app/documents",
        icon: FileText,
      }));

    const tasks = records.tasks
      .filter((item) => matches(item.title) || matches(item.evidence_check))
      .slice(0, 5)
      .map((item) => ({
        id: `task-${item.id}`,
        kind: "task",
        title: item.title,
        hint: item.status,
        to: item.tender_id ? `/app/tenders/${item.tender_id}?tab=tasks` : "/app/checklist",
        icon: ClipboardCheck,
      }));

    return [...destinations, ...tenders, ...documents, ...tasks];
  }, [query, records, t]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  useEffect(() => {
    if (!listRef.current) return;
    const node = listRef.current.querySelector(`[data-index="${active}"]`);
    node?.scrollIntoView({ block: "nearest" });
  }, [active, results.length]);

  const go = useCallback(
    (item) => {
      if (!item) return;
      close();
      navigate(item.to);
    },
    [close, navigate],
  );

  const onKeyDown = (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((value) => (results.length ? (value + 1) % results.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((value) => (results.length ? (value - 1 + results.length) % results.length : 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      go(results[active]);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center px-4 pt-[12vh]">
      <button
        type="button"
        className="absolute inset-0 bg-navy-950/45 backdrop-blur-[2px]"
        aria-label={t("palette.close")}
        onClick={close}
      />
      <div
        className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-navy-100 bg-white shadow-pop animate-fade-in dark:border-navy-700 dark:bg-navy-900"
        role="dialog"
        aria-modal="true"
        aria-label={t("palette.title")}
      >
        <div className="flex items-center gap-2.5 border-b border-navy-100 px-4 dark:border-navy-800">
          <Search className="h-4 w-4 shrink-0 text-navy-400" aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t("palette.placeholder")}
            aria-label={t("palette.placeholder")}
            className="h-12 w-full bg-transparent text-sm text-navy-900 outline-none placeholder:text-navy-400 dark:text-navy-50"
          />
          {loading ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-navy-400" aria-hidden="true" /> : null}
          <kbd className="hidden shrink-0 rounded border border-navy-200 px-1.5 py-0.5 text-[10px] font-semibold text-navy-500 sm:inline dark:border-navy-700 dark:text-navy-300">
            Esc
          </kbd>
        </div>

        <div ref={listRef} className="max-h-[52vh] overflow-y-auto p-1.5">
          {results.length ? (
            <ul role="listbox" aria-label={t("palette.title")}>
              {results.map((item, index) => {
                const Icon = item.icon;
                return (
                  <li key={item.id} role="option" aria-selected={index === active}>
                    <button
                      type="button"
                      data-index={index}
                      onMouseEnter={() => setActive(index)}
                      onClick={() => go(item)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition",
                        index === active
                          ? "bg-teal-50 text-navy-900 dark:bg-teal-950/60 dark:text-white"
                          : "text-navy-700 hover:bg-navy-50 dark:text-navy-200 dark:hover:bg-navy-800",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0 text-navy-400" aria-hidden="true" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{item.title}</span>
                        {item.hint ? (
                          <span className="mt-0.5 block truncate text-xs muted">{item.hint}</span>
                        ) : null}
                      </span>
                      <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-navy-500 dark:text-navy-300">
                        {t(`palette.kinds.${item.kind}`)}
                      </span>
                      {index === active ? (
                        <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-navy-400" aria-hidden="true" />
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="px-4 py-10 text-center">
              <p className="text-sm font-medium text-navy-800 dark:text-navy-100">
                {t("palette.empty")}
              </p>
              <p className="mt-1 text-xs muted">{t("palette.emptyBody")}</p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-navy-100 px-4 py-2 text-[11px] text-navy-500 dark:border-navy-800 dark:text-navy-400">
          <span className="inline-flex items-center gap-1.5">
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
            {t("palette.hint")}
          </span>
          <span>{t("palette.count", { count: results.length })}</span>
        </div>
      </div>
    </div>
  );
}
