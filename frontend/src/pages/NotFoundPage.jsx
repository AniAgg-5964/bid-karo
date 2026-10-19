import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Compass } from "lucide-react";

import { Logo } from "../components/Logo";
import { Button } from "../components/ui/Button";
import { LanguageSwitch } from "../components/LanguageSwitch";
import { ThemeToggle } from "../components/ThemeToggle";

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-mist px-4 dark:bg-navy-950">
      <div className="absolute right-4 top-4 flex items-center gap-2">
        <LanguageSwitch compact />
        <ThemeToggle />
      </div>
      <Logo className="mb-8" />
      <div className="surface flex max-w-md flex-col items-center px-8 py-10 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
          <Compass className="h-6 w-6" />
        </div>
        <p className="mt-4 text-5xl font-semibold tracking-tight text-navy-900 dark:text-white">404</p>
        <p className="mt-2 text-sm muted">{t("errors.notFound")}</p>
        <Link to="/" className="mt-6">
          <Button>{t("common.goToDashboard")}</Button>
        </Link>
      </div>
    </div>
  );
}
