import { cn } from "../../lib/utils";

export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-navy-200 px-6 py-12 text-center dark:border-navy-700",
        className,
      )}
    >
      {Icon ? (
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
