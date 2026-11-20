const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const preview = process.argv.includes('--preview');
const hybrid = preview || process.argv.includes('--hybrid');
const output = path.join(root, preview ? 'outputs/supervisor_usability/rehearsal' : hybrid ? 'outputs/assembly-flow-v1' : 'outputs/operator-v1');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  fs.mkdirSync(output, {recursive: true});
  const server = spawn(process.env.BEAST_PYTHON, ['-X', 'utf8', '-B', '-u', ...(hybrid
    ? ['tests/web/serve_assembly_fixture.py', ...(preview ? ['--preview', '--seconds', '30'] : [])] : [
    'server/realtime/run_realtime_server.py', '--source', 'dummy',
    '--guidance-mode', 'operator', '--port', '0', '--max-frames', '250'])],
    {cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe']});
  const ended = once(server, 'exit');
  let stdout = '', stderr = '', browser;
  server.stdout.on('data', data => stdout += data);
  server.stderr.on('data', data => stderr += data);
  try {
    for (let i = 0; i < 100 && !stdout.includes('overlay=http'); i++) {
      if (server.exitCode !== null) throw new Error(stderr);
      await wait(100);
    }
    const url = stdout.match(/overlay=(http:\/\/127\.0\.0\.1:\d+)/)?.[1];
    assert.ok(url, stdout + stderr);
    browser = await chromium.launch({headless: true});
    const page = await browser.newPage({viewport: {width: 1440, height: 900}});
    const errors = [], requests = [], states = new Set(), progress = new Set();
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => requests.push(r.url()));
    page.on('response', async r => {
      if (r.url().endsWith('/state.json') && r.ok()) {
        try {
          const snapshot = await r.json();
          states.add(snapshot.current_state);
          progress.add(snapshot.guidance?.hold_progress);
        } catch {}
      }
    });
    await page.goto(url + '/supervisor.html');
    await page.waitForFunction(() => document.querySelector('#confirmStep').disabled === false);
    if (!hybrid) assert.match(await page.locator('#sourceKind').innerText(), /더미/);
    assert.equal(requests.some(u => u.includes('frame.jpg')), false);
    if (!hybrid || preview) {
      await page.locator('#videoEnabled').check();
      await page.waitForFunction(() => document.querySelector('#videoImage').naturalWidth > 0);
    }
    for (const revision of hybrid ? [1, 2, 7] : [1, 2, 3, 4, 5, 6, 7]) {
      if (hybrid && revision === 7) {
        assert.equal(await page.locator('#confirmStep').isVisible(), false);
        await page.waitForFunction(() => model.snapshot?.current_state === 'S6' && model.snapshot?.marker_status === 'LOST');
        assert.equal(await page.locator('#status').getAttribute('data-status'), 'AWAITING_CONFIRMATION');
        assert.equal(await page.locator('#confirmStep').isEnabled(), true);
        assert.deepEqual([...states].filter(Boolean), ['S0','S1','S2','S3','S4','S5','S6']);
        await page.setViewportSize({width: 390, height: 844});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        await page.screenshot({path: path.join(output, 'mobile-final.png'), fullPage: true});
      }
      await page.locator('#confirmStep').click();
      await page.waitForFunction(rev => model.snapshot?.extra?.operator?.revision === rev, revision);
      assert.equal(await page.locator('#currentState').innerText(), 'S' + Math.min(revision, 6));
      if (hybrid && revision === 2) {
        assert.equal(await page.locator('#steps li.current span').innerText(), '나사 A');
        assert.equal(await page.locator('#stateLabel').innerText(), '나사 A 작업');
        assert.equal(await page.locator('#operatorResult').innerText(), '');
      }
      if (revision === 2 || revision === 3) {
        await page.setViewportSize(revision === 2 ? {width: 1440, height: 900} : {width: 390, height: 844});
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
        await page.screenshot({path: path.join(output, revision === 2 ? 'desktop.png' : 'mobile.png'), fullPage: true});
      }
    }
    assert.equal(await page.locator('#status').getAttribute('data-status'), 'COMPLETED');
    assert.equal(await page.locator('#confirmStep').isDisabled(), true);
    if (preview) {
      assert.match(await page.locator('#sourceKind').innerText(), /합성/);
      assert(progress.has('retained'), 'Rehearsal must exercise progress retention');
      assert.equal(await page.locator('#videoImage').evaluate(el => el.naturalWidth), 960);
      await wait(1800);
      assert.equal(await page.locator('#status').getAttribute('data-status'), 'COMPLETED');
      await page.screenshot({path: path.join(output, 'completed.png'), fullPage: true});
    }
    const [code] = await ended;
    assert.equal(code, 0, stderr);
    await page.waitForFunction(() => document.querySelector('#status').dataset.status === 'DISCONNECTED');
    assert.equal(await page.locator('#confirmStep').isDisabled(), true);
    assert.deepEqual(errors, []);
    // Image object URLs are in-page buffers, not external network requests.
    assert.deepEqual(requests.filter(u => new URL(u).origin !== url), []);
    const logDir = stdout.match(/log_dir=(.+)/)?.[1].trim();
    if (!hybrid) {
      const rows = fs.readFileSync(path.join(logDir, 'results.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
      assert.equal(rows.filter(r => r.transition_event === 'operator_confirmation').length, 7);
      assert.equal(rows.at(-1).guidance.phase, 'COMPLETED');
      assert.ok(rows.every(r => r.guidance_mode === 'operator'));
      assert.equal(fs.existsSync(path.join(logDir, 'frames')), false);
    }
    const report = {realServer: true, hybrid, preview, cameraUsed: false, confirmations: hybrid ? 3 : 7,
      completed: true, disconnectDisabled: true, pageErrors: errors, logDir};
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally {
    if (server.exitCode === null) server.kill();
    await ended;
    if (browser) await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
