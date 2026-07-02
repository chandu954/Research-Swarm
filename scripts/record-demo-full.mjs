/**
 * Full product demo — landing → settings → PDFs → multi-agent research → results.
 * Requires backend (:8000) and frontend (:3001) running.
 */
import { chromium } from "playwright";
import { mkdir, readFile, rename, readdir, copyFile } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import { execSync } from "child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const FRONTEND_URL = process.env.DEMO_URL || "http://localhost:3001";
const OUTPUT_DIR = path.join(ROOT, "assets");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function loadEnv() {
  const raw = await readFile(path.join(ROOT, "backend", ".env"), "utf8");
  const env = {};
  for (const line of raw.split("\n")) {
    const m = line.match(/^([A-Z_]+)=(.*)$/);
    if (m) env[m[1]] = m[2].trim();
  }
  return env;
}

async function main() {
  const env = await loadEnv();
  const providerSettings = {
    provider: "openrouter",
    plannerModel: env.PLANNER_MODEL || "qwen/qwen3-32b",
    researchModel: env.RESEARCH_MODEL || "google/gemini-2.5-flash",
    documentModel: env.DOCUMENT_MODEL || "qwen/qwen3-32b",
    answerModel: env.ANSWER_MODEL || "mistralai/mistral-small-3.2-24b-instruct",
    openrouterKey: env.OPENROUTER_API_KEY || "",
  };

  await mkdir(OUTPUT_DIR, { recursive: true });
  const videoDir = path.join(OUTPUT_DIR, ".recordings");
  await mkdir(videoDir, { recursive: true });

  console.log("Recording full functional demo ...");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: videoDir, size: { width: 1440, height: 900 } },
  });

  await context.addInitScript((settings) => {
    localStorage.setItem(
      "researchswarm-provider-settings",
      JSON.stringify(settings),
    );
  }, providerSettings);

  const page = await context.newPage();

  try {
    // 1. Landing page
    console.log("  → Landing page");
    await page.goto(FRONTEND_URL, { waitUntil: "domcontentloaded", timeout: 30000 });
    await sleep(4000);
    await page.evaluate(() => window.scrollBy({ top: 700, behavior: "smooth" }));
    await sleep(3000);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
    await sleep(2000);

    // 2. Open workspace
    console.log("  → Research workspace");
    await page.getByRole("link", { name: /start researching/i }).click();
    await page.waitForURL("**/app**", { timeout: 15000 });
    await page.waitForSelector("text=What do you want to research today?", {
      timeout: 20000,
    });
    await sleep(2500);

    // 3. Show OpenRouter settings
    console.log("  → Provider settings");
    await page.getByRole("button", { name: "Settings" }).click();
    await page.waitForSelector("h2:text('Settings')", { timeout: 5000 });
    await sleep(2500);
    await page.getByRole("button", { name: "openrouter" }).click();
    await sleep(2500);
    await page.locator(".fixed.inset-0.z-40").click({ position: { x: 10, y: 10 } });
    await sleep(1200);

    // 4. Start research
    console.log("  → Running multi-agent research ...");
    await page.getByRole("button", { name: /Research LangGraph/i }).click();

    // 6. Show live AI workflow while agents run
    const workflow = page.locator("text=AI workflow").first();
    if (await workflow.count()) {
      await workflow.scrollIntoViewIfNeeded();
    }
    await page.waitForSelector("text=Thinking", { timeout: 15000 }).catch(() => {});
    await sleep(6000);

    // Wait for agent timeline activity
    await page
      .waitForFunction(
        () => {
          const text = document.body.innerText;
          return (
            text.includes("Complete") ||
            text.includes("Planner") ||
            text.includes("Web research")
          );
        },
        { timeout: 30000 },
      )
      .catch(() => {});
    await sleep(4000);

    // 7. Wait for final answer
    await page
      .waitForFunction(
        () => {
          const text = document.body.innerText;
          const hasAnswer =
            text.includes("References") ||
            text.includes("## ") ||
            text.includes("LangGraph");
          return hasAnswer && !text.includes("Thinking...");
        },
        { timeout: 150000 },
      )
      .catch(() => console.warn("  ⚠ Answer timeout — saving partial recording."));
    console.log("  → Answer received");

    await sleep(3500);

    // 8. Scroll chat answer into view
    await page.evaluate(() => {
      const main = document.querySelector("main");
      const scrollables = main
        ? [...main.querySelectorAll("*")].filter(
            (el) => el.scrollHeight > el.clientHeight + 100,
          )
        : [];
      for (const el of scrollables.slice(0, 2)) {
        el.scrollTop = el.scrollHeight;
      }
    });
    await sleep(3000);

    // 9. Sources panel
    console.log("  → Sources & metrics");
    const sources = page.locator("text=Sources").first();
    if (await sources.count()) {
      await sources.scrollIntoViewIfNeeded();
      await sleep(2500);
    }

    const plan = page.locator("text=Execution plan").first();
    if (await plan.count()) {
      await plan.scrollIntoViewIfNeeded();
      await sleep(2500);
    }

    const metrics = page.locator("text=Run metrics").first();
    if (await metrics.count()) {
      await metrics.scrollIntoViewIfNeeded();
      await sleep(3000);
    }

    await sleep(2000);
  } finally {
    await page.close();
    await context.close();
    await browser.close();
  }

  const files = await readdir(videoDir);
  const webm = files.find((f) => f.endsWith(".webm"));
  if (!webm) throw new Error("No recording produced.");

  const webmPath = path.join(OUTPUT_DIR, "demo.webm");
  const mp4Path = path.join(OUTPUT_DIR, "demo.mp4");
  const fullWebm = path.join(OUTPUT_DIR, "demo-full.webm");
  const fullMp4 = path.join(OUTPUT_DIR, "demo-full.mp4");

  await rename(path.join(videoDir, webm), webmPath);
  console.log(`Saved: ${webmPath}`);

  try {
    execSync(
      `ffmpeg -y -i "${webmPath}" -c:v libx264 -pix_fmt yuv420p -movflags +faststart "${mp4Path}"`,
      { stdio: "pipe" },
    );
    console.log(`Saved: ${mp4Path}`);
    await copyFile(webmPath, fullWebm);
    await copyFile(mp4Path, fullMp4);
    console.log(`Copied to: ${fullMp4}`);
  } catch (e) {
    console.warn("ffmpeg conversion skipped:", e.message);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
