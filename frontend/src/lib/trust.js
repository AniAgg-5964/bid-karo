/**
 * The provenance model.
 *
 * The interface has to be honest about where a statement came from and how
 * far it has been checked. These are the only states the system can actually
 * prove, and each one names the real backend field it is derived from.
 *
 *   ai_extracted     an automated extraction produced it
 *   source_referenced it points at an identifiable source
 *   source_verified  it was found in that source
 *   user_confirmed   a person reviewed and confirmed it
 *   needs_review     the evidence is insufficient, ambiguous or conflicting
 *   unverified       the available information does not support a check
 *   unavailable      the source cannot be reached
 *
 * Nothing here promotes a state on its own. An extracted requirement is never
 * shown as verified because it reads well.
 */

export const TRUST = {
  AI_EXTRACTED: "ai_extracted",
  SOURCE_REFERENCED: "source_referenced",
  SOURCE_VERIFIED: "source_verified",
  USER_CONFIRMED: "user_confirmed",
  NEEDS_REVIEW: "needs_review",
  UNVERIFIED: "unverified",
  REJECTED: "rejected",
  UNAVAILABLE: "unavailable",
  CONTRADICTED: "contradicted",
};

/** The tone used for each state. Colour never carries the meaning alone. */
export const TRUST_TONES = {
  [TRUST.AI_EXTRACTED]: "neutral",
  [TRUST.SOURCE_REFERENCED]: "info",
  [TRUST.SOURCE_VERIFIED]: "verified",
  [TRUST.USER_CONFIRMED]: "verified",
  [TRUST.NEEDS_REVIEW]: "review",
  [TRUST.UNVERIFIED]: "neutral",
  [TRUST.REJECTED]: "blocked",
  [TRUST.UNAVAILABLE]: "neutral",
  [TRUST.CONTRADICTED]: "blocked",
};

/** The icon used for each state. */
export const TRUST_ICONS = {
  [TRUST.AI_EXTRACTED]: "sparkles",
  [TRUST.SOURCE_REFERENCED]: "link",
  [TRUST.SOURCE_VERIFIED]: "shield-check",
  [TRUST.USER_CONFIRMED]: "user-check",
  [TRUST.NEEDS_REVIEW]: "flag",
  [TRUST.UNVERIFIED]: "shield-question",
  [TRUST.REJECTED]: "x",
  [TRUST.UNAVAILABLE]: "unplug",
  [TRUST.CONTRADICTED]: "shield-alert",
};

/**
 * The trust state of one requirement.
 *
 * @param {object} requirement a requirement record
 * @returns {{state: string, tone: string, icon: string, detail: string|null}}
 */
export function requirementTrust(requirement) {
  if (!requirement) {
    return { state: TRUST.UNAVAILABLE, tone: TRUST_TONES[TRUST.UNAVAILABLE], icon: TRUST_ICONS[TRUST.UNAVAILABLE], detail: null };
  }

  const evidenceStatus = requirement.evidence_status || "none";

  // A human decision is the strongest statement we hold.
  if (evidenceStatus === "confirmed") {
    return {
      state: TRUST.USER_CONFIRMED,
      tone: TRUST_TONES[TRUST.USER_CONFIRMED],
      icon: TRUST_ICONS[TRUST.USER_CONFIRMED],
      detail: requirement.evidence_document_title || null,
    };
  }
  if (evidenceStatus === "contradicted") {
    return {
      state: TRUST.CONTRADICTED,
      tone: TRUST_TONES[TRUST.CONTRADICTED],
      icon: TRUST_ICONS[TRUST.CONTRADICTED],
      detail: requirement.evidence_document_title || null,
    };
  }

  // Then the source check: was the excerpt found on the page it names?
  const status = requirement.verification_status || "unverified";
  if (status === "verified") {
    return {
      state: TRUST.SOURCE_VERIFIED,
      tone: TRUST_TONES[TRUST.SOURCE_VERIFIED],
      icon: TRUST_ICONS[TRUST.SOURCE_VERIFIED],
      detail: null,
    };
  }
  if (status === "needs_review") {
    return {
      state: TRUST.NEEDS_REVIEW,
      tone: TRUST_TONES[TRUST.NEEDS_REVIEW],
      icon: TRUST_ICONS[TRUST.NEEDS_REVIEW],
      detail: requirement.verification_notes || null,
    };
  }
  if (status === "rejected") {
    return {
      state: TRUST.REJECTED,
      tone: TRUST_TONES[TRUST.REJECTED],
      icon: TRUST_ICONS[TRUST.REJECTED],
      detail: requirement.verification_notes || null,
    };
  }
  if (requirement.source_url || requirement.document_title) {
    return {
      state: TRUST.SOURCE_REFERENCED,
      tone: TRUST_TONES[TRUST.SOURCE_REFERENCED],
      icon: TRUST_ICONS[TRUST.SOURCE_REFERENCED],
      detail: requirement.verification_notes || null,
    };
  }
  return {
    state: TRUST.UNVERIFIED,
    tone: TRUST_TONES[TRUST.UNVERIFIED],
    icon: TRUST_ICONS[TRUST.UNVERIFIED],
    detail: requirement.verification_notes || null,
  };
}

/** The eligibility gate of a requirement, as the assessment reports it. */
export function eligibilityTrust(gate) {
  if (gate === "pass") {
    return { state: "pass", tone: "verified", icon: "circle-check" };
  }
  if (gate === "fail") {
    return { state: "fail", tone: "blocked", icon: "circle-x" };
  }
  return { state: "unknown", tone: "review", icon: "circle-help" };
}

/**
 * Whether the source of a tender was checked, and when.
 *
 * The states are deliberately distinct: a check that failed is not the same
 * as a check that never ran, and neither is the same as a source we simply
 * do not have.
 */
export function sourceFreshness(tender) {
  if (!tender) return { state: "unknown", tone: "neutral", labelKey: "trust.source.unknown" };
  if (!tender.source_url) {
    return { state: "none", tone: "neutral", labelKey: "trust.source.notRecorded" };
  }
  if (!tender.source_retrieved_at) {
    return { state: "never", tone: "review", labelKey: "trust.source.neverChecked" };
  }
  return { state: "checked", tone: "info", labelKey: "trust.source.checked" };
}
