import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  Compass,
  ExternalLink,
  FileSearch,
  Info,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Input, Label } from "../components/ui/Field";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { Spinner } from "../components/ui/Spinner";
import { useToast } from "../contexts/ToastContext";
import { api, ApiError } from "../lib/api";
import { cn, formatDate, formatDateTime, formatNumber } from "../lib/utils";
import { fetchStatusTone, scorePercent, scoreTone, sortByRelevance, sourceKindTone, sourceTypeTone } from "../lib/discovery";

function StatTile({ label, value }) {
  return (
    <div className="rounded-xl border border-navy-100 px-4 py-3 dark:border-navy-800">
      <p className="text-lg font-semibold text-navy-900 dark:text-white">{value}</p>
      <p className="mt-0.5 text-xs muted">{label}</p>
    </div>
  );
}

function formatValue(amount, currency) {
  return `${currency || "INR"} ${formatNumber(amount)}`;
}

const WHY_ROWS = [
  ["skipped_no_work_match", "discover.why.noWorkMatch"],
  ["skipped_no_work_description", "discover.why.noWorkDescription"],
  ["skipped_no_deadline", "discover.why.noDeadline"],
  ["skipped_closed", "discover.why.alreadyClosed"],
  ["skipped_non_tender", "discover.why.indexPages"],
  ["skipped_foreign", "discover.why.foreign"],
  ["fetch_failed", "discover.why.notRetrievable"],
];

// When a run lists nothing, the user gets the real numbers instead of a
// bare "no tenders found".
function WhyNothingListed({ stats }) {
  const { t } = useTranslation();
  const rows = WHY_ROWS.map(([key, label]) => [label, stats?.[key] ?? 0]).filter(
    ([, value]) => value > 0,
  );
  if (!rows.length) return null;
  return (
    <div className="rounded-xl border border-navy-100 bg-white p-4 dark:border-navy-800 dark:bg-navy-900">
      <p className="text-sm font-semibold text-navy-900 dark:text-white">
        {t("discover.why.title")}
      </p>
      <p className="mt-1 text-xs muted">{t("discover.why.body")}</p>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <li
            key={label}
            className="flex items-center justify-between gap-3 rounded-lg bg-navy-50 px-3 py-2 text-xs dark:bg-navy-800"
          >
            <span className="text-navy-700 dark:text-navy-200">{t(label)}</span>
            <span className="font-semibold text-navy-900 dark:text-white">{value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TenderCard({ item, locale, onSave, onDismiss, saving }) {
  const { t } = useTranslation();
  const extracted = item.extracted || {};
  const relevance = item.relevance || {};
  const evidence = extracted.evidence || {};
  const percent = scorePercent(relevance.score);
  const evidenceEntries = Object.entries(evidence);

  const infoRows = [
    { key: "authority", label: t("discover.field.authority"), value: extracted.authority },
    { key: "reference", label: t("discover.field.reference_number"), value: extracted.reference_number },
    {
      key: "deadline",
      label: t("discover.field.deadline"),
      value: extracted.deadline ? formatDate(extracted.deadline, locale) : null,
    },
    {
      key: "value",
      label: t("discover.field.value"),
      value:
        extracted.value_amount === null || extracted.value_amount === undefined
          ? null
          : formatValue(extracted.value_amount, extracted.value_currency),
    },
    { key: "location", label: t("discover.field.location"), value: extracted.location },
  ];

  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={sourceTypeTone(item.source_type)}>{t(`discover.sourceType.${item.source_type}`)}</Badge>
              <Badge tone={fetchStatusTone(item.fetch_status)}>{t(`discover.fetchStatus.${item.fetch_status}`)}</Badge>
              <Badge tone={scoreTone(relevance.score)}>
                {t("discover.relevance", { percent })}
              </Badge>
              {item.extracted_from === "listing_table" ? (
                <Badge tone="blue">{t("discover.fromListing")}</Badge>
              ) : null}
              {item.extracted_from === "search_result" ? (
                <Badge tone="amber">{t("discover.fromSearchResult")}</Badge>
              ) : null}
              {relevance.region_match ? (
                <Badge tone="teal">{t("discover.inYourRegion")}</Badge>
              ) : null}
            </div>
            <h3 className="mt-2 text-base font-semibold leading-6 text-navy-900 dark:text-white">
              {item.title}
            </h3>
            <p className="mt-1 text-xs muted">
              {item.site_name || item.source_url} · {t("discover.retrievedAt", { time: formatDateTime(item.retrieved_at, locale) })}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 rounded-xl border border-navy-200 px-3 py-2 text-xs font-semibold text-navy-700 transition hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {t("discover.openSource")}
            </a>
            <Button size="sm" variant="subtle" onClick={() => onSave(item)} loading={saving}>
              {t("discover.save")}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onDismiss(item)}>
              {t("discover.dismiss")}
            </Button>
          </div>
        </div>

        {item.snippet ? (
          <p className="text-sm leading-6 text-navy-700 dark:text-navy-200">{item.snippet}</p>
        ) : null}

        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {infoRows.map((row) => (
            <div key={row.key} className="rounded-xl border border-navy-100 px-3.5 py-3 dark:border-navy-800">
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-navy-400">{row.label}</dt>
              <dd
                className={cn(
                  "mt-1 text-sm",
                  row.value ? "text-navy-900 dark:text-navy-50" : "italic text-navy-400",
                )}
              >
                {row.value || t("discover.notStated")}
              </dd>
            </div>
          ))}
        </dl>

        {relevance.reasons?.length ? (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-navy-400">
              {t("discover.reasons")}
            </p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {relevance.reasons.map((reason) => (
                <li
                  key={reason}
                  className="rounded-full bg-teal-50 px-2.5 py-1 text-[11px] font-medium text-teal-800 dark:bg-teal-950 dark:text-teal-200"
                >
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <details className="rounded-xl border border-navy-100 px-3.5 py-3 dark:border-navy-800">
          <summary className="cursor-pointer text-xs font-semibold text-navy-700 dark:text-navy-200">
            {t("discover.evidenceTitle")}
          </summary>
          <p className="mt-2 text-xs muted">{t("discover.evidenceNote")}</p>
          {evidenceEntries.length ? (
            <ul className="mt-3 space-y-2">
              {evidenceEntries.map(([field, excerpt]) => (
                <li key={field} className="text-xs leading-5">
                  <span className="font-semibold text-navy-700 dark:text-navy-200">
                    {t(`discover.field.${field}`, field)}
                  </span>
                  <span className="text-navy-500"> — </span>
                  <span className="text-navy-600 dark:text-navy-300">“{excerpt}”</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs italic text-navy-400">{t("discover.noEvidence")}</p>
          )}
          {item.fetch_error ? (
            <p className="mt-3 text-xs text-amber-700 dark:text-amber-300">
              {t("discover.fetchNote", { reason: item.fetch_error })}
            </p>
          ) : null}
        </details>
      </CardContent>
    </Card>
  );
}

export function DiscoverPage() {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const [keywords, setKeywords] = useState(searchParams.get("q") || "");
  const [status, setStatus] = useState(null);
  const [items, setItems] = useState([]);
  const [sources, setSources] = useState([]);
  const [runStats, setRunStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [needsProfile, setNeedsProfile] = useState(false);
  const [savingId, setSavingId] = useState(null);

  const locale = i18n.language === "hi" ? "hi-IN" : "en-IN";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statusResponse, tenderResponse, runResponse, sourceResponse] = await Promise.all([
        api.get("/discovery/status"),
        api.get("/discovery/tenders?limit=50"),
        api.get("/discovery/runs?limit=1"),
        api.get("/discovery/sources?limit=8"),
      ]);
      setStatus(statusResponse);
      setItems(sortByRelevance(tenderResponse.items || []));
      setSources(sourceResponse.items || []);
      const latestRun = runResponse.items?.[0];
      if (latestRun?.stats) setRunStats(latestRun.stats);
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      toast.error(t("errors.generic"));
    } finally {
      setLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (event) => {
    event.preventDefault();
    setRunning(true);
    setNeedsProfile(false);
    try {
      const payload = await api.post("/discovery/run", { keywords: keywords.trim() || null });
      setItems(sortByRelevance(payload.items || []));
      setSources(payload.sources || []);
      setRunStats(payload.run?.stats || null);
      toast.success(t("discover.runSuccess"));
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setNeedsProfile(true);
        toast.error(error.message);
      } else if (error instanceof ApiError && error.status === 503) {
        setStatus((current) => ({ ...(current || {}), configured: false }));
        toast.error(error.message);
      } else {
        toast.error(error instanceof ApiError ? error.message : t("discover.runFailed"));
      }
    } finally {
      setRunning(false);
      setLoading(false);
    }
  };

  const saveTender = async (item) => {
    setSavingId(item.id);
    try {
      await api.post(`/discovery/tenders/${item.id}/save`, {});
      setItems((current) => current.map((row) => (row.id === item.id ? { ...row, status: "saved" } : row)));
      toast.success(t("discover.saved"));
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : t("discover.saveFailed"));
    } finally {
      setSavingId(null);
    }
  };

  const dismissTender = async (item) => {
    try {
      await api.post(`/discovery/tenders/${item.id}/dismiss`, {});
      setItems((current) => current.filter((row) => row.id !== item.id));
      toast.info(t("discover.dismissed"));
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : t("errors.generic"));
    }
  };

  const stats = useMemo(() => runStats, [runStats]);
  const configured = status?.configured !== false;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("discover.title")}
        description={t("discover.subtitle")}
        actions={
          <Button variant="outline" onClick={load} loading={loading} disabled={running}>
            <RefreshCw className="h-4 w-4" />
            {t("common.refresh")}
          </Button>
        }
      />

      <Card>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-3">
            <span
              className={cn(
                "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
                configured
                  ? "bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300"
                  : "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
              )}
            >
              {configured ? <Compass className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-navy-900 dark:text-white">
                {configured ? t("discover.statusConfigured") : t("discover.statusUnconfigured")}
              </p>
              <p className="mt-1 text-sm leading-6 muted">
                {configured ? t("discover.statusBody") : t("discover.unconfiguredBody")}
              </p>
            </div>
          </div>

          {needsProfile ? (
            <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100 sm:flex-row sm:items-center sm:justify-between">
              <span>{t("discover.needProfile")}</span>
              <Link
                to="/app/company"
                className="inline-flex shrink-0 items-center gap-1.5 font-semibold underline underline-offset-2"
              >
                {t("discover.openProfile")}
              </Link>
            </div>
          ) : null}

          <form onSubmit={run} className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <div>
              <Label htmlFor="discover-keywords">{t("discover.keywords")}</Label>
              <Input
                id="discover-keywords"
                value={keywords}
                onChange={(event) => setKeywords(event.target.value)}
                placeholder={t("discover.keywordsPlaceholder")}
                disabled={!configured || running}
              />
            </div>
            <Button type="submit" loading={running} disabled={!configured || running}>
              {!running ? <Search className="h-4 w-4" /> : null}
              {running ? t("discover.running") : t("discover.run")}
            </Button>
          </form>

          <p className="flex items-start gap-2 text-xs leading-5 muted">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {t("discover.runNote")}
          </p>
        </CardContent>
      </Card>

      {stats ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("discover.coverage")}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 pt-2 sm:grid-cols-3 lg:grid-cols-4">
            <StatTile label={t("discover.stats.queries")} value={stats.queries ?? 0} />
            <StatTile label={t("discover.stats.searchHits")} value={stats.search_hits ?? 0} />
            <StatTile label={t("discover.stats.unique")} value={stats.unique_candidates ?? 0} />
            <StatTile label={t("discover.stats.fetched")} value={stats.fetched ?? 0} />
            <StatTile label={t("discover.stats.fetchFailed")} value={stats.fetch_failed ?? 0} />
            <StatTile label={t("discover.stats.nonTender")} value={stats.skipped_non_tender ?? 0} />
            <StatTile label={t("discover.stats.rowsFound")} value={stats.rows_found ?? 0} />
            <StatTile
              label={t("discover.stats.fromSearchResults")}
              value={stats.notices_from_search_results ?? 0}
            />
            <StatTile
              label={t("discover.stats.noWorkMatch")}
              value={stats.skipped_no_work_match ?? 0}
            />
            <StatTile
              label={t("discover.stats.noWorkDescription")}
              value={stats.skipped_no_work_description ?? 0}
            />
            <StatTile
              label={t("discover.stats.noDeadline")}
              value={stats.skipped_no_deadline ?? 0}
            />
            <StatTile label={t("discover.stats.closed")} value={stats.skipped_closed ?? 0} />
            <StatTile label={t("discover.stats.foreign")} value={stats.skipped_foreign ?? 0} />
            <StatTile label={t("discover.stats.fromListings")} value={stats.tenders_from_listings ?? 0} />
            <StatTile label={t("discover.stats.listed")} value={stats.listed ?? 0} />
          </CardContent>
        </Card>
      ) : null}

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-navy-900 dark:text-white">
              {t("discover.results")}
            </h2>
            <p className="text-sm muted">
              {t("discover.resultsHint", { count: items.length })}
            </p>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center gap-3 rounded-xl border border-navy-100 px-5 py-8 dark:border-navy-800">
            <Spinner />
            <span className="text-sm muted">{t("discover.loading")}</span>
          </div>
        ) : items.length ? (
          <div className="space-y-4">
            {items.map((item) => (
              <TenderCard
                key={item.id}
                item={item}
                locale={locale}
                onSave={saveTender}
                onDismiss={dismissTender}
                saving={savingId === item.id}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            <EmptyState
              icon={runStats ? FileSearch : Sparkles}
              title={t("discover.emptyTitle")}
              description={runStats ? t("discover.emptyBody") : t("discover.emptyStored")}
            />
            {runStats ? <WhyNothingListed stats={runStats} /> : null}
          </div>
        )}
      </section>

      {sources.length ? (
        <section className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-navy-900 dark:text-white">
              {t("discover.sources")}
            </h2>
            <p className="text-sm muted">{t("discover.sourcesHint")}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {sources.map((source) => (
              <div
                key={source.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-navy-100 bg-white p-4 dark:border-navy-800 dark:bg-navy-900"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={sourceKindTone(source.source_kind || source.source_type)}>
                      {t(
                        `discover.sourceKind.${source.source_kind || source.source_type}`,
                        { defaultValue: t(`discover.sourceType.${source.source_type}`) },
                      )}
                    </Badge>
                    <Badge tone="neutral">{t("discover.indexPage")}</Badge>
                  </div>
                  <p className="mt-1.5 line-clamp-2 text-sm font-semibold text-navy-900 dark:text-white">
                    {source.title}
                  </p>
                  <p className="mt-0.5 text-xs muted">{source.site_name || source.source_url}</p>
                </div>
                <a
                  href={source.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-navy-200 px-3 py-2 text-xs font-semibold text-navy-700 transition hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  {t("discover.openSource")}
                </a>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
