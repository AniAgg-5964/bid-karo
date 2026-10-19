import { cn } from "../lib/utils";

export function Logo({ compact = false, light = false, className }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div
        className={cn(
          "relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-sm",
          light ? "bg-white" : "bg-navy-900 dark:bg-teal-600",
        )}
      >
        <span className={cn("text-lg font-bold leading-none", light ? "text-navy-900" : "text-white")}>
          B
        </span>
        <span
          className={cn(
            "absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full border bg-teal-400",
            light ? "border-white" : "border-white dark:border-navy-900",
          )}
        />
      </div>
      {!compact ? (
        <div className="leading-tight">
          <p
            className={cn(
              "text-lg font-bold tracking-tight",
              light ? "text-white" : "text-navy-900 dark:text-white",
            )}
          >
            Bid<span className={light ? "text-teal-300" : "text-teal-700 dark:text-teal-300"}>Karo</span>
          </p>
          <p
            className={cn(
              "text-[10px] font-medium uppercase tracking-[0.16em]",
              light ? "text-navy-200" : "text-navy-400",
            )}
          >
            Tender intelligence
          </p>
        </div>
      ) : null}
    </div>
  );
}
