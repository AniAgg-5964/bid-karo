import { useTranslation } from "react-i18next";

import { cn } from "../../lib/utils";

/*
  The workbench is organised by what the user is trying to do, not by the
  order the screens were written in. The screens themselves are unchanged:
  every tab here already exists in the product.
*/
const GROUPS = [
  {
    key: "understand",
    tabs: [
      { key: "overview", label: "overview" },
      { key: "documents", label: "documents" },
      { key: "requirements", label: "requirements" },
    ],
  },
  {
    key: "evaluate",
    tabs: [
      { key: "score", label: "score" },
      { key: "eligibility", label: "eligibility" },
      { key: "legal", label: "legal" },
      { key: "recommend", label: "recommend" },
    ],
  },
  {
    key: "execute",
    tabs: [
      { key: "tasks", label: "tasks" },
      { key: "compliance", label: "compliance" },
      { key: "obligations", label: "obligations" },
    ],
  },
  {
    key: "monitor",
    tabs: [
      { key: "changes", label: "changes" },
    ],
  },
];

export function WorkbenchTabs({ active, onChange, counts = {} }) {
  const { t } = useTranslation();

  return (
    <div className="surface overflow-hidden">
      <div
        role="tablist"
        aria-label={t("tenders.detail.sections")}
        className="flex flex-col gap-0 sm:flex-row"
      >
        {GROUPS.map((group, groupIndex) => (
          <div
            key={group.key}
            className={cn(
              "flex flex-wrap items-center gap-1 px-3 py-2.5",
              groupIndex > 0 &&
                "border-t border-navy-100 sm:border-l sm:border-t-0 dark:border-navy-800",
            )}
          >
            <p className="mr-1 hidden shrink-0 text-[10px] font-bold uppercase tracking-[0.14em] text-navy-500 lg:block dark:text-navy-300">
              {t(`tenders.workbench.${group.key}`)}
            </p>
            <p className="mr-1 shrink-0 text-[10px] font-bold uppercase tracking-[0.14em] text-navy-500 lg:hidden dark:text-navy-300">
              {t(`tenders.workbench.${group.key}`)}
            </p>
            {group.tabs.map((tab) => {
              const selected = active === tab.key;
              const count = counts[tab.key];
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  onClick={() => onChange(tab.key)}
                  className={cn(
                    "relative shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                    selected
                      ? "bg-teal-50 text-teal-800 dark:bg-teal-950/60 dark:text-teal-200"
                      : "text-navy-500 hover:bg-navy-50 hover:text-navy-900 dark:text-navy-300 dark:hover:bg-navy-800 dark:hover:text-white",
                  )}
                >
                  {t(`tenders.detail.${tab.label}`)}
                  {count ? (
                    <span className="ml-1.5 tabular rounded-full bg-navy-100 px-1.5 py-0.5 text-[10px] font-bold text-navy-600 dark:bg-navy-800 dark:text-navy-200">
                      {count}
                    </span>
                  ) : null}
                  {selected ? (
                    <span
                      className="absolute inset-x-2 -bottom-[1px] h-0.5 rounded-full bg-teal-600"
                      aria-hidden="true"
                    />
                  ) : null}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
