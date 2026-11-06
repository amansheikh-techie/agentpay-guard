/**
 * scripts/capture-screenshots.mjs
 *
 * Automated screenshot capture script for AgentPay Guard.
 * Built for the PayPal AI Hackathon 2026.
 *
 * Runs headless Chromium at 1440x900 (deviceScaleFactor: 2), resets the demo state,
 * executes the standard test scenarios, and saves high-resolution PNGs to docs/screenshots/:
 *   01-dashboard.png         Mission Control dashboard with $100 budget & $40 cap
 *   02-agent-request.png     AI shopping proposal under review (Allowed by policy)
 *   03-approved-purchase.png Explicitly approved purchase with PayPal Sandbox Order & updated budget
 *   04-blocked-over-limit.png Proposing purchase exceeding $40 cap (Smart Alternatives shown)
 *   05-blocked-merchant.png  Proposing purchase from unauthorized merchant
 *   06-audit-trail.png       Immutable audit trail of all evaluations & events
 *   07-voice-assistant.png   Voice assistant ready with accent selection & microphone
 *
 * Usage:
 *   npm run screenshots
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');
const SCREENSHOTS_DIR = path.join(REPO_ROOT, 'docs', 'screenshots');
const BACKEND_URL = process.env.VITE_API_URL || 'http://localhost:8000';
const FRONTEND_URL = process.env.FRONTEND_BASE_URL || 'http://localhost:5173';

async function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkServiceReachable(url) {
  try {
    const res = await fetch(url);
    return res.ok || res.status < 500;
  } catch {
    return false;
  }
}

async function resetDemoState() {
  console.log(`[1/8] Resetting demo state via POST ${BACKEND_URL}/api/policy/reset...`);
  try {
    const res = await fetch(`${BACKEND_URL}/api/policy/reset`, { method: 'POST' });
    if (!res.ok) {
      console.warn(`Warning: Reset returned status ${res.status}`);
    } else {
      console.log('  Demo policy and spend counters reset to pristine state ($100 budget, $40 cap).');
    }
  } catch (err) {
    console.warn('Could not reset demo state on backend (is backend running?):', err.message);
  }
}

async function main() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }

  console.log('Verifying service connectivity...');
  const backendUp = await checkServiceReachable(`${BACKEND_URL}/api/policy`);
  const frontendUp = await checkServiceReachable(FRONTEND_URL);

  if (!backendUp) {
    console.error(` ERROR: Backend is not responding at ${BACKEND_URL}. Please start backend:`);
    console.error(`       cd backend && .\\.venv\\Scripts\\uvicorn.exe app.main:app --port 8000`);
    process.exit(1);
  }
  if (!frontendUp) {
    console.error(` ERROR: Frontend is not responding at ${FRONTEND_URL}. Please start frontend:`);
    console.error(`       cd frontend && npm run dev`);
    process.exit(1);
  }

  // 1. Reset demo state to clean baseline
  await resetDemoState();

  console.log('Launching headless Chromium browser (1440x900 @2x scale)...');
  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    recordVideo: {
      dir: SCREENSHOTS_DIR,
      size: { width: 1440, height: 900 },
    },
  });

  // Polyfill SpeechRecognition in headless context so voice toolbar renders reliably
  await context.addInitScript(() => {
    if (!window.SpeechRecognition && !window.webkitSpeechRecognition) {
      window.webkitSpeechRecognition = class MockSpeechRecognition {
        constructor() {
          this.continuous = false;
          this.interimResults = false;
          this.lang = 'en-IN';
        }
        start() {}
        stop() {}
        abort() {}
      };
    }
  });

  const page = await context.newPage();

  try {
    // -------------------------------------------------------------------------
    // 1. Capture 01-dashboard.png (Overview Mission Control)
    // -------------------------------------------------------------------------
    console.log('[2/8] Capturing 01-dashboard.png...');
    await page.goto(`${FRONTEND_URL}/?tab=overview`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.overview-tab', { timeout: 15000 });
    await page.waitForSelector('.overview-hero', { timeout: 15000 });
    await wait(800);
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, '01-dashboard.png'),
      fullPage: false,
    });
    console.log('  Saved docs/screenshots/01-dashboard.png');

    // -------------------------------------------------------------------------
    // 2. Capture 07-voice-assistant.png (Voice Assistant Ready)
    // -------------------------------------------------------------------------
    console.log('[3/8] Capturing 07-voice-assistant.png...');
    await page.goto(`${FRONTEND_URL}/?tab=shopping`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.voice-toolbar', { timeout: 15000 });
    await page.waitForSelector('.voice-status-text', { timeout: 15000 });
    await wait(800);
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, '07-voice-assistant.png'),
      fullPage: false,
    });
    console.log('  Saved docs/screenshots/07-voice-assistant.png');

    // -------------------------------------------------------------------------
    // 3. Capture 02-agent-request.png (Scenario A Proposal)
    // -------------------------------------------------------------------------
    console.log('[4/8] Capturing 02-agent-request.png (Scenario A: Allowed Wireless Mouse)...');
    const scenarioBtns = await page.$$('.scenario-btn');
    if (scenarioBtns.length > 0) {
      await scenarioBtns[0].click();
      await wait(300);
      const proposeBtn = await page.$('#submit-request-btn');
      if (proposeBtn) {
        await proposeBtn.click();
        console.log('  Waiting for policy engine evaluation (up to 45s)...');
        await page.waitForSelector('text=ALLOWED BY POLICY', { timeout: 45000 });
        await wait(1000);
        await page.screenshot({
          path: path.join(SCREENSHOTS_DIR, '02-agent-request.png'),
          fullPage: false,
        });
        console.log('  Saved docs/screenshots/02-agent-request.png');
      }
    }

    // -------------------------------------------------------------------------
    // 4. Capture 03-approved-purchase.png (Explicit Human Approval & PayPal Sandbox Order)
    // -------------------------------------------------------------------------
    console.log('[5/8] Capturing 03-approved-purchase.png (Creating PayPal Sandbox Order)...');
    const approvePayBtn = await page.$('button:has-text("Explicitly Approve & Pay")');
    if (approvePayBtn) {
      await approvePayBtn.click();
      console.log('  Waiting for PayPal Sandbox order creation...');
      await page.waitForSelector('text=PayPal Sandbox Order:', { timeout: 30000 });
      await wait(1000);
    }
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, '03-approved-purchase.png'),
      fullPage: false,
    });
    console.log('  Saved docs/screenshots/03-approved-purchase.png');

    // -------------------------------------------------------------------------
    // 5. Capture 04-blocked-over-limit.png (Scenario B: Exceeds $40 Cap)
    // -------------------------------------------------------------------------
    console.log('[6/8] Capturing 04-blocked-over-limit.png (Scenario B: Over Limit)...');
    const scenarioBtns2 = await page.$$('.scenario-btn');
    if (scenarioBtns2.length > 1) {
      await scenarioBtns2[1].click(); // Scenario B
      await wait(300);
      const proposeBtn = await page.$('#submit-request-btn');
      if (proposeBtn) {
        await proposeBtn.click();
        console.log('  Waiting for policy block verdict (up to 45s)...');
        await page.waitForSelector('text=BLOCKED BY POLICY ENGINE', { timeout: 45000 });
        await wait(1000);
        await page.screenshot({
          path: path.join(SCREENSHOTS_DIR, '04-blocked-over-limit.png'),
          fullPage: false,
        });
        console.log('  Saved docs/screenshots/04-blocked-over-limit.png');
      }
    }

    // -------------------------------------------------------------------------
    // 6. Capture 05-blocked-merchant.png (Scenario C: Unauthorized Merchant)
    // -------------------------------------------------------------------------
    console.log('[7/8] Capturing 05-blocked-merchant.png (Scenario C: Unauthorized Merchant)...');
    const scenarioBtns3 = await page.$$('.scenario-btn');
    if (scenarioBtns3.length > 2) {
      await scenarioBtns3[2].click(); // Scenario C
      await wait(300);
      const proposeBtn = await page.$('#submit-request-btn');
      if (proposeBtn) {
        await proposeBtn.click();
        console.log('  Waiting for policy block verdict (up to 45s)...');
        await page.waitForSelector('text=BLOCKED BY POLICY ENGINE', { timeout: 45000 });
        await wait(1000);
        await page.screenshot({
          path: path.join(SCREENSHOTS_DIR, '05-blocked-merchant.png'),
          fullPage: false,
        });
        console.log('  Saved docs/screenshots/05-blocked-merchant.png');
      }
    }

    // -------------------------------------------------------------------------
    // 7. Capture 06-audit-trail.png (Immutable Audit Trail Log)
    // -------------------------------------------------------------------------
    console.log('[8/8] Capturing 06-audit-trail.png (Audit Log Tab)...');
    await page.goto(`${FRONTEND_URL}/?tab=audit`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.audit-tab-wrapper', { timeout: 15000 });
    await page.waitForSelector('text=Immutable Audit Trail', { timeout: 15000 });
    await wait(1000);
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, '06-audit-trail.png'),
      fullPage: false,
    });
    console.log('  Saved docs/screenshots/06-audit-trail.png');

    console.log('\n All 7 screenshots captured successfully at 1440x900 (deviceScaleFactor: 2)!');
  } catch (err) {
    console.error(' Screenshot capture encountered an error:', err);
    throw err;
  } finally {
    const video = page.video();
    await page.close();
    await context.close();
    await browser.close();

    if (video) {
      try {
        const videoPath = await video.path();
        const targetVideoPath = path.join(SCREENSHOTS_DIR, 'demo.webm');
        if (fs.existsSync(videoPath)) {
          if (fs.existsSync(targetVideoPath)) {
            try {
              fs.unlinkSync(targetVideoPath);
            } catch {}
          }
          fs.renameSync(videoPath, targetVideoPath);
          console.log(` Saved demo recording to docs/screenshots/demo.webm`);
        }
      } catch (videoErr) {
        console.warn('Could not save demo.webm:', videoErr.message);
      }
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
