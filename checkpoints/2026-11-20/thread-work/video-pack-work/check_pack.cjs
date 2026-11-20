const { chromium } = require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1111-574-0_26.1111.574.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
const { pathToFileURL } = require('node:url');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const pack = 'C:/Users/fresh/OneDrive/Desktop/AI_Assembly_Video_Pack_20261115';
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(pathToFileURL(path.join(pack, '자료_미리보기.html')).href);
    const images = await page.locator('img').evaluateAll(async nodes => {
      for (const img of nodes) {
        img.loading = 'eager';
        await img.decode().catch(() => {});
      }
      return nodes.map(img => ({file: img.alt, width: img.naturalWidth, height: img.naturalHeight, loaded: img.complete && img.naturalWidth > 0}));
    });
    await page.waitForFunction(() => document.querySelector('video').readyState >= 1);
    const video = await page.locator('video').evaluate(v => ({width: v.videoWidth, height: v.videoHeight, duration: v.duration, ready: v.readyState}));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    await page.screenshot({path: path.join(__dirname, 'pack-preview-desktop.png')});
    await page.setViewportSize({width: 390, height: 844});
    const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    const result = {images, video, errors, desktopOverflow: overflow, mobileOverflow};
    fs.writeFileSync(path.join(__dirname, 'pack-check.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
    if (images.some(i => !i.loaded) || errors.length || overflow || mobileOverflow) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch(e => {console.error(e); process.exitCode = 1;});
