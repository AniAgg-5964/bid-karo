import { Loader2 } from "lucide-react";

import { cn } from "../../lib/utils";

export function Spinner({ className }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-teal-700", className)} aria-hidden="true" />;
}

export function FullPageLoader({ label = "Loading…" }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-mist dark:bg-navy-950">
      <Spinner className="h-7 w-7" />
      <p className="text-sm muted">{label}</p>
    </div>
  );
}

export function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-lg bg-navy-100 dark:bg-navy-800", className)} />;
}
