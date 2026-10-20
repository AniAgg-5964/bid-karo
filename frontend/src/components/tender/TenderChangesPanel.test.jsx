import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ChangeRow } from "./TenderChangesPanel";

vi.mock("react-i18next", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useTranslation: () => ({
      t: (key, options) => {
        if (options?.defaultValue) return options.defaultValue;
        if (key.includes("changes.fields.")) return key.split(".").pop();
        return key;
      },
    }),
  };
});

const change = {
  id: "change-1",
  company_id: "company-1",
  tender_id: "tender-1",
  tender_title: "Four-laning of a demo highway",
  field: "deadline",
  old_value: "2026-11-01",
  new_value: "2026-11-15",
  summary: "Submission deadline changed from 2026-11-01 to 2026-11-15",
  severity: "warning",
  review_status: "pending",
  source_url: "https://example.invalid/notice",
  detected_at: "2026-10-20T09:00:00Z",
};

function renderRow(props = {}) {
  return render(
    <MemoryRouter>
      <ChangeRow change={change} onReview={() => {}} busy={false} {...props} />
    </MemoryRouter>,
  );
}

describe("ChangeRow", () => {
  it("shows the summary, the field and both values of a detected change", () => {
    const { unmount } = renderRow();
    expect(screen.getByText(change.summary)).toBeInTheDocument();
    expect(screen.getByText("Deadline")).toBeInTheDocument();
    expect(screen.getByText("2026-11-01")).toBeInTheDocument();
    expect(screen.getByText("2026-11-15")).toBeInTheDocument();
    unmount();
  });

  it("offers review actions only while a change is pending", () => {
    const { unmount } = renderRow();
    expect(screen.getByRole("button", { name: /changes.acknowledge/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /changes.dismiss/ })).toBeInTheDocument();
    unmount();

    renderRow({ change: { ...change, review_status: "acknowledged" } });
    expect(screen.queryByRole("button", { name: /changes.acknowledge/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /changes.dismiss/ })).not.toBeInTheDocument();
  });

  it("links to the source of the change when one was recorded", () => {
    renderRow();
    const link = screen.getByRole("link", { name: /tenders.requirements.source/ });
    expect(link).toHaveAttribute("href", "https://example.invalid/notice");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });
});
