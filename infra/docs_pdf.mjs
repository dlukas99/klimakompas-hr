// `make docs-pdf`: joins the documents into one PDF through headless Chromium (ADR 0007).
import { chromium } from "@playwright/test";
import { Marked } from "marked";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const FILES = [
  "README.md",
  "docs/projekt.md",
  "docs/arhitektura.md",
  "docs/izvori-podataka.md",
  "docs/metodologija.md",
  "docs/preduvjeti.md",
  "docs/kvaliteta-podataka.md",
  "docs/api.md",
  "docs/agent.md",
  "docs/ml.md",
  "docs/pristupacnost.md",
  "docs/korisnicki-vodic.md",
  "docs/daljnji-razvoj.md",
  "docs/deploy.md",
  "docs/alati-i-licence.md",
];
const marked = new Marked();
const renderer = {
  code({ text, lang }) {
    if (lang === "mermaid") return `<pre class="mermaid">${text}</pre>`;
    const safe = text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    return `<pre><code>${safe}</code></pre>`;
  },
};
marked.use({ renderer });

const toc = [];
const sections = FILES.map((file, index) => {
  const raw = readFileSync(join(ROOT, file), "utf-8");
  const title = /^# (.+)$/m.exec(raw)?.[1] ?? file;
  toc.push(`<li><a href="#doc-${index}">${title}</a></li>`);
  const folder = dirname(join(ROOT, file));
  const html = marked
    .parse(raw)
    .replace(/src="(?!https?:)([^"]+)"/g, (_, src) => `src="file://${join(folder, src)}"`);
  return `<section id="doc-${index}" class="doc">${html}</section>`;
}).join("\n");

const page = `<!doctype html><html lang="hr"><head><meta charset="utf-8"><title>KlimaKompas HR</title>
<style>
body{font:11pt/1.45 "Inter Variable",system-ui,sans-serif;color:#0f172a}
.cover{height:90vh;display:flex;flex-direction:column;justify-content:center}
.cover h1{font-size:34pt;margin:0}
.doc{break-before:page}
h1{font-size:20pt}h2{font-size:14pt;margin-top:1.2em}h3{font-size:12pt}
table{border-collapse:collapse;width:100%;font-size:9pt;margin:.6em 0}
td,th{border:1px solid #cbd5e1;padding:3px 5px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
pre{background:#f1f5f9;padding:8px;font-size:9pt;white-space:pre-wrap}
img{max-width:100%;max-height:11cm}
a{color:#0f172a}
</style></head><body>
<div class="cover"><h1>KlimaKompas HR</h1>
<p>Projektna dokumentacija</p>
<p>Tim Požega, FERIT Osijek · Mentor: dr. sc. Matej Džijan</p>
<p>Datathon Portala otvorenih podataka 2026., izazov B – Okoliš i održivi prostor</p></div>
<section class="doc"><h1>Sadržaj</h1><ol>${toc.join("")}</ol></section>
${sections}
<script src="file://${join(ROOT, "frontend/node_modules/mermaid/dist/mermaid.min.js")}"></script>
<script>mermaid.initialize({startOnLoad:true});</script>
</body></html>`;

mkdirSync(join(ROOT, "dist"), { recursive: true });
const htmlPath = join(ROOT, "dist", "dokumentacija.html");
writeFileSync(htmlPath, page);
const browser = await chromium.launch();
const tab = await browser.newPage();
await tab.goto(`file://${htmlPath}`);
await tab.waitForTimeout(3000);
await tab.pdf({
  path: join(ROOT, "dist", "KlimaKompasHR_dokumentacija.pdf"),
  format: "A4",
  margin: { top: "18mm", bottom: "18mm", left: "16mm", right: "16mm" },
  printBackground: true,
});
await browser.close();
