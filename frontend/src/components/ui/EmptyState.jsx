import { cn } from "../../lib/utils";

/*
  The empty state.

  It can carry an original illustration, drawn as engineering linework, or
  the icon on its own. The illustration is decorative: it repeats what the
  words already say, so it is hidden from assistive technology.
*/
export function EmptyState({ icon: Icon, title, description, action, art, className, compact = false }) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-navy-200 px-6 text-center dark:border-navy-700",
        compact ? "py-8" : "py-12",
        className,
      )}
    >
      {art ? (
        <img
          src={art}
          alt=""
          aria-hidden="true"
          className={cn("mb-4 w-44 select-none opacity-95", compact ? "h-24 object-contain" : "h-32 object-contain")}
        />
      ) : Icon ? (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300">
          <Icon className="h-6 w-6" aria-hidden="true" />
        </div>
      ) : null}
      <h3 className="text-sm font-semibold text-navy-900 dark:text-white">{title}</h3>
      {description ? <p className="mt-1.5 max-w-md text-sm muted">{description}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
