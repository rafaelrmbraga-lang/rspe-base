// Capturas para o guia da APTO SEEU: a tela de extensões do Chrome (Modo do desenvolvedor ligado, com a extensão carregada) e o popup.
// Uso: node ferramentas/apto_seeu/capturas_chrome.js dist/apto_seeu capturas_dir
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path"), os = require("os");
const EXT = path.resolve(process.argv[2]), OUT = path.resolve(process.argv[3]);
const abrir = (vp) => chromium.launchPersistentContext(fs.mkdtempSync(path.join(os.tmpdir(), "apto-guia-")), { headless: true, channel: "chromium",
  viewport: vp, deviceScaleFactor: 2, args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`] });
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  let ctx = await abrir({ width: 1280, height: 760 });
  let pg = ctx.pages()[0];
  await pg.goto("chrome://extensions/");
  await pg.waitForTimeout(1200);
  await pg.evaluate(() => { const t = document.querySelector("extensions-manager").shadowRoot.querySelector("extensions-toolbar").shadowRoot.querySelector("#devMode"); if (!t.checked) t.click(); });
  await pg.waitForTimeout(800);
  await pg.screenshot({ path: path.join(OUT, "ext_2.png") });
  await ctx.close();
  ctx = await abrir({ width: 340, height: 300 });
  const sw = ctx.serviceWorkers()[0] || await ctx.waitForEvent("serviceworker");
  pg = ctx.pages()[0];
  await pg.goto(`chrome-extension://${new URL(sw.url()).host}/popup.html`);
  await pg.waitForTimeout(600);
  await pg.setViewportSize({ width: 340, height: await pg.evaluate(() => document.body.scrollHeight) });
  await pg.screenshot({ path: path.join(OUT, "popup.png") });
  await ctx.close();
})().catch((e) => { console.error(e); process.exit(1); });
