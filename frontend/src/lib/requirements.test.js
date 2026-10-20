import { describe, expect, it } from "vitest";

import {
  categoryTone,
  isSampleTender,
  pageReference,
  requirementQuery,
  summarizeRequirements,
  verificationTone,
} from "./requirements";

describe("requirementQuery", () => {
  it("builds an encoded query from active filters", () => {
    expect(
      requirementQuery({ category: "eligibility", verification_status: "unverified" }),
    ).toBe("?category=eligibility&verification_status=unverified");
  });

  it("omits empty filters", () => {
    expect(requirementQuery({ category: "", mandatory: "unknown" })).toBe("?mandatory=unknown");
    expect(requirementQuery()).toBe("");
  });
});

describe("pageReference", () => {
  it("reports a printed label only when it differs from the viewer page", () => {
    expect(pageReference({ page_index: 3, printed_page: "3" })).toEqual({
      viewer: 3,
      printed: "",
    });
    expect(pageReference({ page_index: 3, printed_page: "A-2" })).toEqual({
      viewer: 3,
      printed: "A-2",
    });
  });
});

describe("tones and summaries", () => {
  it("maps verification and category states to readable tones", () => {
    expect(verificationTone("verified")).toBe("green");
    expect(verificationTone("unverified")).toBe("amber");
    expect(verificationTone("rejected")).toBe("red");
    expect(categoryTone("eligibility")).toBe("teal");
    expect(categoryTone("unknown")).toBe("neutral");
  });

  it("counts verified and unverified items", () => {
    expect(
      summarizeRequirements([
        { verification_status: "verified" },
        { verification_status: "unverified" },
        { verification_status: "needs_review" },
      ]),
    ).toEqual({ total: 3, verified: 1, unverified: 1 });
  });

  it("marks only flagged tenders as samples", () => {
    expect(isSampleTender({ is_sample: true })).toBe(true);
    expect(isSampleTender({})).toBe(false);
    expect(isSampleTender(null)).toBe(false);
  });
});
