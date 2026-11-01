// usage: node render.mjs <view> <w> <h> <out.png>
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
import http from 'http';
import fs from 'fs';
import path from 'path';

const [view = 'street', w = '1600', h = '1067', out = `out_${view}.png`] = process.argv.slice(2);
const root = path.dirname(new URL(import.meta.url).pathname);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-watchdog', '--max-active-webgl-contexts=4'] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.type(), m.text().slice(0, 300)); });
page.on('pageerror', e => console.log('[pageerror]', e.message));
const t0 = Date.now();
await page.goto(`http://localhost:${port}/index.html?view=${view}&w=${w}&h=${h}${process.env.EXTRA || ""}`);
console.log(await page.evaluate(() => { const c = document.createElement("canvas").getContext("webgl2"); return "maxTex " + c.getParameter(c.MAX_TEXTURE_SIZE) + " " + c.getParameter(c.getExtension("WEBGL_debug_renderer_info")?.UNMASKED_RENDERER_WEBGL || c.RENDERER); }));
await page.waitForFunction(() => window.__done || window.__err, null, { timeout: 0, polling: 1000 });
const err = await page.evaluate(() => window.__err);
if (err) console.log('ERR', err);
const data = await page.evaluate(() => document.querySelector('canvas').toDataURL('image/png'));
fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
console.log(`rendered ${view} ${w}x${h} -> ${out} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
await browser.close(); server.close();
