import { cn } from "../lib/utils";
import markUrl from "../assets/logo-mark.svg";

/*
  The mark is a tender sheet drawn as engineering linework, in blueprint
  cobalt, with the jade check that says the evidence was verified. It is the
  same drawing whether it sits on a light surface or on the ink navigation.
*/
export function Logo({ compact = false, light = false, className }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
          light ? "bg-white/95" : "bg-white",
        )}
      >
        <img src={markUrl} alt="" aria-hidden="true" className="h-7 w-7" />
      </span>
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
              light ? "text-navy-400" : "text-navy-400",
            )}
          >
            Tender intelligence
          </p>
        </div>
      ) : null}
    </div>
  );
}
