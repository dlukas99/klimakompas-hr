import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const mapCanvas = "canvas.maplibregl-canvas";

test("U1: citizen finds an address and reads the card", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "hr");
  await page.getByRole("combobox").fill("Trg Ante Starčevića 1 Osijek");
  await page.getByRole("option").first().click();
  await expect(page).toHaveURL(/\/iskaznica/);
  await expect(
    page.getByRole("heading", { name: /Trg Ante Starčevića/ }),
  ).toBeVisible();
  await expect(page.getByTestId("hazard-flood")).toBeVisible();
  await expect(page.getByText("Veći je od")).toBeVisible();
  await expect(page.getByText(/Izjava o ograničenju/)).toBeVisible();
});

test("U2: clicking the map opens a card", async ({ page }) => {
  await page.goto("/karta?pogled=45.33000,17.67000,10.00");
  await expect(page.locator(mapCanvas)).toBeVisible();
  await page.waitForResponse(
    (r) => r.url().includes("/tiles/grid_risk/") && r.ok(),
  );
  const box = await page.locator(mapCanvas).boundingBox();
  await page.mouse.click(
    (box?.x ?? 0) + (box?.width ?? 0) / 2,
    (box?.y ?? 0) + (box?.height ?? 0) / 2,
  );
  await expect(page).toHaveURL(/oznaka=/);
  await expect(
    page.getByTestId("card-panel").getByTestId("hazard-air"),
  ).toBeVisible();
});

test("map really draws at full size", async ({ page }) => {
  const jls = page.waitForResponse(
    (r) => r.url().includes("/tiles/jls_risk/") && r.ok(),
  );
  const cells = page.waitForResponse(
    (r) => r.url().includes("/tiles/grid_risk/") && r.ok(),
  );
  await page.goto("/karta?pogled=45.33000,17.67000,9.00");
  await Promise.all([jls, cells]);
  const box = await page.locator(mapCanvas).boundingBox();
  // A zero-height map still counts as "visible", so the size is checked directly.
  const viewport = page.viewportSize();
  expect(box?.width).toBe(viewport?.width);
  expect(box?.height).toBeGreaterThan((viewport?.height ?? 0) * 0.8);
});

test("layer choice is kept in the URL", async ({ page, viewport }) => {
  test.skip((viewport?.width ?? 0) < 768, "the panel starts closed on phones");
  await page.goto("/karta");
  await page.getByRole("radio", { name: /Poplave/ }).click();
  await expect(page).toHaveURL(/sloj=flood/);
  await page.reload();
  await expect(page.getByRole("radio", { name: /Poplave/ })).toBeChecked();
});

test("official flood maps load only from the browser, on request", async ({
  page,
  viewport,
}) => {
  test.skip((viewport?.width ?? 0) < 768, "the panel starts closed on phones");
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("servisi.voda.hr")) requests.push(request.url());
  });
  await page.goto("/karta?pogled=45.33000,17.67000,10.00");
  await page.waitForResponse((r) => r.url().includes("/tiles/grid_risk/"));
  expect(requests).toEqual([]);
  await page.getByRole("checkbox", { name: /Službene karte poplava/ }).click();
  await expect(page.getByText(/ne prikazuju sve scenarije/)).toBeVisible();
  await expect.poll(() => requests.length).toBeGreaterThan(0);
});

test("U3: official compares municipalities and exports data", async ({
  page,
}) => {
  await page.goto("/opcine");
  await page.getByLabel(/Pretraži po nazivu/).fill("pozega");
  await page.getByRole("link", { name: "Požega" }).click();
  await expect(
    page.getByRole("heading", { name: "Požega", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText(/Rang u Hrvatskoj/)).toBeVisible();
  await expect(page.getByRole("cell", { name: "Alaginci" })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /Preuzmi naselja/ }).click();
  expect((await download).suggestedFilename()).toBe("naselja-Požega.csv");
});

test("U5: reviewer sees the status of every source", async ({ page }) => {
  await page.goto("/podaci");
  await expect(
    page.getByRole("heading", { name: "Registar izvora" }),
  ).toBeVisible();
  await expect(page.getByText("Upravne jedinice INSPIRE")).toBeVisible();
  await expect(page.getByText("Samo u pregledniku").first()).toBeVisible();
});

test("U4: quick questions answer without an AI model", async ({ page }) => {
  await page.route("**/api/v1/agent/status", (route) =>
    route.fulfill({ json: { llm_available: false } }),
  );
  await page.goto("/asistent");
  await page.getByRole("button", { name: /upozorenja DHMZ/ }).click();
  await expect(page.getByTestId("quick-answer")).toContainText(/upozorenja/);
  await expect(
    page.getByTestId("quick-answer").getByRole("link").first(),
  ).toBeVisible();
  await page.getByRole("button", { name: /najtoplije/ }).click();
  await expect(
    page.getByText("Najprije odaberite općinu ili grad.").first(),
  ).toBeVisible();
  await page.getByLabel("Općina ili grad", { exact: true }).fill("Požega");
  await page
    .getByRole("option", { name: /Požega/ })
    .first()
    .click();
  await page.getByRole("button", { name: /najtoplije/ }).click();
  await expect(page.getByTestId("quick-answer")).toContainText(
    /toplinskim rizikom/,
  );
});

test("assistant suggests addresses only from the chosen municipality", async ({
  page,
}) => {
  await page.goto("/asistent");
  const place = page.getByLabel(/Adresa ili naselje/);
  await expect(place).toBeDisabled();
  await page.getByLabel("Općina ili grad", { exact: true }).fill("Čaglin");
  await page
    .getByRole("option", { name: /Čaglin/ })
    .first()
    .click();
  await expect(place).toBeEnabled();
  await place.fill("Jasik");
  const options = page.getByRole("option");
  await expect(options.first()).toBeVisible();
  for (const text of await options.allTextContents()) {
    expect(text).toMatch(/Čaglin/);
  }
});

test("free questions work without an AI model", async ({ page }) => {
  await page.route("**/api/v1/agent/status", (route) =>
    route.fulfill({ json: { llm_available: false } }),
  );
  await page.goto("/asistent");
  await expect(page.getByTestId("no-model")).toBeVisible();
  await page.getByLabel("Vaše pitanje").fill("Koliko stanovnika ima Požega?");
  await page.getByRole("button", { name: "Pošalji" }).click();
  // A local model may take several seconds on a shared CPU.
  await expect(page.getByTestId("chat-answer")).toContainText(/22\.294/, {
    timeout: 30_000,
  });
});

test("map panel opens the full card", async ({ page }) => {
  await page.goto(
    "/karta?oznaka=45.35085,17.98695&naziv=%C4%8Caglin&razina=naselje",
  );
  await expect(page.getByTestId("card-panel")).toBeVisible();
  await page.getByRole("link", { name: "Otvori punu iskaznicu" }).click();
  await expect(page).toHaveURL(/\/iskaznica\?.*razina=naselje/);
  await expect(page.getByTestId("card-areas")).toContainText("478");
  // The map's last moveend must not bring the user back to the map.
  await page.waitForTimeout(1000);
  await expect(page).toHaveURL(/\/iskaznica/);
});

test("a searched municipality never says it has no residents", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("combobox").fill("Čaglin");
  await page
    .getByRole("option", { name: /Općina/ })
    .first()
    .click();
  await expect(page.getByTestId("card-population")).toContainText(
    "2.111 stanovnika",
  );
  await expect(page.getByText(/nema stanovnika/)).toHaveCount(0);
});

test("an unknown municipality shows a clear message", async ({ page }) => {
  await page.goto("/opcine/99999");
  await expect(page.getByRole("alert")).toContainText("nije pronađen");
});

test("a point outside Croatia explains itself", async ({ page }) => {
  await page.goto("/iskaznica?lat=42.5&lon=13.5");
  await expect(page.getByRole("alert")).toContainText(
    "izvan područja Hrvatske",
  );
});

test("map keeps its layers when the basemap host is down", async ({ page }) => {
  await page.route("https://tiles.openfreemap.org/**", (route) =>
    route.abort(),
  );
  const cells = page.waitForResponse(
    (r) => r.url().includes("/tiles/jls_risk/") && r.ok(),
  );
  await page.goto("/karta?pogled=45.33000,17.67000,9.00");
  await cells;
  await expect(page.getByText("Podloga karte nije dostupna")).toBeVisible();
});

test("map stays usable when the API is down", async ({ page }) => {
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({ status: 503, body: "" }),
  );
  await page.goto("/karta");
  await expect(page.locator(mapCanvas)).toBeVisible();
  await page.getByRole("combobox").fill("Osijek");
  await expect(page.getByText("Pretraga trenutno nije dostupna")).toBeVisible();
});

for (const path of [
  "/",
  "/karta",
  "/iskaznica?lat=45.56&lon=18.68&naziv=Osijek",
  "/opcine",
  "/opcine/03514",
  "/asistent",
  "/podaci",
  "/o-projektu",
]) {
  test(`axe finds no violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    if (path === "/karta") {
      await expect(page.locator(mapCanvas)).toBeVisible();
      await expect(
        page.getByText("Državne geodetske uprave").first(),
      ).toBeAttached();
    } else {
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByRole("status"))
        .toHaveCount(0, { timeout: 15000 })
        .catch(() => undefined);
    }
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}
