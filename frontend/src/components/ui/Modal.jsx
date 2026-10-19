import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import { cn } from "../../lib/utils";

const SIZES = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
};

export function Modal({ open, onClose, title, description, children, footer, size = "md" }) {
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const timer = window.setTimeout(() => closeRef.current?.focus(), 30);
    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      window.clearTimeout(timer);
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-end justify-center p-0 sm:items-center sm:p-6">
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-navy-950/45 backdrop-blur-[2px]"
        aria-label="Close dialog"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className={cn(
          "relative max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-navy-100 bg-white shadow-pop animate-slide-up dark:border-navy-800 dark:bg-navy-900 sm:rounded-2xl",
          SIZES[size] || SIZES.md,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-navy-100 px-5 py-4 dark:border-navy-800 sm:px-6">
          <div>
            <h2 id="modal-title" className="text-lg font-semibold tracking-tight text-navy-900 dark:text-white">
              {title}
            </h2>
            {description ? <p className="mt-1 text-sm muted">{description}</p> : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-navy-500 transition hover:bg-navy-100 hover:text-navy-800 dark:hover:bg-navy-800 dark:hover:text-white"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-5 sm:px-6">{children}</div>
        {footer ? (
          <div className="flex flex-col-reverse gap-2 border-t border-navy-100 px-5 py-4 dark:border-navy-800 sm:flex-row sm:justify-end sm:px-6">
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
