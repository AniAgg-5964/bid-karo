import { forwardRef, useId } from "react";

import { cn } from "../../lib/utils";

export const Label = forwardRef(function Label({ className, children, ...props }, ref) {
  return (
    <label
      ref={ref}
      className={cn(
        "mb-1.5 block text-sm font-medium text-navy-800 dark:text-navy-100",
        className,
      )}
      {...props}
    >
      {children}
    </label>
  );
});

const fieldStyles =
  "w-full rounded-xl border bg-white px-3.5 py-2.5 text-sm text-navy-900 placeholder:text-navy-400 transition focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20 disabled:cursor-not-allowed disabled:bg-navy-50 dark:bg-navy-900 dark:text-navy-50 dark:placeholder:text-navy-500";

export const Input = forwardRef(function Input({ className, invalid, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        fieldStyles,
        invalid
          ? "border-red-400 focus:border-red-500 focus:ring-red-500/20"
          : "border-navy-200 dark:border-navy-700",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
});

export const Textarea = forwardRef(function Textarea({ className, invalid, rows = 4, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        fieldStyles,
        "resize-y leading-6",
        invalid
          ? "border-red-400 focus:border-red-500 focus:ring-red-500/20"
          : "border-navy-200 dark:border-navy-700",
        className,
      )}
      aria-invalid={invalid || undefined}
      {...props}
    />
  );
});

export const Select = forwardRef(function Select({ className, children, invalid, ...props }, ref) {
  return (
    <select
      ref={ref}
      className={cn(
        fieldStyles,
        "cursor-pointer appearance-none bg-[length:16px_16px] bg-[right_12px_center] bg-no-repeat pr-10",
        invalid
          ? "border-red-400 focus:border-red-500 focus:ring-red-500/20"
          : "border-navy-200 dark:border-navy-700",
        className,
      )}
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%236e8dbb' stroke-width='2'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
      }}
      aria-invalid={invalid || undefined}
      {...props}
    >
      {children}
    </select>
  );
});

export function FieldError({ children }) {
  if (!children) return null;
  return (
    <p className="mt-1.5 text-xs font-medium text-red-600 dark:text-red-400" role="alert">
      {children}
    </p>
  );
}

export function Field({ label, htmlFor, hint, error, required, children, className }) {
  const generatedId = useId();
  const id = htmlFor || generatedId;
  return (
    <div className={className}>
      {label ? (
        <Label htmlFor={id}>
          {label}
          {required ? <span className="ml-1 text-red-500">*</span> : null}
        </Label>
      ) : null}
      {children({ id })}
      {hint && !error ? <p className="mt-1.5 text-xs muted">{hint}</p> : null}
      <FieldError>{error}</FieldError>
    </div>
  );
}
