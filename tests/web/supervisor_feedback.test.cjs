const { test } = require('node:test');
const assert = require('node:assert/strict');
const { supervisorFeedback, FramePreviewState } = require('../../web_overlay/supervisor_state.js');

function view(status = 'GUIDING', patch = {}) {
  return { status, snapshot: {
    current_state: 'S2', marker_status: 'OK', marker_count: 4,
    guidance: { phase: status, reason: '' },
    extra: { yolo_reason: 'ok', driver_count: 1, tool_tip_source: 2 },
    ...patch,
  } };
}

test('feedback follows server phases; observed means withdrawal pending, not complete', () => {
  assert.equal(typeof supervisorFeedback, 'function');
  assert.equal(supervisorFeedback(view()).stage, 0);
  assert.equal(supervisorFeedback(view('OBSERVING')).stage, 1);
  const observed = supervisorFeedback(view('OBSERVED'));
  assert.equal(observed.stage, 2);
  assert.match(observed.title, /이탈/);
  assert.match(observed.detail, /작업.*끝.*드라이버/);
  assert.equal(supervisorFeedback(view('AWAITING_CONFIRMATION', { current_state: 'S6' })).stage, null);
});

test('tracking loss explains capture separately and invalidates driver evidence', () => {
  assert.equal(typeof supervisorFeedback, 'function');
  const result = supervisorFeedback(view('TRACKING_LOST', { marker_status: 'LOST', marker_count: 3 }));
  assert.match(result.title, /마커/);
  assert.match(result.detail, /카메라/);
  assert.equal(result.stage, null);
  assert.equal(result.driver, '판정 보류');
});

test('duplicate drivers are not described as no driver; missing diagnostics stay unknown', () => {
  assert.equal(typeof supervisorFeedback, 'function');
  const v = view('PAUSED', { guidance: { reason: 'tool_not_visible' },
    extra: { yolo_reason: 'ok', driver_count: 2 } });
  assert.match(supervisorFeedback(v).title, /복수/);
  assert.match(supervisorFeedback(v).driver, /2/);
  assert.equal(supervisorFeedback(view('GUIDING', { extra: {} })).driver, '정보 없음');
  assert.equal(supervisorFeedback(view('GUIDING', { extra: { yolo_reason: 'stale', driver_count: 0 } })).driver, '판정 보류');
});

test('explicit multiple-candidate reason remains blocked with recheck guidance', () => {
  const v = view('PAUSED', { guidance: { reason: 'multiple_tool_candidates' },
    extra: { yolo_reason: 'ok', driver_count: 2 } });
  const result = supervisorFeedback(v);
  assert.match(result.title, /복수/);
  assert.match(result.detail, /다시 확인/);
  assert.equal(result.stage, null);
});

test('disconnect and stale views never display old driver evidence as current', () => {
  assert.equal(typeof supervisorFeedback, 'function');
  for (const status of ['DISCONNECTED', 'STALE', 'INVALID_DATA', 'WAITING']) {
    const result = supervisorFeedback(view(status));
    assert.equal(result.stage, null);
    assert.equal(result.driver, '판정 보류');
  }
});

const image = (patch = {}) => ({ session: 's', frame: 1, timestamp: 1000, age: 0, source: 'camera', ...patch });
test('video freshness is independent, includes RTT, and duplicate frames cannot renew it', () => {
  assert.equal(typeof FramePreviewState, 'function');
  const state = new FramePreviewState();
  assert.equal(state.apply(image({ age: 200 }), 0, 100), true);
  assert.equal(state.view(1299).status, 'LIVE');
  assert.equal(state.view(1300).status, 'STALE');
  assert.equal(state.apply(image(), 1400, 1400), false);
  assert.equal(state.view(1400).status, 'STALE');
});

test('video rejects missing metadata and reversed frames, and accepts new sessions', () => {
  assert.equal(typeof FramePreviewState, 'function');
  const state = new FramePreviewState();
  assert.equal(state.apply(image({ frame: 4 }), 0, 0), true);
  assert.equal(state.apply(image({ frame: 3 }), 10, 10), false);
  assert.equal(state.view(10).status, 'INVALID');
  assert.equal(state.apply(image({ session: 'next' }), 20, 20), true);
  assert.equal(state.view(20).status, 'LIVE');
  for (const patch of [{ age: null }, { timestamp: -1 }, { frame: 0 }, { session: '' }]) {
    assert.equal(state.apply(image(patch), 30, 30), false);
  }
});
