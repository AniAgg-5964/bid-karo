import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EvidenceDock } from "./EvidenceDock";
import { api } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: { get: vi.fn() },
}));

const REQUIREMENT = {
  id: "requirement-1",
  document_id: "document-1",
  document_title: "Synthetic RFP",
  page_index: 3,
  printed_page: "3",
  clause_reference: "3.1",
  excerpt: "The bidder shall have an average annual turnover of INR 5 crore.",
  verification_status: "verified",
  evidence_status: "none",
  source_url: "https://example.gov.in/tender/road-14",
  document_retrieved_at: "2026-10-20T09:00:00Z",
};

const PAGE = {
  page_index: 3,
  printed_label: "3",
  text:
    "3. Eligibility\n\n3.1 The bidder shall have an average annual turnover of INR 5 crore.\n\n3.2 The bidder shall hold a valid ISO 9001 certification.",
  has_text: true,
  text_source: "text_layer",
};

describe("EvidenceDock", () => {
  it("shows the cited words in place on the source page", async () => {
    api.get.mockResolvedValue(PAGE);
    render(
      <EvidenceDock open requirement={REQUIREMENT} tenderId="tender-1" onClose={() => {}} />,
    );

    await waitFor(() => expect(api.get).toHaveBeenCalled());
    const mark = await screen.findByText(
      "The bidder shall have an average annual turnover of INR 5 crore.",
      { selector: "mark" },
    );
    expect(mark).toBeInTheDocument();
    expect(mark.className).toContain("cited");
  });

  it("says the source page is not available instead of showing nothing", async () => {
    api.get.mockRejectedValue(Object.assign(new Error("missing"), { status: 404 }));
    render(
      <EvidenceDock open requirement={REQUIREMENT} tenderId="tender-1" onClose={() => {}} />,
    );

    expect(await screen.findByText(/not available/i)).toBeInTheDocument();
  });

  it("shows the source identity and the page it came from", async () => {
    api.get.mockResolvedValue(PAGE);
    render(
      <EvidenceDock open requirement={REQUIREMENT} tenderId="tender-1" onClose={() => {}} />,
    );

    expect(await screen.findByText("Synthetic RFP")).toBeInTheDocument();
    expect(screen.getByText("3.1")).toBeInTheDocument();
  });
});
