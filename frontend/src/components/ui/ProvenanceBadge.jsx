import {
  CircleCheck,
  CircleHelp,
  CircleX,
  Flag,
  Link2,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Sparkles,
  Unplug,
  UserCheck,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "../../lib/utils";
import { TRUST_ICONS, TRUST_TONES } from "../../lib/trust";

const ICONS = {
  sparkles: Sparkles,
  link: Link2,
  "shield-check": ShieldCheck,
  "user-check": UserCheck,
  flag: Flag,
  "shield-question": ShieldQuestion,
  x: X,
  unplug: Unplug,
  "shield-alert": ShieldAlert,
  "circle-check": CircleCheck,
  "circle-x": CircleX,
  "circle-help": CircleHelp,
};

/*
  The status colours are deliberately restrained, and every state carries a
  word and an icon as well. Colour is never the only signal.
*/
const TONES = {
  neutral:
    "border-navy-200 bg-navy-50 text-navy-700 dark:border-navy-700 dark:bg-navy-800 dark:text-navy-200",
  info: "border-cobalt-200 bg-cobalt-50 text-cobalt-800 dark:border-cobalt-800 dark:bg-cobalt-950/50 dark:text-cobalt-200",
  verified:
    "border-emerald-200 bg-emerald-100/70 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200",
  review:
    "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200",
  blocked:
    "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200",
};

/**
 * A badge that says where a statement came from and how far it has been
 * checked.
 */
export function ProvenanceBadge({ state, tone, icon, label, detail, className, size = "md" }) {
  const { t } = useTranslation();
  const Icon = ICONS[icon] || ShieldQuestion;
  const resolvedTone = TONES[tone] || TONES.neutral;

  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border font-semibold",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
        resolvedTone,
        className,
      )}
    >
      <Icon className={size === "sm" ? "h-3 w-3 shrink-0" : "h-3.5 w-3.5 shrink-0"} aria-hidden="true" />
      <span className="truncate">{label || t(`trust.states.${state}`)}</span>
      {detail ? (
        <span className="hidden truncate font-normal opacity-80 sm:inline" title={detail}>
          · {detail}
        </span>
      ) : null}
    </span>
  );
}

export { TRUST_TONES, TRUST_ICONS };
