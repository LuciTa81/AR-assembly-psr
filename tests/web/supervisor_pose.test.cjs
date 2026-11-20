const { test } = require('node:test');
const assert = require('node:assert/strict');
const { supervisorPoseFeedback, supervisorFeedback } = require('../../web_overlay/supervisor_state.js');

function view(code = 'marker_geometry', status = 'GUIDING') {
  return { status, ageMs: 25, snapshot: {
    frame_id: 8, current_state: 'S2', guidance: { phase: 'GUIDING', reason: '' },
    extra: { presentation_overlay: 1, presentation_pose: 'pose_rejected',
      presentation_diagnostics: { frame_id: 8, analysis_status: 'pose_rejected',
        reason_code: code, publish_age_ms: 20 } },
  } };
}
test('position feedback is separate from assembly instructions and has bounded reason labels', () => {
  assert.equal(typeof supervisorPoseFeedback, 'function');
  const v = view();
  assert.match(supervisorPoseFeedback(v), /배치/);
  assert.equal(supervisorFeedback(v).stage, 0);
  assert.match(supervisorPoseFeedback(view('insufficient_markers')), /마커.*부족/);
  assert.match(supervisorPoseFeedback(view('solver_failed')), /위치 계산/);
  assert.match(supervisorPoseFeedback(view('pose_quality')), /불확실/);
  assert.match(supervisorPoseFeedback(view('<script>')), /확인 불가/);
  assert.match(supervisorPoseFeedback(view('constructor')), /확인 불가/);
});
test('expired, disconnected and mismatched frame diagnostics cannot reuse the old reason', () => {
  assert.equal(typeof supervisorPoseFeedback, 'function');
  for (const status of ['STALE', 'DISCONNECTED', 'INVALID_DATA', 'WAITING']) {
    assert.doesNotMatch(supervisorPoseFeedback(view('marker_geometry', status)), /배치/);
  }
  const v = view();
  v.ageMs = 151;
  assert.match(supervisorPoseFeedback(v), /갱신 지연/);
  v.ageMs = 5;
  v.snapshot.extra.presentation_diagnostics.frame_id = 7;
  assert.match(supervisorPoseFeedback(v), /확인 불가/);
});
test('tracking is camera pose only, and absent metadata never claims optical alignment', () => {
  assert.equal(typeof supervisorPoseFeedback, 'function');
  const v = view('tracking');
  v.snapshot.extra.presentation_pose = 'tracking';
  v.snapshot.extra.presentation_diagnostics.analysis_status = 'tracking';
  assert.match(supervisorPoseFeedback(v), /카메라 위치 추적/);
  assert.match(supervisorPoseFeedback(v), /정합 미검증/);
  v.snapshot.extra = {};
  assert.match(supervisorPoseFeedback(v), /사용 안 함/);
});
