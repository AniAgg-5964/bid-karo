import { describe, expect, it } from "vitest";

import { findExcerpt, splitAroundExcerpt } from "./excerpt";

const PAGE =
  "3. Eligibility\n\n3.1 The bidder shall have an average annual turnover of at least INR 5 crore during the last three financial years.\n\n3.2 The bidder shall hold a valid ISO 9001:2015 certification.";

describe("findExcerpt", () => {
  it("finds an excerpt that is already a span of the page", () => {
    const range = findExcerpt(PAGE, "The bidder shall hold a valid ISO 9001:2015 certification.");
    expect(range).not.toBeNull();
    expect(range.exact).toBe(true);
    expect(PAGE.slice(range.start, range.end)).toBe(
      "The bidder shall hold a valid ISO 9001:2015 certification.",
    );
  });

  it("finds an excerpt that differs only in whitespace", () => {
    const range = findExcerpt(PAGE, "average annual turnover   of at\nleast INR 5 crore");
    expect(range).not.toBeNull();
    expect(range.exact).toBe(false);
    expect(PAGE.slice(range.start, range.end)).toContain("average annual turnover");
  });

  it("finds an excerpt that differs in typographic quotes", () => {
    const page = "The authority said “the work shall begin” on 1 April.";
    const range = findExcerpt(page, 'the work shall begin');
    expect(range).not.toBeNull();
    // The highlight covers the cited words themselves, inside the page's own
    // quotation marks.
    expect(page.slice(range.start, range.end)).toBe("the work shall begin");
    expect(page[range.start - 1]).toBe("“");
  });

  it("returns nothing for an excerpt that is not in the page", () => {
    expect(findExcerpt(PAGE, "a performance guarantee of five percent")).toBeNull();
  });

  it("returns nothing for an empty page or excerpt", () => {
    expect(findExcerpt("", "anything")).toBeNull();
    expect(findExcerpt(PAGE, "")).toBeNull();
  });
});

describe("splitAroundExcerpt", () => {
  it("splits the page so the cited words sit in place", () => {
    const parts = splitAroundExcerpt(PAGE, "The bidder shall have an average annual turnover");
    expect(parts.found).toBe(true);
    expect(parts.cited).toBe("The bidder shall have an average annual turnover");
    expect(parts.before).toContain("3.1");
    expect(parts.after).toContain("3.2");
  });

  it("reports when the excerpt is not in the page", () => {
    const parts = splitAroundExcerpt(PAGE, "something else entirely");
    expect(parts.found).toBe(false);
    expect(parts.cited).toBe("");
  });
});
