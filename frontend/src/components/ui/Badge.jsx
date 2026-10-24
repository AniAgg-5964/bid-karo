import { cn } from "../../lib/utils";

const TONES = {
  neutral: "bg-navy-100 text-navy-600 dark:bg-navy-800 dark:text-navy-200",
  teal: "bg-teal-50 text-teal-700 dark:bg-teal-900/40 dark:text-teal-200",
  green: "bg-teal-50 text-teal-700 dark:bg-teal-900/40 dark:text-teal-200",
  emerald: "bg-teal-50 text-teal-700 dark:bg-teal-900/40 dark:text-teal-200",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200",
  red: "bg-red-50 text-red-600 dark:bg-red-900/40 dark:text-red-200",
  blue: "bg-sky-50 text-sky-700 dark:bg-sky-900/40 dark:text-sky-200",
};

export function Badge({ tone = "neutral", className, children }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-medium leading-5",
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
  extracted: "green",
  no_text_layer: "amber",
  failed: "red",
  download_blocked: "red",
  rejected: "red",
  yes: "amber",
  no: "neutral",
  unknown: "neutral",
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
