import { cn } from "../../lib/utils";

export function PageHeader({ eyebrow, title, description, actions, className }) {
  return (
    <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between", className)}>
      <div className="min-w-0">
        {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
        <h1 className="text-2xl font-semibold tracking-tight text-navy-900 dark:text-white sm:text-[28px]">
          {title}
        </h1>
        {description ? <p className="mt-1.5 max-w-2xl text-sm muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
