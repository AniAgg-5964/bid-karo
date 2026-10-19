import { useRef, useState } from "react";
import { X } from "lucide-react";

import { cn } from "../lib/utils";

export function TagInput({ value = [], onChange, placeholder, ariaLabel, className }) {
  const [draft, setDraft] = useState("");
  const valueRef = useRef(value);
  valueRef.current = value;

  const add = () => {
    const candidates = draft
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (!candidates.length) return;
    const next = [...(valueRef.current || [])];
    candidates.forEach((candidate) => {
      if (!next.some((item) => item.toLowerCase() === candidate.toLowerCase())) {
        next.push(candidate);
      }
    });
    onChange(next);
    setDraft("");
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      add();
    } else if (event.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div
      className={cn(
        "flex min-h-11 w-full flex-wrap items-center gap-1.5 rounded-xl border border-navy-200 bg-white px-2.5 py-2 text-sm transition focus-within:border-teal-600 focus-within:ring-2 focus-within:ring-teal-500/20 dark:border-navy-700 dark:bg-navy-900",
        className,
      )}
    >
      {value.map((item) => (
        <span
          key={item}
          className="inline-flex items-center gap-1 rounded-md bg-teal-50 px-2 py-1 text-xs font-medium text-teal-800 dark:bg-teal-950 dark:text-teal-200"
        >
          {item}
          <button
            type="button"
            onClick={() => onChange(value.filter((entry) => entry !== item))}
            className="rounded-sm p-0.5 hover:bg-teal-100 dark:hover:bg-teal-900"
            aria-label={`Remove ${item}`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={add}
        placeholder={value.length ? "" : placeholder}
        aria-label={ariaLabel || placeholder}
        className="min-w-[110px] flex-1 bg-transparent px-1 py-1 text-sm text-navy-900 outline-none placeholder:text-navy-400 dark:text-navy-50"
      />
    </div>
  );
}
