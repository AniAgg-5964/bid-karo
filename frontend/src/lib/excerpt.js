/**
 * Finding a cited excerpt inside the text of its page.
 *
 * The page text is the real stored text, and the excerpt is the real stored
 * excerpt. The two can differ in whitespace and in the typographic quotes a
 * PDF produces, so the match ignores those. The offsets that come back point
 * into the original page text, so the highlight sits on the words the tender
 * actually printed.
 */

const QUOTE_MAP = {
  "‘": "'",
  "’": "'",
  "‚": "'",
  "‛": "'",
  "“": '"',
  "”": '"',
  "„": '"',
  "‟": '"',
  "′": "'",
  "″": '"',
  "‐": "-",
  "‑": "-",
  "‒": "-",
  "–": "-",
  "—": "-",
  "―": "-",
  "−": "-",
  " ": " ",
};

/**
 * Normalise the text and keep a map back to the original positions.
 *
 * The map is what makes the highlight honest: every character of the
 * normalised text remembers the character of the page it came from.
 */
function normaliseWithMap(value) {
  const source = String(value ?? "");
  let text = "";
  const map = [];
  let pendingSpace = false;

  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    const replaced = QUOTE_MAP[character] ?? character;
    if (/\s/.test(replaced)) {
      pendingSpace = true;
      continue;
    }
    if (pendingSpace) {
      pendingSpace = false;
      if (text.length) {
        text += " ";
        map.push(index);
      }
    }
    text += replaced.toLowerCase();
    map.push(index);
  }

  return { text, map };
}

function normalise(value) {
  return normaliseWithMap(value).text;
}

/**
 * The range of `pageText` that holds `excerpt`.
 *
 * @returns {{start: number, end: number, exact: boolean} | null}
 *   `start` and `end` are offsets into `pageText`. `exact` is true when the
 *   excerpt is already a contiguous span of the page.
 */
export function findExcerpt(pageText, excerpt) {
  const source = String(pageText ?? "");
  const needle = normalise(excerpt);
  if (!source || !needle) return null;

  // Fast path: the excerpt is already a contiguous span.
  const direct = source.indexOf(excerpt);
  if (direct !== -1) {
    return { start: direct, end: direct + excerpt.length, exact: true };
  }

  // Otherwise match on the normalised text and map the offsets back.
  const haystack = normaliseWithMap(source);
  const position = haystack.text.indexOf(needle);
  if (position === -1) return null;

  const start = haystack.map[position];
  const lastIndex = position + needle.length - 1;
  const lastOriginal = haystack.map[lastIndex];
  if (start === undefined || lastOriginal === undefined) return null;

  return { start, end: lastOriginal + 1, exact: false };
}

/**
 * The text of a page split around the cited excerpt, so the reader can see
 * the cited words in place.
 */
export function splitAroundExcerpt(pageText, excerpt) {
  const range = findExcerpt(pageText, excerpt);
  if (!range) {
    return { before: pageText || "", cited: "", after: "", found: false };
  }
  return {
    before: (pageText || "").slice(0, range.start),
    cited: (pageText || "").slice(range.start, range.end),
    after: (pageText || "").slice(range.end),
    found: true,
  };
}
