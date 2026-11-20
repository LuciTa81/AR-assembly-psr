(function (root) {
  'use strict';
  const budgetMs = 500;
  const targets = ['box', 'lid', 'screw_a', 'screw_b', 'screw_c', 'screw_d', 'complete'];
  const markerStatuses = ['OK', 'LOST', 'FALLBACK', 'DISABLED', 'UNSTABLE'];
  const text = (value, max) => typeof value === 'string' && value.trim().length > 0 && value.length <= max;
  const integer = value => Number.isSafeInteger(value);
  function valid(frame) {
    if (!frame || frame.schema_version !== 'realtime_v1' || !text(frame.session_id, 256)
        || !integer(frame.frame_id) || frame.frame_id < 1 || !integer(frame.timestamp_ms) || frame.timestamp_ms <= 0
        || !integer(frame.frame_age_ms) || frame.frame_age_ms < 0 || frame.system_status !== 'RUNNING'
        || !/^S[0-6]$/.test(frame.current_state) || !text(frame.current_label, 128)
        || !text(frame.next_action, 256) || !markerStatuses.includes(frame.marker_status)) return false;
    const index = Number(frame.current_state[1]);
    const g = frame.guidance;
    if (frame.target !== targets[index] || !g || g.schema_version !== 'assembly_guidance_v1'
        || typeof g.reason !== 'string' || typeof g.acknowledgement !== 'string'
        || g.acknowledgement.length > 160 || !integer(g.acknowledgement_remaining_ms)
        || g.acknowledgement_remaining_ms < 0 || g.acknowledgement_remaining_ms > 3000) return false;
    if (!validHold(g, index)) return false;
    return g.phase === 'PAUSED' || (index === 6 ? g.phase === 'AWAITING_CONFIRMATION'
      || (g.phase === 'COMPLETED' && g.reason === 'operator_confirmation')
      : ['GUIDING', 'OBSERVING'].includes(g.phase) || (index >= 2 && g.phase === 'OBSERVED'));
  }
  function validHold(g, index) {
    if (g.hold_progress === undefined) return g.hold_remaining_ms === undefined;
    if (g.hold_progress === 'none') return g.hold_remaining_ms === 0;
    if (index < 2 || index > 5) return false;
    if (g.hold_progress === 'checkpoint') return g.phase === 'PAUSED' && g.hold_remaining_ms === 0;
    if (g.hold_progress === 'retained') return g.phase === 'PAUSED'
      && integer(g.hold_remaining_ms) && g.hold_remaining_ms > 0 && g.hold_remaining_ms <= 3000;
    return g.hold_progress === 'recheck' && g.hold_remaining_ms === 0
      && ['PAUSED', 'GUIDING'].includes(g.phase);
  }
  const hold = {
    WAITING: 'Waiting for the local vision server',
    STALE: 'Updates paused. Guidance paused.',
    DISCONNECTED: 'Connection lost. Guidance paused.',
    INVALID_DATA: 'Invalid guidance data. Guidance paused.',
    TRACKING_LOST: 'Bring the workspace markers into view',
  };
  function identity(frame) {
    return JSON.stringify([frame.timestamp_ms, frame.current_state, frame.target, frame.next_action,
      frame.current_label, frame.marker_status, frame.guidance.schema_version,
      frame.guidance.phase, frame.guidance.reason, frame.guidance.acknowledgement,
      frame.guidance.hold_progress, frame.guidance.hold_remaining_ms]);
  }
  class SupervisorState {
    constructor() {
      this.snapshot = null;
      this.fault = 'WAITING';
      this.expiresAt = 0;
      this.ackExpiresAt = 0;
      this.ackKey = null;
      this.holdExpiresAt = 0;
    }
    disconnect() { this.fault = 'DISCONNECTED'; }
    invalid() { this.fault = 'INVALID_DATA'; }
    apply(frame, started, received) {
      if (frame && frame.system_status === 'STARTING') { this.fault = 'WAITING'; return false; }
      if (!valid(frame) || !Number.isFinite(started) || !Number.isFinite(received) || received < started) {
        this.invalid(); return false;
      }
      // Server and browser clocks are unrelated. Count server age plus the full RTT.
      const age = frame.frame_age_ms + received - started;
      if (age >= budgetMs) { this.fault = 'STALE'; return false; }
      const deadline = received + budgetMs - age;
      if (this.snapshot && this.snapshot.session_id === frame.session_id) {
        if (frame.frame_id < this.snapshot.frame_id || frame.timestamp_ms < this.snapshot.timestamp_ms) {
          this.invalid(); return false;
        }
        if (frame.frame_id === this.snapshot.frame_id) {
          this.expiresAt = Math.min(this.expiresAt, deadline);
          if (identity(frame) !== identity(this.snapshot)) this.invalid();
          this.updateAck(frame, received, age);
          this.holdExpiresAt = Math.min(this.holdExpiresAt,
            received + Math.max(0, (frame.guidance.hold_remaining_ms || 0) - age));
          return false;
        }
      }
      this.snapshot = JSON.parse(JSON.stringify(frame));
      this.expiresAt = deadline;
      this.fault = null;
      this.updateAck(frame, received, age);
      this.holdExpiresAt = received + Math.max(0, (frame.guidance.hold_remaining_ms || 0) - age);
      return true;
    }
    updateAck(frame, received, age) {
      const g = frame.guidance;
      if (!g.acknowledgement) { this.ackExpiresAt = 0; return; }
      const key = JSON.stringify([frame.session_id, frame.current_state, g.acknowledgement]);
      const deadline = received + Math.max(0, g.acknowledgement_remaining_ms - age);
      this.ackExpiresAt = key === this.ackKey ? Math.min(this.ackExpiresAt, deadline) : deadline;
      this.ackKey = key;
    }
    view(now) {
      let status = !Number.isFinite(now) ? 'INVALID_DATA' : this.fault;
      if (!status) {
        const finalCheck = this.snapshot.current_state === 'S6'
          && this.snapshot.guidance.reason === 'operator_confirmation'
          && ['AWAITING_CONFIRMATION', 'COMPLETED'].includes(this.snapshot.guidance.phase);
        status = now >= this.expiresAt ? 'STALE' : this.snapshot.marker_status !== 'OK' && !finalCheck
          ? 'TRACKING_LOST' : this.snapshot.guidance.phase;
      }
      const active = ['GUIDING', 'OBSERVING', 'OBSERVED', 'AWAITING_CONFIRMATION', 'COMPLETED'].includes(status);
      const progress = this.snapshot?.guidance?.hold_progress;
      const holdProgress = ['PAUSED', 'TRACKING_LOST', 'GUIDING'].includes(status)
        && (['checkpoint', 'recheck'].includes(progress) || progress === 'retained' && now < this.holdExpiresAt) ? progress : 'none';
      return {
        status, snapshot: this.snapshot, isReference: !active, holdProgress,
        instruction: active || status === 'PAUSED' ? this.snapshot.next_action : hold[status],
        acknowledgement: active && now < this.ackExpiresAt ? this.snapshot.guidance.acknowledgement : '',
        ageMs: this.snapshot ? Math.max(0, budgetMs - this.expiresAt + now) : null,
      };
    }
  }
  function supervisorConfirmation(view) {
    const data = view.snapshot, control = data?.extra?.operator;
    const hybrid = control?.mode === 'hybrid';
    const manualStep = control?.mode === 'operator' || (hybrid && ['S0', 'S1', 'S6'].includes(data.current_state));
    return {hybrid, visible: manualStep,
      enabled: manualStep && !view.isReference && !control.pending && !control.completed
        && (!hybrid || control.can_confirm === true)};
  }
  function supervisorFeedback(view) {
    const result = baseSupervisorFeedback(view);
    if (['PAUSED', 'TRACKING_LOST'].includes(view.status) && view.holdProgress === 'checkpoint') {
      const target = view.snapshot.target.slice(-1).toUpperCase();
      result.title = 'HOLD 기록 보존 · 위치 재확인';
      result.detail = '유지 시간을 처음부터 반복하지 않아도 됩니다. '
        + (view.status === 'TRACKING_LOST' ? '먼저 작업대 마커를 보여 주세요.'
          : '드라이버를 나사 ' + target + ' 위치에 잠깐 보여 주세요.');
      result.stage = null;
      return result;
    }
    if (['PAUSED', 'TRACKING_LOST', 'GUIDING'].includes(view.status)
        && ['retained', 'recheck'].includes(view.holdProgress)) {
      const target = view.snapshot.target.slice(-1).toUpperCase();
      result.title = view.holdProgress === 'retained' ? '진행 보존 중 · 잠시 대기' : '나사 ' + target + ' 재확인 필요';
      result.detail = (view.holdProgress === 'retained'
        ? '현재 나사의 관측 진행을 잠시 기억하고 있습니다. ' : '완료한 단계는 유지됩니다. ') + result.detail;
      result.stage = null;
    }
    return result;
  }
  function supervisorWorkflow(view) {
    const steps = ['상자 배치', '뚜껑 닫기', '나사 A', '나사 B', '나사 C', '나사 D', '최종 확인'];
    const data = view.snapshot, index = data ? Number(data.current_state[1]) : -1;
    const control = data?.extra?.operator, confirmation = supervisorConfirmation(view);
    const label = steps[index] || '작업 대기';
    const feedback = supervisorFeedback(view);
    let action = '입력 연결을 기다리고 있어요';
    if (data && view.isReference) action = '현재 작업을 잠시 멈춰 주세요';
    else if (data) {
      if (view.status === 'COMPLETED') action = '작업자 최종 확인 완료';
      else if (index === 6) action = '전체 조립 상태를 직접 확인해 주세요';
      else if (confirmation.visible) action = label + ' 상태를 확인해 주세요';
      else if (index >= 2) action = view.holdProgress === 'recheck' ? label + ' 위치를 다시 확인해 주세요'
        : view.status === 'OBSERVED' ? '작업을 마쳤으면 드라이버를 ' + label + '에서 떼어 주세요'
        : view.status === 'OBSERVING' ? '드라이버를 ' + label + '에 유지해 주세요'
        : '드라이버를 ' + label + '에 대어 주세요';
      else action = index === 0 ? '상자를 제자리에 놓아 주세요' : '뚜껑을 닫아 주세요';
    }
    let confirmationHint = '';
    if (confirmation.visible) {
      if (view.isReference) confirmationHint = feedback.detail;
      else if (control.completed) confirmationHint = '실제 조립 상태를 작업자가 확인한 기록입니다.';
      else if (control.pending) confirmationHint = '확인을 접수했습니다. 새 입력에서 반영 중입니다.';
      else if (!confirmation.enabled) confirmationHint = '확인 가능한 새 상태를 기다립니다.';
      else confirmationHint = index === 6 ? '나사 네 곳과 뚜껑을 직접 확인해 주세요. 자동 체결 검증은 아닙니다.'
        : index === 0 ? '상자와 마커 배치를 유지해 주세요.'
        : index === 1 ? '뚜껑이 제자리에 닫혀 있는지 확인해 주세요.' : label + '의 체결 상태를 직접 확인해 주세요.';
    }
    return { steps, label, action, confirmationHint,
      mode: view.isReference ? '안내 보류' : confirmation.visible ? '사용자 확인' : '자동 관측',
      progress: index < 0 ? '단계 수신 대기' : view.status === 'COMPLETED' ? '전체 확인 완료'
        : (view.isReference ? '마지막 단계 ' : '현재 단계 ') + (index + 1) + ' / 7' };
  }
  function baseSupervisorFeedback(view) {
    const data = view.snapshot, extra = data?.extra || {};
    const reason = data?.guidance?.reason || '';
    const result = { stage: null, title: '상태 수신 대기', detail: '로컬 인식 서버의 연결을 기다립니다.', driver: '판정 보류' };
    const faults = {
      WAITING: ['상태 수신 대기', '로컬 인식 서버의 연결을 기다립니다.'],
      DISCONNECTED: ['서버 연결 끊김', '연결이 복구될 때까지 작업 안내를 보류합니다.'],
      STALE: ['상태 갱신 중단', '마지막 상태를 참고로 표시합니다. 다음 단계는 판정하지 않습니다.'],
      INVALID_DATA: ['상태 데이터 확인 필요', '유효한 새 상태를 기다립니다.'],
      TRACKING_LOST: ['마커 추적 대기', '등록 마커의 테두리와 흰 여백 전체가 카메라 안에 들어오게 해 주세요.'],
    };
    if (faults[view.status]) {
      [result.title, result.detail] = faults[view.status];
      return result;
    }
    if (reason === 'operator_confirmation') {
      result.title = view.status === 'COMPLETED' ? '작업자 최종 확인 완료' : '사용자 확인 모드';
      const hybrid = extra.operator?.mode === 'hybrid';
      result.detail = view.status === 'COMPLETED' ? '작업자가 전체 조립 상태를 확인했습니다. 자동 체결 검증 결과는 아닙니다.'
        : hybrid ? (data.current_state === 'S6' ? 'A–D 접근·이탈 관측이 끝났습니다. 실제 체결 상태는 작업자가 확인해야 합니다.'
          : '현재 배치 상태는 사용자 확인으로 기록됩니다. A–D는 도구 접근·이탈 관측으로 진행됩니다.')
        : '단계 완료는 작업자 확인으로 기록됩니다. 자동 인식은 실행하지 않습니다.';
      result.driver = hybrid ? (data.current_state === 'S6' ? '나사 관측 종료' : '나사 작업 대기') : '자동 인식 꺼짐';
      return result;
    }
    const count = extra.driver_count;
    if (extra.yolo_reason === 'ok') {
      result.driver = integer(count) && count >= 0 ? count === 0 ? '미검출' : count + '개 검출' : '정보 없음';
    } else result.driver = extra.yolo_reason ? '판정 보류' : '정보 없음';
    if (view.status === 'PAUSED') {
      const reasons = {
        multiple_tool_candidates: ['드라이버 복수 후보', '위치가 모호해 현재 목표를 다시 확인해야 합니다. 작업 영역에는 드라이버 하나만 보여 주세요.'],
        tool_not_visible: [count > 1 && extra.yolo_reason === 'ok' ? '드라이버 복수 검출' : '드라이버 관측 대기',
          count > 1 && extra.yolo_reason === 'ok' ? '중복 검출로 이탈 판정을 보류합니다.' : '드라이버를 카메라 시야 안에 유지해 주세요.'],
        tool_position_unknown: ['드라이버 끝 위치 확인 중', '도구 끝과 목표 나사가 함께 보이도록 해 주세요.'],
        invalid_observation: ['새 분석 결과 대기', '현재 추적에 맞는 유효한 도구 관측을 기다립니다.'],
        observation_gap: ['도구 관측 끊김', '연속 관측이 끊겨 접근·이탈 판정을 보류합니다.'],
        invalid_roi: ['상자 영역 확인 중', '작업대와 상자의 위치를 확인해 주세요.'],
      };
      [result.title, result.detail] = reasons[reason] || ['관측 일시 정지', '서버의 유효한 새 관측을 기다립니다.'];
    } else if (view.status === 'AWAITING_CONFIRMATION') {
      result.title = '최종 사용자 확인 대기';
      result.detail = '관측 순서가 끝났습니다. 실제 체결 상태는 작업자가 확인해야 합니다.';
    } else {
      const screw = Number(data?.current_state?.slice(1)) >= 2;
      result.stage = ['GUIDING', 'OBSERVING', 'OBSERVED'].indexOf(view.status);
      if (view.status === 'OBSERVED') {
        result.title = '접근 관측됨 · 도구 이탈 대기';
        result.detail = '작업이 끝나면 드라이버를 목표에서 떼되 카메라에는 보이게 유지해 주세요.';
      } else if (view.status === 'OBSERVING') {
        result.title = screw ? '목표 접근 관측 중' : '배치 상태 관측 중';
        result.detail = '아직 다음 단계로 넘어가지 않고 현재 작업을 유지합니다.';
      } else {
        result.title = screw ? '목표 나사 접근 대기' : '상자·뚜껑 배치 대기';
        result.detail = screw ? '현재 목표에 드라이버를 접근시켜 주세요.' : '위 작업 지시에 맞춰 배치해 주세요.';
      }
    }
    return result;
  }

  class FramePreviewState {
    constructor() { this.snapshot = null; this.expiresAt = 0; this.fault = 'WAITING'; }
    apply(frame, started, received) {
      const reject = status => { this.fault = status; return false; };
      if (!frame || !text(frame.session, 256) || !text(frame.source, 128)
          || !integer(frame.frame) || frame.frame < 1 || !integer(frame.timestamp) || frame.timestamp <= 0
          || !integer(frame.age) || frame.age < 0 || !Number.isFinite(started)
          || !Number.isFinite(received) || received < started) return reject('INVALID');
      const age = frame.age + received - started;
      if (age >= 1500) return reject('STALE');
      const deadline = received + 1500 - age;
      const old = this.snapshot;
      if (old?.session === frame.session) {
        if (frame.frame < old.frame || frame.timestamp < old.timestamp) return reject('INVALID');
        if (frame.frame === old.frame) {
          this.expiresAt = Math.min(this.expiresAt, deadline);
          if (frame.timestamp !== old.timestamp || frame.source !== old.source) this.fault = 'INVALID';
          return false;
        }
      }
      this.snapshot = { ...frame };
      this.expiresAt = deadline;
      this.fault = null;
      return true;
    }
    view(now) {
      return { status: this.fault || (now >= this.expiresAt ? 'STALE' : 'LIVE'),
        snapshot: this.snapshot, ageMs: this.snapshot ? Math.max(0, 1500 - this.expiresAt + now) : null };
    }
  }
  function supervisorPoseFeedback(view) {
    const faults = {
      WAITING: '위치 안내 대기 · 상태 수신 대기',
      DISCONNECTED: '위치 안내 보류 · 서버 연결 끊김',
      STALE: '위치 안내 보류 · 상태 갱신 지연',
      INVALID_DATA: '위치 안내 보류 · 상태 데이터 확인 필요',
      TRACKING_LOST: '위치 안내 보류 · 작업대 마커 추적 중단',
    };
    if (faults[view.status]) return faults[view.status];
    const data = view.snapshot, extra = data?.extra;
    if (extra?.presentation_overlay !== 1) return '위치 안내 사용 안 함';
    const d = extra.presentation_diagnostics;
    if (!d || d.frame_id !== data.frame_id || !Number.isFinite(view.ageMs) || view.ageMs < 0)
      return '위치 안내 보류 · 위치 정보 확인 불가';
    // State age is already capture-to-client age, including the request RTT.
    if (view.ageMs > 150 || extra.presentation_pose === 'stale')
      return '위치 안내 보류 · 위치 갱신 지연';
    if (extra.presentation_pose === 'camera_error') return '위치 안내 보류 · 카메라 입력 중단';
    if (extra.presentation_pose === 'waiting') return '위치 안내 대기 · 새 관측 대기';
    if (extra.presentation_pose === 'tracking' && d.analysis_status === 'tracking')
      return '카메라 위치 추적 중 · ' + (extra.presentation_selection === 'stage'
        ? (extra.presentation_target ? '현재 목표 ' + extra.presentation_target : '목표 강조 없음')
        : 'A 고정 참조') + ' · 안경 정합 미검증';
    const reasons = {
      insufficient_markers: '등록 마커 부족 · 테두리 전체가 보이게 해 주세요',
      marker_geometry: '마커 배치 조건 부족 · 서로 떨어진 마커가 함께 보이게 해 주세요',
      solver_failed: '위치 계산 실패 · 새 관측 대기',
      pose_quality: '위치 계산 불확실 · 새 관측 대기',
      target_outside: '목표가 카메라 시야 밖에 있음',
    };
    return '위치 안내 보류 · ' + (extra.presentation_pose === 'pose_rejected' && d.analysis_status === 'pose_rejected'
      && Object.hasOwn(reasons, d.reason_code) ? reasons[d.reason_code] : '위치 정보 확인 불가');
  }
  const api = { SupervisorState, supervisorFeedback, supervisorWorkflow, supervisorPoseFeedback, supervisorConfirmation, FramePreviewState };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else Object.assign(root, api);
})(globalThis);
