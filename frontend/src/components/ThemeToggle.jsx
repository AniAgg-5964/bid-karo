import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useTheme } from "../contexts/ThemeContext";
import { cn } from "../lib/utils";

export function ThemeToggle({ className }) {
  const { isDark, toggleTheme } = useTheme();
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-navy-200 bg-white text-navy-600 transition hover:bg-navy-50 hover:text-navy-900 dark:border-navy-700 dark:bg-navy-900 dark:text-navy-300 dark:hover:bg-navy-800 dark:hover:text-white",
        className,
      )}
      aria-label={isDark ? t("common.light") : t("common.dark")}
      title={isDark ? t("common.light") : t("common.dark")}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
