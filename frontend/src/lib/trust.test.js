import { describe, expect, it } from "vitest";

import { TRUST, requirementTrust, sourceFreshness } from "./trust";

describe("requirementTrust", () => {
  it("calls a requirement source-verified only when it was checked against the page", () => {
    const trust = requirementTrust({ verification_status: "verified" });
    expect(trust.state).toBe(TRUST.SOURCE_VERIFIED);
  });

  it("calls a requirement user-confirmed when a person confirmed the evidence", () => {
    const trust = requirementTrust({
      verification_status: "verified",
      evidence_status: "confirmed",
      evidence_document_title: "ISO 9001 certificate",
    });
    expect(trust.state).toBe(TRUST.USER_CONFIRMED);
    expect(trust.detail).toBe("ISO 9001 certificate");
  });

  it("calls a contradicted evidence match contradicted, not failed", () => {
    const trust = requirementTrust({
      verification_status: "verified",
      evidence_status: "contradicted",
    });
    expect(trust.state).toBe(TRUST.CONTRADICTED);
  });

  it("calls an unchecked requirement needs review and keeps the reason", () => {
    const trust = requirementTrust({
      verification_status: "needs_review",
      verification_notes: "The excerpt was not found on the cited page.",
    });
    expect(trust.state).toBe(TRUST.NEEDS_REVIEW);
    expect(trust.detail).toContain("not found");
  });

  it("never calls an unchecked requirement verified", () => {
    const trust = requirementTrust({ verification_status: "unverified" });
    expect(trust.state).not.toBe(TRUST.SOURCE_VERIFIED);
    expect(trust.state).not.toBe(TRUST.USER_CONFIRMED);
  });

  it("falls back to source-referenced when the requirement points at a source", () => {
    const trust = requirementTrust({
      verification_status: "unverified",
      document_title: "RFP",
      source_url: "https://example.gov.in/tender",
    });
    expect(trust.state).toBe(TRUST.SOURCE_REFERENCED);
  });

  it("handles a missing requirement without throwing", () => {
    expect(requirementTrust(null).state).toBe(TRUST.UNAVAILABLE);
  });
});

describe("sourceFreshness", () => {
  it("says a source that was never checked has not been checked", () => {
    const state = sourceFreshness({ source_url: "https://example.gov.in", source_retrieved_at: null });
    expect(state.state).toBe("never");
    expect(state.tone).toBe("review");
  });

  it("says a checked source was checked", () => {
    const state = sourceFreshness({
      source_url: "https://example.gov.in",
      source_retrieved_at: "2026-10-20T09:00:00Z",
    });
    expect(state.state).toBe("checked");
  });

  it("says a tender with no source has no source recorded", () => {
    expect(sourceFreshness({ source_url: null }).state).toBe("none");
  });
});
