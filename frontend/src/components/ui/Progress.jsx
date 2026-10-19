import { cn } from "../../lib/utils";

export function Progress({ value = 0, className, tone = "teal", label }) {
  const clamped = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className={className}>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-navy-100 dark:bg-navy-800"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        aria-label={label}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            tone === "teal" ? "bg-teal-600" : tone === "amber" ? "bg-amber-500" : "bg-navy-700",
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
