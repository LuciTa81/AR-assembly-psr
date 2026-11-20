'use strict';

// A separate Chrome window: no personal browser profile, screenshots or recordings.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({
    channel: 'chrome', headless: false,
    args: ['--window-position=30,30', '--window-size=1440,900'],
  });
  try {
    const context = await browser.newContext({ viewport: null });
    const page = await context.newPage();
    await page.goto('http://127.0.0.1:8765/supervisor.html');
    await page.locator('#videoEnabled').check();
    await page.bringToFront();
    console.log('Chrome supervisor ready: http://127.0.0.1:8765/supervisor.html');
    page.on('close', () => browser.close().catch(() => {}));
    await new Promise(resolve => browser.on('disconnected', resolve));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
