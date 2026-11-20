'use strict';
const model = new SupervisorState();
const byId = id => document.getElementById(id);
const statuses = {
  WAITING: ['연결 대기', 'neutral'], GUIDING: ['작업 안내', 'good'],
  OBSERVING: ['작업 관측 중', 'observe'], OBSERVED: ['관측됨 · 도구 이탈 대기', 'observe'],
  PAUSED: ['관측 일시 정지', 'caution'], TRACKING_LOST: ['마커 추적 중단', 'caution'],
  AWAITING_CONFIRMATION: ['최종 확인 대기', 'caution'], STALE: ['데이터 갱신 중단', 'error'],
  COMPLETED: ['작업자 확인 완료', 'good'],
  DISCONNECTED: ['서버 연결 끊김', 'error'], INVALID_DATA: ['상태 데이터 오류', 'error'],
};
const targetLabels = { box: '상자', lid: '뚜껑', screw_a: '나사 A', screw_b: '나사 B', screw_c: '나사 C', screw_d: '나사 D', complete: '전체 조립 확인' };
let confirming = false;
let confirmationResultKey = null;
function set(id, value) {
  const node = byId(id);
  if (node.textContent !== value) node.textContent = value;
}
function number(value, digits = 0, suffix = '') {
  return Number.isFinite(value) && value >= 0 ? value.toFixed(digits) + suffix : '—';
}
function render() {
  const view = model.view(performance.now());
  const data = view.snapshot;
  const operator = data?.extra?.operator;
  const confirmation = supervisorConfirmation(view);
  const workflow = supervisorWorkflow(view);
  const manual = confirmation.visible;
  const controlKey = JSON.stringify([data?.session_id, operator?.revision]);
  if (confirmationResultKey !== controlKey) set('operatorResult', '');
  byId('operatorControls').hidden = !manual;
  byId('confirmStep').disabled = confirming || !confirmation.enabled;
  set('confirmStep', confirming || operator?.pending ? '확인 반영 중…' : operator?.completed ? '최종 확인 완료' : data?.current_state === 'S6'
    ? '전체 조립 최종 확인' : (targetLabels[data?.target] || '현재 작업') + ' 완료 확인');
  set('confirmationHint', workflow.confirmationHint);
  set('actionTitle', workflow.action);
  set('interactionMode', workflow.mode);
  set('stepProgress', workflow.progress);
  document.querySelector('.video-note').textContent = data?.extra?.presentation_overlay === 1
    ? ('카메라 투영 · ' + (data.extra.presentation_selection === 'stage'
      ? (data.extra.presentation_target ? '현재 목표 ' + data.extra.presentation_target : '목표 강조 없음')
      : 'A 고정 참조') + ' · 안경 시야 녹화 아님 · 정합 미검증')
    : '원본 영상 · 상태와 별도 수신 · 실물 정합 표시 없음';
  const feedback = supervisorFeedback(view);
  set('feedbackTitle', feedback.title);
  set('feedbackDetail', feedback.detail);
  set('poseFeedback', supervisorPoseFeedback(view));
  set('driverEvidence', feedback.driver);
  byId('feedback').dataset.paused = String(view.isReference);
  const isScrew = data && Number(data.current_state[1]) >= 2 && data.current_state !== 'S6';
  set('phaseStart', isScrew ? '대상 접근' : '대상 배치');
  set('phaseEnd', isScrew ? '이탈 대기' : '다음 단계');
  byId('phaseRail').hidden = manual || !data || data.current_state === 'S6';
  document.querySelectorAll('#phaseRail li').forEach((step, i) => {
    step.classList.toggle('active', i === feedback.stage);
    step.classList.toggle('past', feedback.stage !== null && i < feedback.stage);
    if (i === feedback.stage) step.setAttribute('aria-current', 'step');
    else step.removeAttribute('aria-current');
  });
  const [label, tone] = statuses[view.status];
  set('status', label);
  byId('status').dataset.tone = tone;
  byId('status').dataset.status = view.status;
  set('instruction', view.instruction);
  set('instructionCaption', view.isReference ? '안내 보류' : '다음 행동');
  set('acknowledgement', view.acknowledgement || '\u00a0');
  set('stateCaption', data && view.isReference ? '마지막 수신 상태' : '현재 상태');
  set('currentState', data?.current_state || '—');
  set('stateLabel', workflow.label + (isScrew ? ' 작업' : ''));
  set('target', targetLabels[data?.target] || '—');
  set('session', data?.session_id || '연결 대기');
  set('frame', data ? '프레임 ' + data.frame_id : '프레임 —');
  const source = data?.source || '';
  set('sourceKind', source.includes('synthetic') || source.includes('fixture') ? '합성 재생 · 실측 아님'
    : source === 'camera' ? '실시간 카메라' : source === 'session' ? '저장 세션 재생'
    : source === 'dummy' ? '더미 입력 · 실측 아님' : '입력 종류 미확인');
  set('marker', data?.marker_status || '—');
  set('markerCount', number(data?.marker_count));
  const metric = data?.extra?.presentation_overlay === 1;
  set('qualityLabel', metric ? '카메라 재투영 오차' : 'Warp 품질');
  set('quality', metric ? number(data?.extra?.presentation_diagnostics?.rms_px, 2, ' px') : number(data?.warp_quality, 2));
  set('fps', number(data?.fps, 1));
  set('latency', number(data?.latency_ms, 0, ' ms'));
  set('age', number(view.ageMs, 0, ' ms'));
  const reference = data && view.isReference;
  set('dataNote', reference ? '안내가 보류되었습니다. 상태·입력 수치는 마지막 수신값입니다.'
    : data ? (confirmation.hybrid ? '상자·뚜껑·최종: 사용자 확인 · A–D: 자동 관측'
      : manual ? '로컬 서버 상태 · 사용자 확인 진행 · 자동 인식 꺼짐' : '로컬 서버 상태 · 읽기 전용') : '상태 데이터 수신 대기');
  const index = data ? Number(data.current_state[1]) : -1;
  byId('steps').classList.toggle('reference', Boolean(reference));
  document.querySelectorAll('#steps li').forEach((step, i) => {
    step.querySelector('span').textContent = workflow.steps[i];
    step.classList.toggle('past', i < index);
    step.classList.toggle('current', i === index);
    if (i === index) step.setAttribute('aria-current', 'step');
    else step.removeAttribute('aria-current');
  });
}
byId('confirmStep').addEventListener('click', async () => {
  const view = model.view(performance.now()), data = view.snapshot;
  if (confirming || !supervisorConfirmation(view).enabled) return;
  confirming = true;
  render();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2000);
  try {
    const response = await fetch('/operator/confirm', {
      method: 'POST', redirect: 'error', signal: controller.signal,
      headers: {'Content-Type': 'application/json', 'X-AR-Operator': 'confirm'},
      body: JSON.stringify({ session_id: data.session_id, revision: data.extra.operator.revision }),
    });
    confirmationResultKey = JSON.stringify([data.session_id, data.extra.operator.revision]);
    set('operatorResult', response.status === 202 ? '확인 접수 · 새 입력에서 반영됩니다.'
      : '확인 보류 · 현재 단계와 추적 상태를 확인해 주세요.');
  } catch {
    confirmationResultKey = JSON.stringify([data.session_id, data.extra.operator.revision]);
    set('operatorResult', '응답 확인 실패 · 재시도 전에 현재 단계를 확인해 주세요.');
  } finally { clearTimeout(timeout); confirming = false; render(); }
});
async function poll() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1000);
  const started = performance.now();
  try {
    const response = await fetch('/state.json', { cache: 'no-store', signal: controller.signal, redirect: 'error' });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const raw = await response.text();
    if (raw.length > 65536) model.invalid();
    else {
      try { model.apply(JSON.parse(raw), started, performance.now()); }
      catch { model.invalid(); }
    }
  } catch { model.disconnect(); }
  finally { clearTimeout(timeout); render(); setTimeout(poll, 50); }
}
function fullscreenState() {
  const active = Boolean(document.fullscreenElement), button = byId('fullscreen');
  button.disabled = !document.fullscreenEnabled;
  button.setAttribute('aria-pressed', String(active));
  const label = active ? '전체 화면 종료' : '전체 화면';
  button.title = document.fullscreenEnabled ? label : '이 브라우저는 전체 화면을 지원하지 않습니다';
  button.setAttribute('aria-label', button.title);
  byId('expandIcon').toggleAttribute('hidden', active);
  byId('collapseIcon').toggleAttribute('hidden', !active);
}
byId('fullscreen').addEventListener('click', async () => {
  byId('displayError').hidden = true;
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch {
    set('displayError', '전체 화면으로 전환하지 못했습니다. 작업 상태는 그대로 유지됩니다.');
    byId('displayError').hidden = false;
  }
  fullscreenState();
});
document.addEventListener('fullscreenchange', fullscreenState);
fullscreenState();
render();
bindSupervisorVideo();
setInterval(render, 100);
poll();
