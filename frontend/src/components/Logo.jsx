import { cn } from "../lib/utils";

export function Logo({ compact = false, light = false, className }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div
        className={cn(
          "relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
          light ? "bg-white" : "bg-navy-900 dark:bg-teal-600",
        )}
      >
        <span className={cn("text-[15px] font-bold leading-none", light ? "text-navy-900" : "text-white")}>
          B
        </span>
        <span
          className={cn(
            "absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full border bg-teal-400",
            light ? "border-white" : "border-white dark:border-navy-900",
          )}
        />
      </div>
      {!compact ? (
        <div className="leading-[1.05]">
          <p
            className={cn(
              "text-[15px] font-bold tracking-tight",
              light ? "text-white" : "text-navy-900 dark:text-white",
            )}
          >
            BidKaro
          </p>
          <p
            className={cn(
              "mt-0.5 text-[7px] font-semibold uppercase tracking-[0.2em]",
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
