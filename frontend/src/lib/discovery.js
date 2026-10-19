// Pure helpers for the discovery UI. Kept free of React so they can be unit tested.

export function scorePercent(score) {
  const value = Number(score);
  if (!Number.isFinite(value)) return 0;
  return Math.round(Math.min(Math.max(value, 0), 1) * 100);
}

export function scoreTone(score) {
  const percent = scorePercent(score);
  if (percent >= 70) return "green";
  if (percent >= 45) return "teal";
  if (percent >= 30) return "amber";
  return "neutral";
}

export function sourceTypeTone(sourceType) {
  if (sourceType === "official") return "teal";
  if (sourceType === "aggregator") return "blue";
  return "neutral";
}

export function fetchStatusTone(status) {
  if (status === "fetched") return "green";
  if (status === "blocked") return "amber";
  if (status === "error") return "red";
  return "neutral";
}

export const EXTRACTED_FIELD_KEYS = ["authority", "reference_number", "deadline", "value", "location"];

// Convert an extracted-field record into display rows, leaving missing fields as null
// so the UI can say "not stated in source" instead of inventing a value.
export function extractedRows(extracted = {}, formatValue = (amount) => String(amount)) {
  return [
    { key: "authority", value: extracted.authority ?? null },
    { key: "reference_number", value: extracted.reference_number ?? null },
    { key: "deadline", value: extracted.deadline ?? null },
    {
      key: "value",
      value:
        extracted.value_amount === null || extracted.value_amount === undefined
          ? null
          : formatValue(extracted.value_amount, extracted.value_currency),
    },
    { key: "location", value: extracted.location ?? null },
  ];
}

export function sortByRelevance(items = []) {
  return [...items].sort((a, b) => {
    const scoreDelta = (b?.relevance?.score ?? 0) - (a?.relevance?.score ?? 0);
    if (scoreDelta !== 0) return scoreDelta;
    const aOfficial = a?.source_type === "official" ? 1 : 0;
    const bOfficial = b?.source_type === "official" ? 1 : 0;
    return bOfficial - aOfficial;
  });
}
