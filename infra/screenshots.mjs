// `make screenshots`: pages on desktop and phone for the documentation and the submission.
import { chromium } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:5173";
const OUT = new URL("../docs/images/", import.meta.url).pathname;
const PAGES = [
  ["pocetna", "/"],
  ["karta", "/karta?pogled=45.60000,16.20000,7.20"],
  ["iskaznica", "/iskaznica?lat=45.555&lon=18.69&naziv=Osijek"],
  ["jls", "/opcine/03123"],
  ["asistent", "/asistent"],
  ["podaci", "/podaci"],
];
const SIZES = [
  ["desktop", 1280, 900],
  ["mobitel", 360, 740],
];

const browser = await chromium.launch({
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
for (const [sizeName, width, height] of SIZES) {
  const context = await browser.newContext({ viewport: { width, height } });
  const page = await context.newPage();
  for (const [name, path] of PAGES) {
    await page.goto(BASE + path);
    await page.waitForTimeout(6000);
    await page.screenshot({ path: `${OUT}${name}-${sizeName}.png` });
  }
  await context.close();
}
await browser.close();
