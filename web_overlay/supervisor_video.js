'use strict';

function bindSupervisorVideo() {
  const node = id => document.getElementById(id);
  const toggle = node('videoEnabled'), image = node('videoImage');
  let model = new FramePreviewState(), generation = 0, controller = null, timer = null, url = null;
  const statuses = { WAITING: '영상 수신 대기', LIVE: '영상 수신 중',
    STALE: '영상 갱신 중단 · 마지막 영상', DISCONNECTED: '영상 연결 끊김 · 마지막 영상',
    INVALID: '영상 정보 확인 필요 · 마지막 영상' };
  const sourceLabel = source => source === 'camera' ? '카메라 영상'
    : source === 'session' ? '저장 세션 영상'
    : source.includes('synthetic') || source.includes('fixture') ? '미리보기 · 테스트 영상' : '입력 종류 미확인';
  function render() {
    const state = model.view(performance.now());
    node('videoStage').dataset.status = toggle.checked ? state.status : 'OFF';
    const label = statuses[state.status];
    node('videoStatus').textContent = toggle.checked ? url ? label : label.replace(' · 마지막 영상', '') : '꺼짐';
    node('videoEmpty').hidden = Boolean(url);
    node('videoEmpty').textContent = toggle.checked ? '영상 수신 대기' : '영상 표시 꺼짐';
    node('videoSource').textContent = state.snapshot ? sourceLabel(state.snapshot.source) : '입력 미확인';
    node('videoSource').title = state.snapshot?.session || '';
    node('videoFrame').textContent = '영상 프레임 ' + (state.snapshot ? '#' + state.snapshot.frame : '—');
    node('videoAge').textContent = '영상 나이 ' + (state.ageMs === null ? '—' : Math.round(state.ageMs) + ' ms');
  }
  function headerNumber(response, key) {
    const value = response.headers.get(key);
    return value !== null && /^\d+$/.test(value) ? Number(value) : null;
  }
  async function poll(version) {
    if (!toggle.checked || version !== generation) return;
    const request = new AbortController();
    controller = request;
    const timeout = setTimeout(() => request.abort(), 1500);
    const started = performance.now();
    let nextUrl = null;
    try {
      const response = await fetch('/frame.jpg', { cache: 'no-store', redirect: 'error', signal: request.signal });
      if (!response.ok || !response.headers.get('Content-Type')?.startsWith('image/jpeg')) throw new Error('No JPEG');
      const metadata = {
        session: decodeURIComponent(response.headers.get('X-AR-Session') || ''),
        source: decodeURIComponent(response.headers.get('X-AR-Source') || ''),
        frame: headerNumber(response, 'X-AR-Frame-Id'),
        timestamp: headerNumber(response, 'X-AR-Timestamp-Ms'),
        age: headerNumber(response, 'X-AR-Frame-Age-Ms'),
      };
      const blob = await response.blob();
      if (!toggle.checked || version !== generation) return;
      nextUrl = URL.createObjectURL(blob);
      const decoded = new Image();
      decoded.src = nextUrl;
      await decoded.decode();
      if (!toggle.checked || version !== generation) return;
      if (model.apply(metadata, started, performance.now())) {
        const previous = url;
        image.src = nextUrl;
        image.hidden = false;
        url = nextUrl;
        nextUrl = null;
        if (previous) URL.revokeObjectURL(previous);
      }
    } catch {
      if (version === generation && toggle.checked) model.fault = 'DISCONNECTED';
    } finally {
      if (nextUrl) URL.revokeObjectURL(nextUrl);
      clearTimeout(timeout);
      if (controller === request) controller = null;
      if (version === generation && toggle.checked) timer = setTimeout(() => poll(version), 200);
      render();
    }
  }
  function stop() {
    generation++;
    clearTimeout(timer);
    controller?.abort();
    model = new FramePreviewState();
    image.hidden = true;
    image.removeAttribute('src');
    if (url) URL.revokeObjectURL(url);
    url = null;
    render();
  }
  toggle.checked = false;
  toggle.addEventListener('change', () => { stop(); if (toggle.checked) poll(generation); });
  window.addEventListener('pagehide', () => { toggle.checked = false; stop(); });
  setInterval(render, 100);
  render();
}
