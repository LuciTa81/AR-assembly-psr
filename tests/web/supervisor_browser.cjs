// Use an installed Playwright module via PLAYWRIGHT_MODULE; no package install is needed.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'outputs/supervisor_r6');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  // Do not replace an existing runtime on Unity's fixed local port.
  try { await fetch('http://127.0.0.1:8765/state.json'); throw new Error('Port 8765 already in use'); }
  catch (error) { if (error.message === 'Port 8765 already in use') throw error; }
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [], requests = [], observed = new Set(), states = new Set();
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => requests.push(request.url()));
  const server = spawn(process.env.BEAST_PYTHON, ['-X', 'utf8', '-B', 'tests/unity/serve_snapshot_fixture.py', '--guidance'],
    { cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let stderr = '';
  server.stderr.on('data', data => { stderr += data; });
  const ended = once(server, 'exit');
  try {
    for (let attempt = 0; attempt < 100; attempt++) {
      try { if ((await fetch('http://127.0.0.1:8765/state.json')).ok) break; } catch {}
      await wait(100);
    }
    await page.goto('http://127.0.0.1:8765/supervisor.html');
    const started = Date.now();
    let desktop = false, mobile = false, end = false;
    while (Date.now() - started < 27000) {
      const ui = await page.evaluate(() => ({
        status: document.querySelector('#status').dataset.status,
        state: document.querySelector('#currentState').textContent,
        source: document.querySelector('#sourceKind').textContent,
        overflow: document.documentElement.scrollWidth > innerWidth,
        activeSteps: document.querySelectorAll('#steps [aria-current="step"]').length,
      }));
      observed.add(ui.status); states.add(ui.state);
      assert.equal(ui.overflow, false);
      assert.ok(ui.activeSteps <= 1);
      if (!desktop && ui.status === 'OBSERVED') {
        await page.screenshot({ path: path.join(output, 'supervisor-desktop.png'), fullPage: true });
        desktop = true;
        await page.setViewportSize({ width: 390, height: 844 });
      } else if (desktop && !mobile && ui.state === 'S3') {
        await page.screenshot({ path: path.join(output, 'supervisor-mobile.png'), fullPage: true });
        mobile = true;
        await page.setViewportSize({ width: 1440, height: 900 });
      }
      if (!end && ui.status === 'AWAITING_CONFIRMATION') {
        await page.screenshot({ path: path.join(output, 'supervisor-confirmation.png'), fullPage: true });
        end = true;
      }
      await wait(100);
    }
    for (const status of ['GUIDING', 'OBSERVING', 'OBSERVED', 'PAUSED', 'TRACKING_LOST', 'AWAITING_CONFIRMATION', 'DISCONNECTED']) {
      assert.ok(observed.has(status), `missing status ${status}: ${[...observed]}`);
    }
    for (let i = 0; i <= 6; i++) assert.ok(states.has('S' + i), `missing S${i}`);
    assert.deepEqual(errors, []);
    assert.equal(requests.some(url => !url.startsWith('http://127.0.0.1:8765/')), false);
    assert.equal(requests.some(url => url.includes('frame.jpg')), false);
    assert.ok(desktop && mobile && end);
    await page.screenshot({ path: path.join(output, 'supervisor-disconnected.png'), fullPage: true });
    const [code] = await ended;
    assert.equal(code, 0, stderr);
    const report = { statuses: [...observed], states: [...states], pageErrors: errors, noVideoRequests: true, loopbackOnly: true };
    fs.writeFileSync(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally {
    if (server.exitCode === null) server.kill();
    await ended;
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
