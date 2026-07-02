/**
 * Build a 2:30–3:00 story-driven demo (v2).
 * Usage: npm run demo:story
 */
import { chromium } from "playwright";
import { readFile, mkdir, writeFile, readdir } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import { execSync } from "child_process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const DEMO_DIR = path.join(__dirname);
const OUT_DIR = path.join(ROOT, "assets", "demo-build");
const FRONTEND = process.env.DEMO_URL || "http://localhost:3001";
const SLIDES = `file://${path.join(DEMO_DIR, "slides.html")}`;

const LANGGRAPH_QUERY =
  "Research LangGraph. Explain architecture, StateGraph, advantages, and compare with LangChain. Generate a report with citations.";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function run(cmd) {
  execSync(cmd, { stdio: "pipe", maxBuffer: 50 * 1024 * 1024 });
}

function dur(file) {
  return parseFloat(
    execSync(`ffprobe -v error -show_entries format=duration -of csv=p=0 "${file}"`, {
      encoding: "utf8",
    }).trim(),
  );
}

async function loadEnv() {
  const raw = await readFile(path.join(ROOT, "backend", ".env"), "utf8");
  const env = {};
  for (const line of raw.split("\n")) {
    const m = line.match(/^([A-Z_]+)=(.*)$/);
    if (m) env[m[1]] = m[2].trim();
  }
  return env;
}

function generateNarration(text, voice, rate, aiff, m4a) {
  const escaped = text.replace(/"/g, '\\"');
  run(`say -v ${voice} -r ${rate} -o "${aiff}" "${escaped}"`);
  run(`ffmpeg -y -i "${aiff}" -c:a aac -b:a 192k "${m4a}"`);
}

async function slideToVideo(slideId, seconds, outMp4) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${SLIDES}?slide=${slideId}`, { waitUntil: "domcontentloaded" });
  await sleep(400);
  const png = path.join(OUT_DIR, `slide-${slideId}.png`);
  await page.screenshot({ path: png });
  await browser.close();
  run(
    `ffmpeg -y -loop 1 -i "${png}" -filter_complex "[0:v]scale=1440:900,format=yuv420p[v]" ` +
      `-map "[v]" -c:v libx264 -t ${seconds} -pix_fmt yuv420p -r 30 "${outMp4}"`,
  );
}

function trimVideo(input, seconds, output) {
  run(
    `ffmpeg -y -i "${input}" -t ${seconds} -c:v libx264 -pix_fmt yuv420p -an "${output}"`,
  );
}

function padAudio(audioIn, targetSec, outM4a) {
  const current = dur(audioIn);
  if (current >= targetSec - 0.2) {
    run(`cp "${audioIn}" "${outM4a}"`);
    return targetSec;
  }
  const pad = targetSec - current;
  run(
    `ffmpeg -y -i "${audioIn}" -af "apad=pad_dur=${pad}" -t ${targetSec} -c:a aac -b:a 192k "${outM4a}"`,
  );
  return targetSec;
}

function muxAudio(videoIn, audioIn, outMp4, targetDuration) {
  const target = targetDuration || dur(audioIn);
  const paddedAudio = path.join(OUT_DIR, `_pad-${path.basename(audioIn)}`);
  padAudio(audioIn, target, paddedAudio);
  const trimVid = path.join(OUT_DIR, `_trim-${path.basename(outMp4)}`);
  trimVideo(videoIn, target + 0.15, trimVid);
  run(
    `ffmpeg -y -i "${trimVid}" -i "${paddedAudio}" -map 0:v -map 1:a ` +
      `-c:v libx264 -c:a aac -b:a 192k -t ${target + 0.1} ` +
      `-pix_fmt yuv420p -movflags +faststart "${outMp4}"`,
  );
  return target;
}

async function recordUI(name, fn) {
  const videoDir = path.join(OUT_DIR, "raw");
  await mkdir(videoDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: videoDir, size: { width: 1440, height: 900 } },
  });
  const env = await loadEnv();
  await context.addInitScript((settings) => {
    localStorage.setItem("researchswarm-provider-settings", JSON.stringify(settings));
  }, {
    provider: "openrouter",
    plannerModel: env.PLANNER_MODEL || "qwen/qwen3-32b",
    researchModel: env.RESEARCH_MODEL || "google/gemini-2.5-flash",
    documentModel: env.DOCUMENT_MODEL || "qwen/qwen3-32b",
    answerModel: env.ANSWER_MODEL || "mistralai/mistral-small-3.2-24b-instruct",
    openrouterKey: env.OPENROUTER_API_KEY || "",
  });
  const page = await context.newPage();
  console.log(`  Recording UI: ${name}`);
  await fn(page);
  await page.close();
  await context.close();
  await browser.close();
  const files = await readdir(videoDir);
  const webm = files.find((f) => f.endsWith(".webm"));
  const raw = path.join(OUT_DIR, `ui-${name}.webm`);
  if (webm) {
    const { rename } = await import("fs/promises");
    await rename(path.join(videoDir, webm), raw);
  }
  const mp4 = path.join(OUT_DIR, `ui-${name}.mp4`);
  run(`ffmpeg -y -i "${raw}" -c:v libx264 -pix_fmt yuv420p -r 30 "${mp4}"`);
  return mp4;
}

async function recordAllUI() {
  const landing = await recordUI("landing", async (page) => {
    await page.goto(FRONTEND, { waitUntil: "domcontentloaded" });
    await sleep(3500);
    await page.evaluate(() => window.scrollBy({ top: 400, behavior: "smooth" }));
    await sleep(2500);
  });

  const liveResearch = await recordUI("live-research", async (page) => {
    await page.goto(`${FRONTEND}/app`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("text=What do you want to research today?", { timeout: 20000 });
    await sleep(1200);

    const composer = page.locator("#research-composer");
    await composer.click();
    await composer.fill(LANGGRAPH_QUERY);
    await sleep(1000);
    await page.locator('button[aria-label="Start research"]').click();

    // Keep AI workflow panel in view during execution
    const wf = page.locator("text=AI workflow").first();
    if (await wf.count()) await wf.scrollIntoViewIfNeeded();
    await page.waitForSelector("text=Thinking", { timeout: 15000 }).catch(() => {});
    await sleep(6000);

    // Wait for live agent activity
    await page
      .waitForFunction(
        () => {
          const t = document.body.innerText;
          return t.includes("Planner") || t.includes("Web research") || t.includes("Live");
        },
        { timeout: 30000 },
      )
      .catch(() => {});
    await sleep(8000);

    await sleep(8000);

    // Wait for completed answer — keep workflow visible
    await page
      .waitForFunction(
        () => {
          const t = document.body.innerText;
          return (
            (t.includes("LangGraph") || t.includes("LangChain") || t.includes("StateGraph")) &&
            !t.includes("Thinking...")
          );
        },
        { timeout: 150000 },
      )
      .catch(() => {});

    // Hold on workflow + answer for remainder of scene
    if (await wf.count()) await wf.scrollIntoViewIfNeeded();
    await sleep(6000);
    await page.evaluate(() => {
      for (const el of document.querySelectorAll("*")) {
        if (el.scrollHeight > el.clientHeight + 100) el.scrollTop += 200;
      }
    });
    await sleep(4000);
  });

  const settings = await recordUI("settings", async (page) => {
    await page.goto(`${FRONTEND}/app`, { waitUntil: "domcontentloaded" });
    await sleep(1000);
    await page.getByRole("button", { name: "Settings" }).click();
    await page.waitForSelector("h2:text('Settings')");
    await sleep(1500);
    await page.getByRole("button", { name: "ollama" }).click();
    await sleep(1200);
    await page.getByRole("button", { name: "openrouter" }).click();
    await sleep(2000);
    await page.locator(".fixed.inset-0.z-40").click({ position: { x: 10, y: 10 } });
    await sleep(800);
  });

  return { landing, "live-research": liveResearch, settings };
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const config = JSON.parse(await readFile(path.join(DEMO_DIR, "narration.json"), "utf8"));
  const voice = config.voice || "Daniel";
  const rate = config.rate || 188;

  console.log("Step 1/4 — Narration ...");
  const audioFiles = {};
  for (const scene of config.scenes) {
    const aiff = path.join(OUT_DIR, `${scene.id}.aiff`);
    const m4a = path.join(OUT_DIR, `${scene.id}.m4a`);
    generateNarration(scene.narration, voice, rate, aiff, m4a);
    audioFiles[scene.id] = m4a;
    console.log(`  ${scene.id}: ${dur(m4a).toFixed(1)}s`);
  }

  console.log("Step 2/4 — UI recordings ...");
  const uiVideos = await recordAllUI();

  console.log("Step 3/4 — Assembling ...");
  const segments = [];
  const uiMap = { hook: uiVideos.landing, "live-research": uiVideos["live-research"], settings: uiVideos.settings };

  for (const scene of config.scenes) {
    const segOut = path.join(OUT_DIR, `seg-${scene.id}.mp4`);
    const audio = audioFiles[scene.id];

    if (scene.type === "slide") {
      const slideVid = path.join(OUT_DIR, `slide-${scene.id}-raw.mp4`);
      const slideDur = scene.maxDuration || dur(audio) + 0.3;
      await slideToVideo(scene.slide, slideDur, slideVid);
      muxAudio(slideVid, audio, segOut, scene.maxDuration);
    } else {
      muxAudio(uiMap[scene.id], audio, segOut, scene.maxDuration);
    }
    const segDur = dur(segOut);
    segments.push(segOut);
    console.log(`  ${scene.id}: ${segDur.toFixed(1)}s`);
  }

  console.log("Step 4/4 — Final concat ...");
  const listFile = path.join(OUT_DIR, "concat.txt");
  await writeFile(listFile, segments.map((s) => `file '${s}'`).join("\n"));
  const finalMp4 = path.join(ROOT, "assets", "demo.mp4");
  const finalFull = path.join(ROOT, "assets", "demo-full.mp4");
  run(
    `ffmpeg -y -f concat -safe 0 -i "${listFile}" -c:v libx264 -c:a aac -pix_fmt yuv420p -movflags +faststart "${finalMp4}"`,
  );
  run(`cp "${finalMp4}" "${finalFull}"`);

  const total = dur(finalMp4);
  console.log(`\n✅ ${finalMp4}`);
  console.log(`   ${Math.floor(total / 60)}m ${Math.round(total % 60)}s`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
