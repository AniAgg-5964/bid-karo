import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  CircleCheck,
  CircleHelp,
  CircleX,
  FileText,
  Link2,
  UserCheck,
} from "lucide-react";

import { cn } from "../../lib/utils";
import { requirementTrust } from "../../lib/trust";

/*
  The evidence thread.

  The same four steps appear wherever a requirement is shown: the tender
  wording, the source it came from, the company evidence, and what it means
  for eligibility. A step that has no data says so. The thread is a record of
  real relationships, not a decoration.
*/

const STEP_STATES = {
  done: "text-emerald-700 dark:text-emerald-300 border-emerald-300 bg-emerald-50/70 dark:border-emerald-800 dark:bg-emerald-950/40",
  pending: "text-amber-700 dark:text-amber-300 border-amber-300 bg-amber-50/70 dark:border-amber-800 dark:bg-amber-950/40",
  empty: "text-navy-400 dark:text-navy-500 border-navy-200 bg-white dark:border-navy-700 dark:bg-navy-900",
};

export function EvidenceThread({ requirement, onOpenSource, className }) {
  const { t } = useTranslation();
  if (!requirement) return null;

  const trust = requirementTrust(requirement);
  const evidenceStatus = requirement.evidence_status || "none";

  const sourceState = requirement.verification_status === "verified" ? "done" : "pending";
  const evidenceState =
    evidenceStatus === "confirmed" ? "done" : evidenceStatus === "contradicted" ? "pending" : "empty";

  return (
    <ol
      className={cn(
        "flex flex-wrap items-stretch gap-x-1 gap-y-2 text-[11px]",
        className,
      )}
      aria-label={t("thread.label")}
    >
      <ThreadStep
        state={sourceState}
        icon={FileText}
        label={t("thread.source")}
        value={
          requirement.document_title
            ? `${requirement.document_title}${
                requirement.page_index ? ` · ${t("tenders.requirements.page", { page: requirement.page_index })}` : ""
              }`
            : t("thread.noSource")
        }
        action={
          requirement.document_id && onOpenSource
            ? { label: t("thread.open"), onClick: () => onOpenSource(requirement) }
            : null
        }
      />
      <Connector />
      <ThreadStep
        state={evidenceState}
        icon={evidenceStatus === "confirmed" ? UserCheck : Link2}
        label={t("thread.evidence")}
        value={
          requirement.evidence_document_title
            ? requirement.evidence_document_title
            : t("thread.noEvidence")
        }
      />
      <Connector />
      <ThreadStep
        state={trust.state === "user_confirmed" ? "done" : sourceState}
        icon={CircleCheck}
        label={t("thread.check")}
        value={
          trust.state === "source_verified"
            ? t("trust.states.source_verified")
            : trust.state === "user_confirmed"
              ? t("trust.states.user_confirmed")
              : t("trust.states.needs_review")
        }
      />
    </ol>
  );
}

function Connector() {
  return (
    <li className="flex items-center px-0.5" aria-hidden="true">
      <ArrowRight className="h-3 w-3 text-navy-300 dark:text-navy-600" />
    </li>
  );
}

function ThreadStep({ state, icon: Icon, label, value, action }) {
  const { t } = useTranslation();
  return (
    <li
      className={cn(
        "flex min-w-[9rem] flex-1 items-start gap-2 rounded-lg border px-2.5 py-1.5",
        STEP_STATES[state] || STEP_STATES.empty,
      )}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block text-[10px] font-bold uppercase tracking-[0.1em] opacity-75">
          {label}
        </span>
        <span className="mt-0.5 block truncate font-medium" title={String(value)}>
          {value}
        </span>
        {action ? (
          <button
            type="button"
            onClick={action.onClick}
            className="mt-1 inline-flex items-center gap-1 text-[10px] font-bold text-cobalt-700 hover:underline dark:text-cobalt-300"
          >
            {action.label}
          </button>
        ) : null}
      </span>
    </li>
  );
}

/** The eligibility impact, shown as one of three honest states. */
export function EligibilityMark({ gate }) {
  const { t } = useTranslation();
  if (gate === "pass") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">
        <CircleCheck className="h-3.5 w-3.5" aria-hidden="true" />
        {t("tenders.eligibility.gates.pass")}
      </span>
    );
  }
  if (gate === "fail") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-300 bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        <CircleX className="h-3.5 w-3.5" aria-hidden="true" />
        {t("tenders.eligibility.gates.fail")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
      <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />
      {t("tenders.eligibility.gates.unknown")}
    </span>
  );
}
