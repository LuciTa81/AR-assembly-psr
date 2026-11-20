const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out = __dirname;
const old = JSON.parse(fs.readFileSync(path.join(out, 'visual-provenance-v3.json'), 'utf8'));
const root = path.resolve(path.dirname(old.supervisor.log), '../../..');
const rows = fs.readFileSync(old.supervisor.log, 'utf8').trim().split(/\r?\n/).map(JSON.parse);
const record = rows.find(row => row.current_state === 'S3' && row.target === 'screw_b'
  && row.marker_status === 'OK' && !row.held_reason && row.guidance?.phase === 'GUIDING'
  && !row.guidance.acknowledgement && row.guidance.acknowledgement_remaining_ms === 0);
assert(record, 'No saved B record without acknowledgement');
fs.writeFileSync(path.join(out, 'supervisor-source-record-v7.json'), JSON.stringify(record, null, 2));

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const errors = [];
  let seq = 0;
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 650 }, deviceScaleFactor: 3 });
    page.on('pageerror', error => errors.push(error.message));
    const photo = await sharp(old.unity.photo).jpeg().toBuffer();
    await page.route('http://127.0.0.1:18769/**', async route => {
      const file = new URL(route.request().url()).pathname.slice(1);
      if (file === 'state.json') {
        const state = structuredClone(record);
        state.source = 'session';
        state.frame_age_ms = 0;
        state.frame_id = record.frame_id + seq++;
        state.timestamp_ms = Date.now();
        return route.fulfill({ json: state });
      }
      if (file === 'frame.jpg') return route.fulfill({ body: photo, headers: {
        'Content-Type': 'image/jpeg', 'X-AR-Session': record.session_id, 'X-AR-Source': 'session',
        'X-AR-Frame-Id': String(record.frame_id + seq++), 'X-AR-Timestamp-Ms': String(Date.now()), 'X-AR-Frame-Age-Ms': '0'
      } });
      if (/^fonts\/IBMPlexSansKR-(Regular|Medium|SemiBold|Bold)\.woff2$/.test(file))
        return route.fulfill({ path: path.join(root, 'web_overlay', file), contentType: 'font/woff2' });
      if (!/^supervisor(?:_demo|_shell|_state|_video)?\.(html|css|js)$/.test(file))
        return route.fulfill({ status: 404, body: '' });
      return route.fulfill({ path: path.join(root, 'web_overlay', file), contentType:
        file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'application/javascript' : 'text/html' });
    });
    await page.goto('http://127.0.0.1:18769/supervisor_demo.html');
    await page.waitForFunction(() => document.querySelector('#currentState').textContent === 'S3');
    await page.locator('#videoEnabled').check();
    await page.waitForFunction(() => document.querySelector('#videoImage').naturalWidth > 0);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => !document.querySelector('#acknowledgement').textContent.trim());
    assert.equal(await page.locator('#targetLetter').innerText(), 'B');
    assert.equal(await page.locator('#stateLabel').innerText(), '나사 B');
    assert.equal((await page.locator('#acknowledgement').innerText()).trim(), '');
    assert.match(await page.locator('#actionTitle').innerText(), /나사 B/);
    assert(await page.locator('.topbar').isVisible());
    const box = await page.locator('.workspace').boundingBox();
    const history = await page.locator('.recent-section').boundingBox();
    const clip = { x: 0, y: 0, width: 1100, height: Math.ceil(box.y + box.height + 8) };
    assert(clip.height < history.y, 'History must be outside capture');
    await page.screenshot({ path: path.join(out, 'supervisor-B-header-v7.png'), clip });
    assert.deepEqual(errors, []);
    const result = { record: old.supervisor.log, frame: record.frame_id, state: record.current_state,
      photo: old.unity.photo, clip, errors, acknowledgement: '',
      note: 'Unmodified application UI, actual saved B state with no acknowledgement, separately saved camera photo. Presentation replay, not synchronized footage. Only transport clocks advanced.' };
    fs.writeFileSync(path.join(out, 'visual-provenance-v7.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
