import { describe, expect, it } from "vitest";

import { extractedRows, fetchStatusTone, scorePercent, scoreTone, sortByRelevance, sourceTypeTone } from "./discovery";

describe("score helpers", () => {
  it("converts a 0-1 score into a clamped percentage", () => {
    expect(scorePercent(0.825)).toBe(83);
    expect(scorePercent(0)).toBe(0);
    expect(scorePercent(undefined)).toBe(0);
    expect(scorePercent(1.4)).toBe(100);
  });

  it("maps scores to tones", () => {
    expect(scoreTone(0.9)).toBe("green");
    expect(scoreTone(0.5)).toBe("teal");
    expect(scoreTone(0.31)).toBe("amber");
    expect(scoreTone(0.1)).toBe("neutral");
  });

  it("tones source types and fetch states", () => {
    expect(sourceTypeTone("official")).toBe("teal");
    expect(sourceTypeTone("aggregator")).toBe("blue");
    expect(fetchStatusTone("fetched")).toBe("green");
    expect(fetchStatusTone("blocked")).toBe("amber");
    expect(fetchStatusTone("error")).toBe("red");
  });
});

describe("sortByRelevance", () => {
  it("orders by score then prefers official sources", () => {
    const items = [
      { title: "b", source_type: "aggregator", relevance: { score: 0.5 } },
      { title: "a", source_type: "official", relevance: { score: 0.5 } },
      { title: "c", source_type: "aggregator", relevance: { score: 0.9 } },
    ];
    expect(sortByRelevance(items).map((item) => item.title)).toEqual(["c", "a", "b"]);
  });

  it("does not mutate the input", () => {
    const items = [{ title: "x", relevance: { score: 0.1 } }];
    sortByRelevance(items);
    expect(items).toHaveLength(1);
  });
});

describe("extractedRows", () => {
  it("keeps missing fields null so the UI can label them honestly", () => {
    const rows = extractedRows({ authority: "PWD", value_amount: 1250000, value_currency: "INR" }, (amount, currency) => `${currency} ${amount}`);
    const byKey = Object.fromEntries(rows.map((row) => [row.key, row.value]));
    expect(byKey.authority).toBe("PWD");
    expect(byKey.value).toBe("INR 1250000");
    expect(byKey.deadline).toBeNull();
    expect(byKey.reference_number).toBeNull();
    expect(byKey.location).toBeNull();
  });
});
