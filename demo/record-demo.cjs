/*
 * BidKaro demo recorder.
 *
 * Records a captioned walkthrough of the local review build with Playwright and
 * writes the caption track next to the raw video so narration can be mixed in.
 *
 * Requirements (install them in a scratch folder, not in the repository):
 *   npm i playwright ffmpeg-static
 *   npx playwright install chromium
 *
 * Usage (from the repository root):
 *   set NODE_PATH=<scratch>\node_modules
 *   set DEMO_OUT_DIR=demo\.recording
 *   node demo\record-demo.cjs
 *
 * Environment overrides:
 *   DEMO_APP_URL    default http://localhost:5173
 *   DEMO_EMAIL     default asha.phase1@example.com
 *   DEMO_PASSWORD  default BidKaro123
 *   DEMO_OUT_DIR   default demo\.recording
 */

const fs = require("fs");
const path = require("path");

const { chromium } = require("playwright");

const APP_URL = process.env.DEMO_APP_URL || "http://localhost:5173";
const EMAIL = process.env.DEMO_EMAIL || "asha.phase1@example.com";
const PASSWORD = process.env.DEMO_PASSWORD || "BidKaro123";
const OUT_DIR = path.resolve(process.env.DEMO_OUT_DIR || path.join(__dirname, ".recording"));
const VIDEO_DIR = path.join(OUT_DIR, "video");
const SHOT_DIR = path.join(OUT_DIR, "shots");

const CAPTION_STYLE = `
  #bidkaro-demo-caption {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 2147483647;
    display: flex;
    justify-content: center;
    padding: 14px 28px 18px;
    background: linear-gradient(to top, rgba(4, 12, 26, 0.94) 55%, rgba(4, 12, 26, 0));
    pointer-events: none;
  }
  #bidkaro-demo-caption span {
    max-width: 1040px;
    text-align: center;
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 19px;
    line-height: 1.45;
    font-weight: 600;
    color: #ffffff;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.9);
  }
  #bidkaro-demo-caption span em {
    color: #5eead4;
    font-style: normal;
  }
`;

const captions = [];
let startMs = Date.now();

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureOverlay(page) {
  const exists = await page.evaluate(() => Boolean(document.getElementById("bidkaro-demo-caption")));
  if (!exists) {
    await page.addStyleTag({ content: CAPTION_STYLE });
    await page.evaluate(() => {
      const box = document.createElement("div");
      box.id = "bidkaro-demo-caption";
      const text = document.createElement("span");
      box.appendChild(text);
      document.body.appendChild(box);
    });
  }
}

async function caption(page, text, holdMs = 4200) {
  await ensureOverlay(page);
  await page.evaluate((value) => {
    const box = document.getElementById("bidkaro-demo-caption");
    if (box) box.firstElementChild.textContent = value;
  }, text);
  captions.push({ text, startMs: Date.now() - startMs, endMs: Date.now() - startMs + holdMs });
  await sleep(holdMs);
}

async function shot(page, name) {
  await page.screenshot({ path: path.join(SHOT_DIR, `${name}.png`) });
}

async function main() {
  fs.mkdirSync(VIDEO_DIR, { recursive: true });
  fs.mkdirSync(SHOT_DIR, { recursive: true });

  const browser = await chromium.launch({ args: ["--autoplay-policy=no-user-gesture-required"] });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: VIDEO_DIR, size: { width: 1280, height: 720 } },
    colorScheme: "light",
    locale: "en-IN",
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  startMs = Date.now();

  // 1. Sign in.
  await page.goto(`${APP_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#email");
  await ensureOverlay(page);
  await caption(page, "BidKaro: tender discovery, cited requirements and compliance workflow.", 7000);
  await page.fill("#email", EMAIL);
  await page.fill("#password", PASSWORD);
  await caption(page, "Signing in to a local demo workspace with demo data.", 7000);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/app/dashboard");

  // 2. Dashboard.
  await page.waitForSelector("text=Dashboard");
  await caption(page, "Dashboard numbers come only from stored records, never from sample metrics.", 7000);
  await shot(page, "01-dashboard");

  // 3. Live discovery.
  await page.getByRole("link", { name: "Discover tenders" }).click();
  await page.waitForSelector("text=/Live discovery is (connected|not configured)/");
  await caption(page, "Discovery runs a live TinyFish search built from your company profile.", 7000);
  await shot(page, "02-discover");

  // 4. Saved tenders.
  await page.getByRole("link", { name: "My tenders" }).click();
  await page.waitForSelector("text=/Synthetic sample tender/");
  await caption(page, "Saved tenders. The first one is a clearly labelled synthetic sample.", 7000);
  await shot(page, "03-tenders");

  // 5. Tender overview.
  await page.getByRole("link", { name: /Synthetic sample tender/ }).first().click();
  await page.waitForSelector("text=Source and provenance");
  await caption(page, "Overview shows the source, the retrieval time and the sample badge.", 7000);
  await shot(page, "04-overview");

  // 6. Requirements.
  await page.getByRole("tab", { name: "Requirements" }).click();
  await page.getByText("Extracted requirements").first().waitFor();
  await caption(page, "Every requirement keeps its document, page, clause and verbatim excerpt.", 7000);
  await shot(page, "05-requirements");

  // 7. Documents.
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByText("Tender documents").first().waitFor();
  await caption(page, "Documents hold the RFP with page text, printed labels and OCR flags.", 7000);
  await shot(page, "06-documents");

  // 8. Suitability.
  await page.getByRole("tab", { name: "Suitability" }).click();
  await page.getByText("Deterministic suitability score").first().waitFor();
  await caption(page, "Suitability is a deterministic score with every weight and reason shown.", 7000);
  await shot(page, "07-suitability");

  // 9. Eligibility.
  await page.getByRole("tab", { name: "Eligibility" }).click();
  await page.getByText("Mandatory eligibility").first().waitFor();
  await caption(page, "Eligibility stays separate, and unknown is never a pass.", 7000);
  await shot(page, "08-eligibility");

  // 10. Checklist.
  await page.getByRole("tab", { name: "Checklist" }).click();
  await page.getByText("Submission and compliance checklist").first().waitFor();
  await caption(page, "Checklist tasks are tender-specific with acceptance criteria and a citation.", 7000);
  await shot(page, "09-checklist");

  // 11. Legal.
  await page.getByRole("tab", { name: "Legal & contract" }).click();
  await page.getByText("Legal and contract obligations").first().waitFor();
  await caption(page, "Legal clauses are cited summaries, not legal advice.", 7000);
  await shot(page, "10-legal");

  // 12. Changes tab.
  await page.getByRole("tab", { name: "Changes" }).click();
  await page.getByText("Source changes").first().waitFor();
  await caption(page, "A baseline snapshot lets a later source recheck be diffed.", 7000);
  await shot(page, "11-changes-tab");

  // 13. Post-award obligations.
  await page.getByRole("tab", { name: "Post-award" }).click();
  await page.getByText("Post-award obligations").first().waitFor();
  await caption(page, "Post-award obligations come only from cited performance clauses.", 7000);
  await shot(page, "12-post-award");

  // 14. Reminders.
  await page.getByRole("link", { name: "Reminders" }).click();
  await page.getByText("Email reminders").first().waitFor();
  await page.getByText(/pending$/).first().waitFor();
  await caption(page, "Reminders come from stored deadlines and tasks. Email needs SMTP.", 7000);
  await shot(page, "13-reminders");

  // 15. Global change review with a real detected change.
  await page.getByRole("link", { name: "Changes & alerts" }).click();
  await page.getByText("Changes & alerts").first().waitFor();
  await caption(page, "Three real changes were detected after a TinyFish recheck of a live source.", 7000);
  await shot(page, "14-changes");

  // 16. Acknowledge one change.
  const acknowledge = page.getByRole("button", { name: "Acknowledge" }).first();
  if (await acknowledge.count()) {
    await acknowledge.click();
    await sleep(1200);
  }
  await caption(page, "Acknowledging stores the human decision and audits it.", 7000);
  await shot(page, "15-changes-acknowledged");

  // 17. Calendar export.
  await page.getByRole("link", { name: "Compliance" }).click();
  await page.getByRole("button", { name: /Export calendar/i }).first().waitFor();
  const download = page.waitForEvent("download", { timeout: 20000 }).catch(() => null);
  const exportButton = page.getByRole("button", { name: /Export calendar/i }).first();
  if (await exportButton.count()) {
    await exportButton.click();
  }
  const file = await download;
  if (file) {
    const target = path.join(OUT_DIR, file.suggestedFilename());
    await file.saveAs(target);
    console.log(`downloaded ${target}`);
  }
  await caption(page, "Calendar export is an authenticated ICS file, with no calendar OAuth.", 7000);
  await shot(page, "16-calendar-export");

  // 18. Settings.
  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByText("Email reminders").first().waitFor();
  await caption(page, "Email reminders are opt-in and lead days are configurable.", 7000);
  await shot(page, "17-settings");

  // 19. Close.
  await caption(page, "Only real TinyFish data and labelled synthetic data. No bid is submitted.", 8000);

  await context.close();
  await browser.close();

  const videoFiles = fs.readdirSync(VIDEO_DIR).filter((name) => name.endsWith(".webm"));
  if (!videoFiles.length) {
    throw new Error("Playwright did not write a video file.");
  }
  const rawVideo = path.join(VIDEO_DIR, videoFiles[0]);
  const manifest = {
    appUrl: APP_URL,
    account: EMAIL,
    rawVideo,
    captions: captions.map((item) => ({ ...item, startMs: item.startMs, endMs: item.endMs })),
  };
  fs.writeFileSync(path.join(OUT_DIR, "captions.json"), JSON.stringify(manifest, null, 2));
  console.log(`raw video: ${rawVideo}`);
  console.log(`captions:  ${captions.length}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
