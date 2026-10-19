import { cn } from "../../lib/utils";

const TONES = {
  neutral: "bg-navy-100 text-navy-700 dark:bg-navy-800 dark:text-navy-200",
  teal: "bg-teal-50 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  green: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200",
  amber: "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  red: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-200",
  blue: "bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-200",
};

export function Badge({ tone = "neutral", className, children }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none",
        TONES[tone] || TONES.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}

const STATUS_TONES = {
  verified: "green",
  complete: "green",
  self_declared: "neutral",
  partial: "amber",
  needs_verification: "amber",
  in_progress: "blue",
  pending: "amber",
  needs_review: "amber",
  unverified: "neutral",
  missing: "red",
  incomplete: "amber",
  expired: "red",
  conflict: "red",
  not_applicable: "neutral",
  saved: "teal",
  preparing: "blue",
  submitted: "green",
  won: "green",
  lost: "red",
  archived: "neutral",
};

export function StatusBadge({ status, label }) {
  if (!status) return null;
  return (
    <Badge tone={STATUS_TONES[status] || "neutral"}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {label || status.replaceAll("_", " ")}
    </Badge>
  );
}
