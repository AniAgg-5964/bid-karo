import { forwardRef } from "react";
import { Loader2 } from "lucide-react";

import { cn } from "../../lib/utils";

const VARIANTS = {
  primary:
    "bg-teal-600 text-white shadow-sm hover:bg-teal-700 focus-visible:ring-teal-500 disabled:bg-teal-600/50",
  secondary:
    "bg-navy-900 text-white hover:bg-navy-800 focus-visible:ring-navy-700 disabled:bg-navy-900/50",
  outline:
    "border border-navy-200 bg-white text-navy-700 hover:border-navy-300 hover:bg-navy-50 dark:border-navy-700 dark:bg-navy-900 dark:text-navy-100 dark:hover:bg-navy-800",
  ghost:
    "text-navy-600 hover:bg-navy-100 hover:text-navy-900 dark:text-navy-300 dark:hover:bg-navy-800 dark:hover:text-white",
  danger:
    "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-500 disabled:bg-red-600/50",
  subtle:
    "bg-teal-50 text-teal-700 hover:bg-teal-100 dark:bg-teal-900/40 dark:text-teal-200 dark:hover:bg-teal-900",
};

const SIZES = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-xs",
  md: "h-9 gap-2 rounded-lg px-4 text-[13px]",
  lg: "h-10 gap-2 rounded-lg px-5 text-sm",
  icon: "h-8 w-8 rounded-lg",
};

export const Button = forwardRef(function Button(
  { className, variant = "primary", size = "md", type = "button", loading = false, disabled, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 dark:focus-visible:ring-offset-navy-950",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
      {children}
    </button>
  );
});
