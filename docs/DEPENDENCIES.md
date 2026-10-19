# Dependencies and security notes

This document records what we ship, what we audit, and the deliberate decisions behind any
remaining advisories.

## Audit policy

- The **production** surface is what ships to users. It must be clean:
  `cd frontend; npm audit --omit=dev` → 0 vulnerabilities.
- **Development-only** advisories (test runner, build watcher, CSS parser) are tracked but not
  treated as release blockers. They never execute in the deployed frontend.

## Current state (2026-10-20)

Frontend:

| Package | Version | Notes |
| --- | --- | --- |
| react | 18.3.x | |
| react-dom | 18.3.x | |
| react-router-dom | 7.18.x | upgraded from 6.x to clear the open-redirect advisory |
| vite | 8.3.x | dev/build only |
| vitest | 5.0.x | dev/test only |
| jsdom | 30.1.x | dev/test only |
| @vitejs/plugin-react | 6.1.x | dev/build only |
| tailwindcss | 3.4.x | see below |

- `npm audit --omit=dev`: **0 vulnerabilities**.
- `npm audit` (full tree): **7 vulnerabilities (2 moderate, 5 high)**, all of them inside the
  `tailwindcss@3` build-time dependency chain (`braces`, `chokidar`, `micromatch`, `fast-glob`,
  `postcss-nested`, `postcss-selector-parser`).

## Why Tailwind v3 advisories are accepted for now

- Every remaining advisory is in the **Tailwind CLI/watch/build** path. Tailwind is compiled at
  build time into a static stylesheet; none of these packages run in the browser or on the server.
- The exposure requires a maliciously crafted glob or CSS selector processed during a local build —
  not attacker-controllable in this application.
- The only available fix is Tailwind `4.x`, which is a real migration: new config format
  (`@import "tailwindcss"`), CSS-first configuration, changed content detection, and renamed
  utilities. Doing it blindly risks visual regressions across the whole UI.
- Decision (agreed with the project owner): defer the Tailwind 4 migration to its own isolated,
  fully re-verified step, and document it rather than rush it into a dependency-bump commit.

## When to revisit

- Before any public/hosted deployment, re-run `npm audit --omit=dev` and confirm it is still clean.
- Schedule the Tailwind 3 → 4 migration as a standalone change with a visual regression pass over
  every page in light and dark mode, both languages.
