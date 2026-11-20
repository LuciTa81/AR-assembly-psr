// Synthetic loopback-only UI regression. No camera or stored user images.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'outputs/supervisor_pose');
const assets = {
  '/supervisor.html': 'text/html', '/supervisor.css': 'text/css',
  '/supervisor.js': 'text/javascript', '/supervisor_state.js': 'text/javascript',
  '/supervisor_video.js': 'text/javascript',
};
let scenario = 'marker_geometry', frame = 0;
function snapshot() {
  const id = ++frame, tracking = scenario === 'tracking';
  return {
    schema_version: 'realtime_v1', session_id: 'synthetic-pose-feedback', source: 'synthetic',
    system_status: 'RUNNING', frame_id: id, timestamp_ms: Date.now(), frame_age_ms: scenario === 'stale' ? 220 : 0,
    marker_status: 'OK', marker_count: 4, current_state: 'S2',
    current_label: 'Lid closed', target: 'screw_a', next_action: 'Fasten screw A',
    guidance: { schema_version: 'assembly_guidance_v1', phase: 'GUIDING', reason: '',
      acknowledgement: '', acknowledgement_remaining_ms: 0 },
    extra: { presentation_overlay: 1, presentation_pose: tracking ? 'tracking' : 'pose_rejected',
      presentation_diagnostics: { frame_id: id, analysis_status: tracking ? 'tracking' : 'pose_rejected',
        reason_code: scenario } },
  };
}
(async () => {
  const server = http.createServer((req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    if (req.url === '/state.json') {
      if (scenario === 'disconnected') { res.writeHead(503).end(); return; }
      res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify(snapshot())); return;
    }
    if (!assets[req.url]) { res.writeHead(404).end(); return; }
    res.setHeader('Content-Type', assets[req.url] + '; charset=utf-8');
    res.end(fs.readFileSync(path.join(root, 'web_overlay', req.url.slice(1))));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [], requests = [], checked = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => requests.push(request.url()));
    const url = 'http://127.0.0.1:' + server.address().port;
    fs.mkdirSync(output, { recursive: true });
    await page.goto(url + '/supervisor.html');
    const cases = {
      marker_geometry: '배치 조건 부족', insufficient_markers: '등록 마커 부족',
      solver_failed: '위치 계산 실패', pose_quality: '위치 계산 불확실',
      target_outside: '시야 밖', stale: '위치 갱신 지연',
      disconnected: '서버 연결 끊김', tracking: '카메라 위치 추적 중',
    };
    for (const [name, viewport] of [['desktop', { width: 1440, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
      await page.setViewportSize(viewport);
      for (const [code, label] of Object.entries(cases)) {
        scenario = code;
        await page.waitForFunction(text => document.querySelector('#poseFeedback').textContent.includes(text), label);
        const ui = await page.evaluate(() => {
          const pose = document.querySelector('#poseFeedback'), feedback = document.querySelector('#feedback');
          const a = pose.getBoundingClientRect(), b = feedback.getBoundingClientRect();
          return { state: document.querySelector('#currentState').textContent,
            instruction: document.querySelector('#instruction').textContent,
            noOverflow: document.documentElement.scrollWidth <= innerWidth,
            fits: pose.scrollHeight <= pose.clientHeight && pose.scrollWidth <= pose.clientWidth,
            noOverlap: a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top };
        });
        assert.equal(ui.state, 'S2');
        if (code !== 'disconnected') assert.equal(ui.instruction, 'Fasten screw A');
        assert.ok(ui.noOverflow && ui.fits && ui.noOverlap, JSON.stringify(ui));
        if (['marker_geometry', 'tracking', 'disconnected'].includes(code))
          await page.screenshot({ path: path.join(output, name + '-' + code + '.png'), fullPage: true });
        checked.push(name + ':' + code);
      }
    }
    assert.deepEqual(errors, []);
    assert.ok(requests.every(request => request.startsWith(url + '/')));
    assert.ok(!requests.some(request => request.includes('frame.jpg')));
    const report = { checked, pageErrors: errors, cameraOpened: false, loopbackOnly: true };
    fs.writeFileSync(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
