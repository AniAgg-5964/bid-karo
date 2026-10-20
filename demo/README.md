# BidKaro demo

`bidkaro-demo.mp4` is a captioned walkthrough of the local review build (Phase 5 and Phase 6). It is about 2 minutes 30 seconds long, 1280x720, with burned-in captions and a synthetic narration track.

## What the video shows

| Time | Screen | What it demonstrates |
| --- | --- | --- |
| 0:00 | Sign in | Local demo account, no live client data |
| 0:16 | Dashboard | Metrics derived from stored records only |
| 0:23 | Discover tenders | Live TinyFish search built from the company profile, with the last run's real statistics |
| 0:30 | My tenders | Saved tenders, including the clearly labelled synthetic sample |
| 0:38 | Tender overview | Source provenance, retrieval time, synthetic-sample badge |
| 0:45 | Requirements | 21 source-cited requirements with document, page, clause and verbatim excerpt |
| 0:52 | Documents | The collected RFP, page text, printed page labels, OCR flags |
| 1:00 | Suitability | Deterministic score 74 / moderate with every weight and reason |
| 1:07 | Eligibility | Mandatory gate kept separate from the soft score; unknown is never a pass |
| 1:14 | Checklist | Tender-specific tasks with acceptance criteria, issuer, trigger and citation |
| 1:22 | Legal and contract | Cited clauses labelled as a source summary, not legal advice |
| 1:29 | Changes tab | Baseline snapshot of the stored tender fields |
| 1:36 | Post-award | Obligations generated only from cited performance clauses |
| 1:43 | Reminders | Reminders derived from stored deadlines and tasks; SMTP reported as not configured |
| 1:50 | Changes and alerts | Three real changes detected on a live-discovered tender after a TinyFish recheck |
| 1:59 | Change review | Acknowledging a change stores the human decision and audits it |
| 2:07 | Calendar export | Authenticated ICS download; no calendar OAuth |
| 2:14 | Settings | Opt-in email reminders, configurable lead days, honest missing-SMTP state |

## What is real and what is synthetic

- **Real.** The Discover page statistics come from a live TinyFish run. The three changes in *Changes and alerts* were produced by rechecking a live-discovered source with TinyFish and diffing the stored fields. Every requirement, task and obligation shown carries a real citation to a stored document, page and clause.
- **Synthetic and labelled.** The sample tender, its RFP, the company evidence library and the 21 seeded requirements come from `scripts/make-sample-tender.py` and `scripts/seed-demo.py`. The tender carries a **Synthetic sample** badge and every page of the PDF is stamped `SYNTHETIC SAMPLE - NOT AN OFFICIAL TENDER`. The authority is fictional.
- **Not shown.** No eligibility is claimed, no bid is submitted, no email is sent (SMTP is not configured on the review machine) and no calendar is connected.

## Captions

- The captions are burned into the video so they work in any player.
- `captions.srt` and `captions.vtt` are the same caption track as sidecar files for players that prefer external subtitles.

## Reproducing the video

Prerequisites: Node.js 20+, the backend on `http://127.0.0.1:8000`, the frontend on `http://localhost:5173`, and a scratch folder with the recording tools (they are not repository dependencies):

```powershell
mkdir demo-tools
cd demo-tools
npm init -y
npm i playwright ffmpeg-static
npx playwright install chromium
```

Seed the demo data (deterministic and idempotent):

```powershell
$env:MONGODB_URI='mongodb://localhost:27017'
$env:MONGODB_DB='bidkaro'
.\backend\.venv\Scripts\python.exe scripts\make-sample-tender.py --seed --email asha.phase1@example.com
.\backend\.venv\Scripts\python.exe scripts\seed-demo.py --email asha.phase1@example.com
```

Record, narrate and encode:

```powershell
.\demo\make-video.ps1 -ToolsPath <path-to-demo-tools>
```

The script runs `demo/record-demo.cjs` (Playwright), `demo/build-narration.py` (Windows SAPI narration and the caption sidecar files) and ffmpeg, and writes `demo/bidkaro-demo.mp4`.

If local text-to-speech is unavailable, `demo/build-narration.py` exits with code 3 and reports that narration is unavailable. The captioned silent WebM from `demo/.recording/video` is then the deliverable; no fake audio is produced.

## Files

| File | Purpose |
| --- | --- |
| `bidkaro-demo.mp4` | The captioned walkthrough with narration |
| `captions.srt`, `captions.vtt` | Caption track as sidecar files |
| `record-demo.cjs` | Playwright recorder with the burned-in caption overlay |
| `build-narration.py` | Local speech synthesis, narration mix and caption files |
| `make-video.ps1` | End-to-end record, narrate and encode helper |
