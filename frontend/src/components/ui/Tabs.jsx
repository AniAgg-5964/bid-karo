import { cn } from "../../lib/utils";

export function Tabs({ items, value, onChange, className, ariaLabel }) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn("flex gap-7 overflow-x-auto border-b border-navy-100 dark:border-navy-800", className)}
    >
      {items.map((item) => {
        const active = item.key === value;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange?.(item.key)}
            className={cn("tab", active && "tab-active")}
          >
            {item.icon ? <item.icon className="h-4 w-4" aria-hidden="true" /> : null}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

export function PillTabs({ items, value, onChange, className, ariaLabel }) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn("flex flex-wrap items-center gap-1", className)}
    >
      {items.map((item) => {
        const active = item.key === value;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange?.(item.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition",
              active
                ? "bg-teal-50 text-teal-700 dark:bg-teal-900/40 dark:text-teal-200"
                : "text-navy-500 hover:bg-navy-50 hover:text-navy-800 dark:text-navy-300 dark:hover:bg-navy-800 dark:hover:text-white",
            )}
          >
            {item.icon ? (
              <item.icon
                className={cn(
                  "h-3.5 w-3.5",
                  active ? "" : item.tone === "amber" ? "text-amber-500" : item.tone === "green" ? "text-teal-600" : "text-navy-400",
                )}
                aria-hidden="true"
              />
            ) : null}
            <span>{item.label}</span>
            {item.count !== undefined ? (
              <span
                className={cn(
                  "rounded px-1 text-[11px] tabular-nums",
                  active ? "bg-teal-100/70 text-teal-800 dark:bg-teal-900 dark:text-teal-100" : "text-navy-400",
                )}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
