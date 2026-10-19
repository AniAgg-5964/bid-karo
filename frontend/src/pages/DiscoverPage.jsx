import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen, Compass, Search, UploadCloud } from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Input, Label, Select } from "../components/ui/Field";
import { useToast } from "../contexts/ToastContext";

export function DiscoverPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const [searchParams] = useSearchParams();
  const [keywords, setKeywords] = useState(searchParams.get("q") || "");
  const [source, setSource] = useState("");

  const submit = (event) => {
    event.preventDefault();
    toast.info(t("discover.phaseTitle"));
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("discover.title")} description={t("discover.subtitle")} />

      <Card>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4 lg:grid-cols-[240px_1fr_auto] lg:items-end">
            <div>
              <Label htmlFor="source">{t("discover.sourceLabel")}</Label>
              <Select id="source" value={source} onChange={(event) => setSource(event.target.value)}>
                <option value="">{t("discover.sourcePlaceholder")}</option>
                <option value="cppp">CPPP / eProcurement</option>
                <option value="gem">GeM</option>
                <option value="state">State eProcurement portal</option>
                <option value="other">Other official source</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="keywords">{t("discover.keywords")}</Label>
              <Input
                id="keywords"
                value={keywords}
                onChange={(event) => setKeywords(event.target.value)}
                placeholder={t("discover.keywordsPlaceholder")}
              />
            </div>
            <Button type="submit" className="lg:mb-0">
              <Search className="h-4 w-4" />
              {t("discover.search")}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card className="overflow-hidden">
          <div className="border-b border-teal-100 bg-teal-50/60 px-6 py-8 dark:border-teal-900 dark:bg-teal-950/30">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-teal-700 shadow-sm dark:bg-navy-900 dark:text-teal-300">
              <Compass className="h-6 w-6" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-navy-900 dark:text-white">{t("discover.phaseTitle")}</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-navy-600 dark:text-navy-300">
              {t("discover.phaseBody")}
            </p>
            <p className="mt-4 max-w-xl text-xs leading-5 muted">{t("discover.configNote")}</p>
          </div>
          <CardContent className="flex flex-wrap gap-2">
            <Link
              to="/app/tenders"
              className="inline-flex items-center gap-2 rounded-xl border border-navy-200 px-4 py-2.5 text-sm font-semibold text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
            >
              {t("discover.goTenders")}
            </Link>
            <Link
              to="/app/documents"
              className="inline-flex items-center gap-2 rounded-xl border border-navy-200 px-4 py-2.5 text-sm font-semibold text-navy-700 hover:bg-navy-50 dark:border-navy-700 dark:text-navy-200 dark:hover:bg-navy-800"
            >
              <UploadCloud className="h-4 w-4" />
              {t("discover.openLibrary")}
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("discover.manualTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="pt-2">
            <p className="text-sm leading-6 muted">{t("discover.manualBody")}</p>
            <div className="mt-4 rounded-xl border border-dashed border-navy-200 p-4 dark:border-navy-700">
              <BookOpen className="h-5 w-5 text-navy-400" />
              <p className="mt-2 text-xs leading-5 muted">{t("common.phaseNote")}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
