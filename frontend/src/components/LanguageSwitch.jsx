import { useTranslation } from "react-i18next";

import { changeLanguage, SUPPORTED_LANGUAGES } from "../i18n";
import { cn } from "../lib/utils";

export function LanguageSwitch({ className, compact = false }) {
  const { i18n } = useTranslation();
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-lg border border-navy-200 bg-white p-0.5 dark:border-navy-700 dark:bg-navy-900",
        className,
      )}
      role="group"
      aria-label="Language"
    >
      {SUPPORTED_LANGUAGES.map((language) => {
        const active = i18n.language === language.code;
        return (
          <button
            key={language.code}
            type="button"
            onClick={() => changeLanguage(language.code)}
            aria-pressed={active}
            title={language.label}
            className={cn(
              "rounded-md px-2 py-1 text-[11px] font-bold transition",
              active
                ? "bg-navy-900 text-white dark:bg-teal-600"
                : "text-navy-500 hover:bg-navy-50 hover:text-navy-800 dark:hover:bg-navy-800 dark:hover:text-white",
            )}
          >
            {compact ? language.short : language.label}
          </button>
        );
      })}
    </div>
  );
}
