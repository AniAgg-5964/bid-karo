import { cn } from "../../lib/utils";

export function Card({ className, children, ...props }) {
  return (
    <section className={cn("surface", className)} {...props}>
      {children}
    </section>
  );
}

export function CardHeader({ className, children, action }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 px-5 pt-5", className)}>
      <div className="min-w-0">{children}</div>
      {action}
    </div>
  );
}

export function CardTitle({ className, children, as: Tag = "h2" }) {
  return (
    <Tag className={cn("text-[15px] font-semibold tracking-tight text-navy-900 dark:text-white", className)}>
      {children}
    </Tag>
  );
}

export function CardDescription({ className, children }) {
  return <p className={cn("mt-1 text-[13px] leading-5 muted", className)}>{children}</p>;
}

export function CardContent({ className, children }) {
  return <div className={cn("px-5 py-4", className)}>{children}</div>;
}
