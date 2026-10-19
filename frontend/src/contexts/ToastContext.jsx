import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

import { cn } from "../lib/utils";

const ToastContext = createContext(null);
let nextId = 1;

const TONES = {
  success: {
    icon: CheckCircle2,
    className: "border-teal-200 bg-teal-50 text-teal-900 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-100",
  },
  error: {
    icon: AlertTriangle,
    className: "border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-100",
  },
  info: {
    icon: Info,
    className: "border-navy-200 bg-white text-navy-900 dark:border-navy-700 dark:bg-navy-900 dark:text-navy-50",
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const push = useCallback(
    (message, tone = "info") => {
      const id = nextId++;
      setToasts((current) => [...current, { id, message, tone }]);
      window.setTimeout(() => dismiss(id), 4200);
    },
    [dismiss],
  );

  const toast = useMemo(
    () => ({
      show: push,
      success: (message) => push(message, "success"),
      error: (message) => push(message, "error"),
      info: (message) => push(message, "info"),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-4 bottom-4 z-[100] flex flex-col items-end gap-2 sm:left-auto sm:right-6 sm:bottom-6"
        role="status"
        aria-live="polite"
      >
        {toasts.map((item) => {
          const tone = TONES[item.tone] || TONES.info;
          const Icon = tone.icon;
          return (
            <div
              key={item.id}
              className={cn(
                "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-pop animate-slide-up",
                tone.className,
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p className="flex-1 leading-5">{item.message}</p>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                className="rounded-md p-0.5 opacity-70 transition hover:opacity-100"
                aria-label="Dismiss notification"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider.");
  return context;
}
