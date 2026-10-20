export const REQUIREMENT_CATEGORIES = [
  "eligibility",
  "technical",
  "financial",
  "compliance",
  "submission",
  "performance",
  "other",
];

export const VERIFICATION_STATUSES = ["verified", "unverified", "needs_review", "rejected"];
export const MANDATORY_VALUES = ["yes", "no", "unknown"];

export function requirementQuery(filters = {}) {
  const params = new URLSearchParams();
  for (const key of ["category", "verification_status", "mandatory", "document_id"]) {
    const value = filters[key];
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function pageReference(requirement) {
  if (!requirement) return "";
  const viewer = Number(requirement.page_index) || 0;
  const printed = String(requirement.printed_page ?? "").trim();
  if (printed && printed !== String(viewer)) {
    return { viewer, printed };
  }
  return { viewer, printed: "" };
}

export function verificationTone(status) {
  if (status === "verified") return "green";
  if (status === "unverified") return "amber";
  if (status === "needs_review") return "amber";
  if (status === "rejected") return "red";
  return "neutral";
}

export function categoryTone(category) {
  if (category === "eligibility") return "teal";
  if (category === "financial") return "blue";
  if (category === "technical") return "neutral";
  if (category === "compliance") return "amber";
  if (category === "submission") return "blue";
  if (category === "performance") return "neutral";
  return "neutral";
}

export function summarizeRequirements(items = []) {
  return items.reduce(
    (summary, item) => {
      summary.total += 1;
      if (item.verification_status === "verified") summary.verified += 1;
      if (item.verification_status === "unverified") summary.unverified += 1;
      return summary;
    },
    { total: 0, verified: 0, unverified: 0 },
  );
}

export function isSampleTender(tender) {
  return Boolean(tender?.is_sample);
}
