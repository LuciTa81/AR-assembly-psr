(function () {
  'use strict';
  const confirmationFor = typeof module !== 'undefined' && module.exports
    ? require('./supervisor_state.js').supervisorConfirmation : supervisorConfirmation;
  const steps = ['상자 배치','뚜껑 닫기','나사 A','나사 B','나사 C','나사 D','최종 확인'];
  const positions = {A:'먼 쪽 · 왼쪽',B:'먼 쪽 · 오른쪽',C:'가까운 쪽 · 왼쪽',D:'가까운 쪽 · 오른쪽'};
  const labels = {READY:'준비됨',CHECK:'직접 확인이 필요해요',APPROACH:'드라이버 접근 대기',HOLD:'드라이버 유지 중',
    'MOVE CLEAR':'드라이버를 떼어 주세요','PAUSED · KEPT':'잠시 멈춤 · 진행 보존',RECHECK:'현재 나사 재확인',
    PAUSED:'안내 일시 정지',OFFLINE:'연결이 끊겼어요','FINAL CHECK':'마지막 확인',CONFIRMED:'작업자 최종 확인 완료',
    WAITING:'연결을 기다려요',PLACE:'배치 대기',OBSERVE:'배치 확인 중'};
  const eventLabels = {start:'기록 시작',transition:'단계 전환',complete:'최종 완료'};
  function demoPresentation(view) {
    const index = Number(view.snapshot?.current_state?.slice(1));
    const target = index >= 2 && index <= 5 ? 'ABCD'[index-2] : null;
    let cue = 'READY', tone = 'good';
    if (view.status === 'DISCONNECTED') { cue = 'OFFLINE'; tone = 'error'; }
    else if (['STALE','INVALID_DATA'].includes(view.status)) { cue = 'PAUSED'; tone = 'error'; }
    else if (view.status === 'WAITING') { cue = 'WAITING'; tone = 'neutral'; }
    else if (view.holdProgress === 'retained') { cue = 'PAUSED · KEPT'; tone = 'caution'; }
    else if (view.holdProgress === 'recheck') { cue = 'RECHECK'; tone = 'caution'; }
    else if (view.isReference) { cue = 'PAUSED'; tone = 'caution'; }
    else if (view.status === 'COMPLETED') cue = 'CONFIRMED';
    else if (index === 6) { cue = 'FINAL CHECK'; tone = 'caution'; }
    else if (confirmationFor(view).visible) cue = 'CHECK';
    else if (index < 2) cue = view.status === 'OBSERVING' ? 'OBSERVE' : 'PLACE';
    else if (view.status === 'OBSERVING') { cue = 'HOLD'; tone = 'observe'; }
    else if (view.status === 'OBSERVED') cue = 'MOVE CLEAR';
    else cue = 'APPROACH';
    return {cue, cueLabel:labels[cue], tone, target, locationLabel:positions[target] || null, label:steps[index] || '연결 대기',
      showFeedback:!['HOLD','CHECK','FINAL CHECK','CONFIRMED'].includes(cue)};
  }

  class DemoHistory {
    constructor(limit = 12) {
      this.limit = limit;
      this.items = [];
      this.milestones = [];
      this.completed = false;
      this.session = null;
      this.pending = null;
      this.key = null;
    }
    entries(filter = 'steps') {
      if (filter === 'all') return this.items;
      if (filter === 'attention') return this.items.filter(item => ['caution','error'].includes(item.tone));
      return this.milestones;
    }
    update(view, now) {
      if (!view.snapshot) return false;
      const data = view.snapshot, p = demoPresentation(view);
      if (data.session_id !== this.session) {
        this.session = data.session_id;
        this.items = []; this.key = null; this.pending = null; this.started = now;
        this.milestones = []; this.completed = false;
      }
      const key = JSON.stringify([data.current_state, p.cue]);
      if (key === this.key) { this.pending = null; return false; }
      const immediate = !this.key || this.items[0].state !== data.current_state
        || ['OFFLINE','CONFIRMED'].includes(p.cue) || ['STALE','INVALID_DATA'].includes(view.status);
      if (!immediate) {
        if (this.pending?.key !== key) this.pending = {key, since:now};
        // History suppresses brief label churn; live guidance is never delayed here.
        if (now-this.pending.since < 250) return false;
      }
      const kind = !this.key ? 'start' : p.cue === 'CONFIRMED' && !this.completed ? 'complete'
        : this.items[0].state !== data.current_state ? 'transition' : 'observation';
      const item = {...p, kind, state:data.current_state, seconds:Math.floor((now-this.started)/1000)};
      if (p.cue === 'CONFIRMED') this.completed = true;
      this.items.unshift(item);
      this.items.length = Math.min(this.limit, this.items.length);
      // Keep stage history independent of frequent pause/recovery events.
      if (kind !== 'observation') {
        this.milestones.unshift(item);
        this.milestones.length = Math.min(this.limit, this.milestones.length);
      }
      this.key = key; this.pending = null;
      return true;
    }
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {DemoHistory, demoPresentation};
    return;
  }
  const history = new DemoHistory(120);
  let historyTimer;
  const node = id => document.getElementById(id);
  const updateText = (id, value) => { if (node(id).textContent !== value) node(id).textContent = value; };
  function update() {
    // Share the original controller's validated model; no second state request or state machine.
    const view = model.view(performance.now()), p = demoPresentation(view);
    node('actionSurface').dataset.tone = p.tone;
    node('targetMap').dataset.reference = String(view.isReference);
    updateText('liveCue', p.cueLabel);
    node('liveCue').dataset.cue = p.cue;
    node('feedback').hidden = !p.showFeedback;
    node('confirmationHint').hidden = view.isReference && p.showFeedback;
    node('targetMap').parentElement.hidden = !p.target;
    updateText('stateLabel', p.label);
    const expired = ['WAITING','DISCONNECTED','STALE','INVALID_DATA'].includes(view.status);
    updateText('backgroundTask', p.label + ' · ' + labels[p.cue]);
    updateText('trackingSummary', expired ? '갱신이 중단되었습니다. 아래 수치는 마지막 수신값입니다.'
      : view.isReference ? '현재 작업 안내는 보류 중입니다. 입력값과 보류 이유를 확인해 주세요.' : '현재 수신한 입력값입니다. 영상과 상태는 별도 채널입니다.');
    updateText('targetLetter', p.target || (view.status === 'COMPLETED' ? 'OK' : '--'));
    node('targetLetter').hidden = !p.target && view.status !== 'COMPLETED';
    updateText('mapLabel', p.target ? (view.isReference ? '마지막 목표 · ' : '') + p.locationLabel : p.label);
    node('targetMap').setAttribute('aria-label', '작업자 기준 목표 도식 · ' + (view.isReference ? '마지막 수신 ' : '') + p.label + (p.locationLabel ? ' · ' + p.locationLabel : ''));
    document.querySelectorAll('[data-screw]').forEach(el => {
      const active = el.dataset.screw === p.target;
      el.classList.toggle('active', active);
      if (active) el.setAttribute('aria-current','true'); else el.removeAttribute('aria-current');
    });
    updateHistory(view);
  }
  function updateHistory(view) {
    clearTimeout(historyTimer);
    if (history.update(view, performance.now())) {
      const list = node('recentEvents');
      list.replaceChildren(...history.entries().slice(0,4).map(item => {
        const li = document.createElement('li'), time = document.createElement('time');
        const title = document.createElement('strong'), detail = document.createElement('span');
        time.textContent = String(Math.floor(item.seconds/60)).padStart(2,'0') + ':' + String(item.seconds%60).padStart(2,'0');
        title.textContent = item.label; detail.textContent = eventLabels[item.kind];
        li.dataset.tone = item.kind === 'complete' ? 'good' : 'neutral'; li.append(time,title,detail);
        return li;
      }));
      node('historyEmpty').hidden = history.items.length > 0;
      updateText('historySession', history.session || '아직 작업 기록이 없습니다.');
      renderHistoryTable();
    }
    if (history.pending) historyTimer = setTimeout(() => updateHistory(model.view(performance.now())), 250);
  }
  function renderHistoryTable() {
    const stageOnly = node('historyFilter').value === 'steps';
    const selected = history.entries(node('historyFilter').value);
    node('historyRows').replaceChildren(...selected.map(item => {
      const row = document.createElement('tr');
      row.dataset.tone = stageOnly ? (item.kind === 'complete' ? 'good' : 'neutral') : item.tone;
      for (const value of [String(Math.floor(item.seconds/60)).padStart(2,'0') + ':' + String(item.seconds%60).padStart(2,'0'),item.label,stageOnly ? eventLabels[item.kind] : labels[item.cue]]) {
        const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
      }
      return row;
    }));
    updateText('eventCount', '표시 기록 ' + selected.length + '개');
    updateText('filteredEmpty', history.items.length ? '해당하는 기록이 없습니다.' : '수신된 작업 기록이 없습니다.');
    node('filteredEmpty').hidden = selected.length > 0;
    node('downloadEvents').disabled = history.items.length === 0;
  }
  node('historyFilter').addEventListener('change',renderHistoryTable);
  node('downloadEvents').addEventListener('click',() => {
    if (!history.items.length) return;
    const payload = {scope:'page_session_events',session_id:history.session,source:model.view(performance.now()).snapshot?.source,
      exported_at:new Date().toISOString(),note:'Page-local received events; not a complete server log or torque verification.',
      events:[...history.items].reverse(),stage_events:[...history.entries()].reverse()};
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'assembly-events-' + new Date().toISOString().replace(/[:.]/g,'-') + '.json';
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
  });
  // Original render updates these nodes synchronously. Observe that batch before paint
  // so the new target/cue cannot lag a stage change by an independent timer tick.
  const observer = new MutationObserver(update);
  function observe() {
    for (const id of ['currentState','status','feedbackTitle','interactionMode'])
      observer.observe(node(id), {childList:true, attributes:true, characterData:true, subtree:true});
  }
  window.addEventListener('pagehide', () => {observer.disconnect(); clearTimeout(historyTimer);});
  window.addEventListener('pageshow', event => {if (event.persisted) {observe(); update();}});
  observe();
  update();
})();
