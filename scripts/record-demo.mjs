/**
 * Records a product demo of ResearchSwarm AI for README / marketing.
 * Requires backend (8000) and frontend (3001) to be running.
 */
import { chromium } from "playwright";
import { mkdir, rename, readdir } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const FRONTEND_URL = process.env.DEMO_URL || "http://localhost:3001";
const OUTPUT_DIR = path.join(ROOT, "assets");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  await mkdir(OUTPUT_DIR, { recursive: true });
  const videoDir = path.join(OUTPUT_DIR, ".recordings");
  await mkdir(videoDir, { recursive: true });

  console.log(`Recording demo from ${FRONTEND_URL} ...`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: {
      dir: videoDir,
      size: { width: 1440, height: 900 },
    },
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();

  try {
    // 1. Landing page intro
    await page.goto(FRONTEND_URL, { waitUntil: "domcontentloaded", timeout: 30000 });
    await sleep(3000);
    await page.evaluate(() => window.scrollBy({ top: 500, behavior: "smooth" }));
    await sleep(1800);

    // 2. Open workspace
    await page.goto(`${FRONTEND_URL}/app`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForSelector("text=What do you want to research today?", {
      timeout: 20000,
    });
    await sleep(2000);

    // 3. Click a suggested prompt (more reliable than typing)
    await page.getByRole("button", { name: /Research LangGraph/i }).click();

    // 4. Show agents working
    await page.waitForSelector("text=Thinking", { timeout: 15000 }).catch(() => {});
    await sleep(4000);

    // 5. Wait for answer
    await page
      .waitForFunction(
        () => {
          const text = document.body.innerText;
          const done =
            text.includes("References") ||
            text.includes("## ") ||
            text.includes("LangGraph");
          const stillThinking = text.includes("Thinking...");
          return done && !stillThinking;
        },
        { timeout: 120000 },
      )
      .catch(() =>
        console.warn("Timed out waiting for full answer — saving partial recording."),
      );

    await sleep(4000);
    await page.evaluate(() => {
      const areas = [...document.querySelectorAll("[class*='overflow-y']")];
      for (const el of areas) {
        if (el.scrollHeight > el.clientHeight + 40) {
          el.scrollTop = el.scrollHeight;
        }
      }
    });
    await sleep(2500);
  } finally {
    await page.close();
    await context.close();
    await browser.close();
  }

  const files = await readdir(videoDir);
  const webm = files.find((f) => f.endsWith(".webm"));
  if (!webm) {
    throw new Error("No recording file produced by Playwright.");
  }

  const dest = path.join(OUTPUT_DIR, "demo.webm");
  await rename(path.join(videoDir, webm), dest);
  console.log(`Saved: ${dest}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
