import { useEffect, useRef, useState } from "react";
import { MoreVertical } from "lucide-react";

import { cn } from "../../lib/utils";

export function KebabMenu({ items = [], label = "More actions", align = "right", buttonClassName }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (!ref.current?.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const visible = items.filter(Boolean);
  if (!visible.length) return null;

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-lg text-navy-400 transition hover:bg-navy-100 hover:text-navy-700 dark:hover:bg-navy-800 dark:hover:text-white",
          buttonClassName,
        )}
      >
        <MoreVertical className="h-4 w-4" />
      </button>
      {open ? (
        <div
          role="menu"
          className={cn(
            "absolute z-30 mt-1 w-52 animate-fade-in overflow-hidden rounded-lg border border-navy-100 bg-white py-1 shadow-pop dark:border-navy-700 dark:bg-navy-900",
            align === "right" ? "right-0" : "left-0",
            "top-full",
          )}
        >
          {visible.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                setOpen(false);
                item.onClick?.();
              }}
              className={cn(
                "flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
                item.danger
                  ? "text-red-600 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-950/40"
                  : "text-navy-700 hover:bg-navy-50 dark:text-navy-200 dark:hover:bg-navy-800",
              )}
            >
              {item.icon ? <item.icon className="h-3.5 w-3.5 shrink-0" /> : null}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
