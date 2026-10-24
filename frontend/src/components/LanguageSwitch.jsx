import { useTranslation } from "react-i18next";
import { ChevronDown } from "lucide-react";

import { changeLanguage, SUPPORTED_LANGUAGES } from "../i18n";
import { cn } from "../lib/utils";

export function LanguageSwitch({ className }) {
  const { i18n } = useTranslation();
  return (
    <div
      className={cn("inline-flex items-center gap-3", className)}
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
              "inline-flex items-center gap-0.5 rounded px-0.5 text-[12px] transition",
              active
                ? "font-bold text-navy-900 dark:text-white"
                : "font-medium text-navy-400 hover:text-navy-700 dark:hover:text-navy-200",
            )}
          >
            {language.code === "hi" ? "हि" : language.short}
            {active ? <ChevronDown className="h-3 w-3 opacity-60" /> : null}
          </button>
        );
      })}
    </div>
  );
}
