const { chromium } = require("playwright");
const fs = require("node:fs");
const baseUrl = process.env.BROWSER_URL || "http://localhost:8000";
const apiKey = process.env.BROWSER_API_KEY;
if (!apiKey)
  throw new Error("Set BROWSER_API_KEY to a north-tenant fixture API key.");
fs.mkdirSync("work", { recursive: true });
const assert = require("node:assert/strict");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1512, height: 1100 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(baseUrl);
  await page.screenshot({ path: "work/dashboard-initial.png", fullPage: true });
  assert(
    await page.getByRole("button", { name: "Run comparison" }).isDisabled(),
  );
  await page.locator("#api-key").fill("wrong-key");
  await page.locator("#connect-button").click();
  await page
    .getByRole("status")
    .filter({ hasText: "Authentication failed" })
    .waitFor();
  await page.locator("#api-key").fill(apiKey);
  await page.locator("#connect-button").click();
  await page.locator("#environment.connected").waitFor();
  assert.equal(await page.locator("#api-key").inputValue(), "");
  await page.locator("#run-button").click();
  await page
    .locator("#run-caption")
    .filter({ hasText: "Completed:" })
    .waitFor();
  assert.equal(await page.locator(".badge.success").count(), 3);
  assert.equal(
    await page.locator("#result-baseline .result-value").textContent(),
    "300",
  );
  assert.equal(
    await page.locator("#result-semantic .result-value").textContent(),
    "60",
  );
  assert.equal(
    await page.locator("#result-vkg .result-value").textContent(),
    "60",
  );
  await page
    .locator("#result-semantic")
    .getByRole("tab", { name: "Context" })
    .click();
  assert.equal(
    await page.locator("#result-semantic .context-chunk").count(),
    3,
  );
  await page
    .locator("#result-vkg")
    .getByRole("tab", { name: "Pipeline" })
    .click();
  assert.equal(await page.locator("#result-vkg .pipeline li").count(), 3);
  const downloadPromise = page.waitForEvent("download");
  await page.locator("#export-button").click();
  const artifact = await downloadPromise;
  await artifact.saveAs("work/browser-export.json");
  const exported = fs.readFileSync("work/browser-export.json", "utf8");
  assert(!exported.includes(apiKey));
  assert.equal(Object.keys(JSON.parse(exported).results).length, 3);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "work/dashboard-desktop.png", fullPage: true });
  await page
    .locator(".examples button")
    .filter({ hasText: "Conversion rate" })
    .click();
  await page.locator("#run-button").click();
  await page
    .locator("#run-caption")
    .filter({ hasText: "Completed:" })
    .waitFor();
  assert.equal(
    await page.locator("#result-semantic .result-value").textContent(),
    "15%",
  );
  await page.locator("#question").fill("List customer emails");
  await page.locator("#run-button").click();
  await page
    .locator("#run-caption")
    .filter({ hasText: "Completed:" })
    .waitFor();
  assert.equal(await page.locator(".badge.error").count(), 3);
  // A dependency failure in one approach must not discard the other results.
  await page.locator("#question").fill("How many eligible customers?");
  await page.route("**/v1/query", (route) => {
    if (route.request().postDataJSON().mode === "vkg")
      return route.fulfill({
        status: 503,
        contentType: "application/json",
        body: '{"detail":"dependency unavailable"}',
      });
    return route.continue();
  });
  await page.locator("#run-button").click();
  await page
    .locator("#run-caption")
    .filter({ hasText: "Completed:" })
    .waitFor();
  assert.equal(await page.locator(".badge.success").count(), 2);
  assert.equal(await page.locator(".badge.error").count(), 1);
  await page.unroute("**/v1/query");
  // A single-mode run works independently of the comparison view.
  await page.locator("#select-all").click();
  await page.locator("input[value=semantic]").check();
  await page.locator("#question").fill("How many conversions?");
  await page.locator("#run-button").click();
  await page
    .locator("#run-caption")
    .filter({ hasText: "Completed:" })
    .waitFor();
  assert.equal(await page.locator(".result-card").count(), 1);
  assert.equal(await page.locator(".result-value").textContent(), "9");
  // No browser storage contains credentials.
  assert.equal(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
    0,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "work/dashboard-mobile.png", fullPage: true });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  );
  assert.deepEqual(errors, []);
  console.log(
    "Browser checks passed: auth, three real modes, context/pipeline, JSON export, rate, denials, single mode, memory-only credentials, responsive layout.",
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
