import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("home page searches and opens the map", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "hr");
  await page.getByRole("combobox").fill("Požega");
  await page
    .getByRole("option")
    .filter({ hasText: "Grad, Požeško-slavonska" })
    .click();
  await expect(page).toHaveURL(/\/karta/);
  await expect(page.getByTestId("map").locator("canvas")).toBeVisible();
});

test("map loads JLS and population tiles", async ({ page }) => {
  const jls = page.waitForResponse(
    (r) => r.url().includes("/tiles/jls/") && r.ok(),
  );
  const cells = page.waitForResponse(
    (r) => r.url().includes("/tiles/grid_pop/") && r.ok(),
  );
  await page.goto("/karta?pogled=45.33000,17.67000,9.00");
  await Promise.all([jls, cells]);
  const box = await page.getByTestId("map").locator("canvas").boundingBox();
  // A zero-height map still counts as "visible", so the size is checked directly.
  const viewport = page.viewportSize();
  expect(box?.width).toBe(viewport?.width);
  expect(box?.height).toBeGreaterThan((viewport?.height ?? 0) * 0.8);
});

test("layer choice is kept in the URL", async ({
  page,
  isMobile,
  viewport,
}) => {
  test.skip(
    isMobile || (viewport?.width ?? 0) < 768,
    "the panel starts closed on phones",
  );
  await page.goto("/karta");
  await page.getByRole("checkbox", { name: /Stanovništvo/ }).click();
  await expect(page).toHaveURL(/slojevi=jls/);
  await page.reload();
  await expect(
    page.getByRole("checkbox", { name: /Stanovništvo/ }),
  ).not.toBeChecked();
});

test("an address search returns a pin on the map", async ({ page }) => {
  await page.goto("/karta");
  await page.getByRole("combobox").fill("Trg Ante Starčevića 1 Osijek");
  await page.getByRole("option").first().click();
  await expect(page).toHaveURL(/oznaka=/);
  await expect(page.getByLabel("Odabrana lokacija")).toBeVisible();
});

test("map keeps its layers when the basemap host is down", async ({ page }) => {
  await page.route("https://tiles.openfreemap.org/**", (route) =>
    route.abort(),
  );
  const jls = page.waitForResponse(
    (r) => r.url().includes("/tiles/jls/") && r.ok(),
  );
  await page.goto("/karta?pogled=45.33000,17.67000,9.00");
  await jls;
  await expect(page.getByText("Podloga karte nije dostupna")).toBeVisible();
});

test("map stays usable when the API is down", async ({ page }) => {
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({ status: 503, body: "" }),
  );
  await page.goto("/karta");
  await expect(page.getByTestId("map").locator("canvas")).toBeVisible();
  await page.getByRole("combobox").fill("Osijek");
  await expect(page.getByText("Pretraga trenutno nije dostupna")).toBeVisible();
});

for (const path of ["/", "/karta"]) {
  test(`axe finds no violations on ${path}`, async ({ page }) => {
    await page.goto(path);
    if (path === "/karta") {
      await expect(page.getByTestId("map").locator("canvas")).toBeVisible();
      await expect(
        page.getByText("Državne geodetske uprave").first(),
      ).toBeAttached();
    }
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}
