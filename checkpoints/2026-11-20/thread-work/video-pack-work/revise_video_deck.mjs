export async function revise(presentation) {
  const shape = (slide, id) => slide.shapes.items.find(item => item.id === String(id));
  const replace = (slide, id, value) => {
    const item = shape(slide, id);
    if (!item) throw new Error(`Missing shape ${id}`);
    item.text.replace(item.text.toString(), value);
    return item;
  };
  const text = (slide, name, value, x, y, w, h, size = 22, color = '#34495E', bold = false) => {
    const item = slide.shapes.add({ geometry: 'textbox', name,
      position: { left: x, top: y, width: w, height: h },
      fill: 'none', line: { fill: 'none', width: 0 } });
    item.text = value;
    item.text.style = { fontSize: size, typeface: 'Malgun Gothic', color, bold,
      alignment: 'left', verticalAlignment: 'middle', insets: 0 };
    return item;
  };
  const node = (slide, name, title, detail, x, y, w, h, offline = false) => {
    const box = slide.shapes.add({ geometry: 'rect', name,
      position: { left: x, top: y, width: w, height: h },
      fill: offline ? '#F4F5F7' : '#EFF5FA',
      line: { fill: offline ? '#CDD2D8' : '#9FB3C7', width: 1.5 } });
    text(slide, name + '-title', title, x + 16, y + 12, w - 32, 30, 21, '#38577D', true);
    text(slide, name + '-detail', detail, x + 16, y + 47, w - 32, h - 56, 17);
    return box;
  };
  const connect = (slide, a, b, fromSide = 'right', toSide = 'left') =>
    slide.shapes.connect(a, b, { kind: 'elbow', fromSide, toSide,
      line: { style: 'solid', fill: '#8194A5', width: 2 },
      tail: { type: 'triangle', width: 'sm', length: 'sm' } });

  const s16 = presentation.slides.items[15];
  replace(s16, 4, '나사 위치와 도구 위치를 계산하고, 시간에 따른 접근과 이탈을 확인합니다.');
  replace(s16, 7, 'ArUco, PnP');
  replace(s16, 11, '마커로 카메라 자세를 추정합니다.\n등록한 A~D 좌표를 영상에 투영해\n목표 나사의 위치를 계산합니다.');
  replace(s16, 14, 'YOLO 도구 검출');
  replace(s16, 18, '드라이버 검출 결과에서 끝점을\n추정합니다. 나사 평면에서 목표와의\n거리를 계산해 근접 여부를 봅니다.');
  replace(s16, 21, 'MediaPipe 손 특징');
  replace(s16, 25, '저장 영상에서 손 관절 특징을\n추출합니다. HMM, Viterbi로 작업\n단계의 시간적 순서를 분석합니다.');
  for (const id of [11, 18, 25]) {
    const item = shape(s16, id);
    item.position = { ...item.position, height: 108 };
    item.text.fontSize = 21;
  }
  shape(s16, 28).delete();
  s16.speakerNotes.text = '마커 검출은 작업대와 카메라의 위치 관계를 구하는 데 사용합니다. PnP로 카메라 자세를 구하고, 등록해 둔 네 나사 좌표를 영상으로 투영합니다. YOLO는 드라이버를 찾습니다. 검출 결과에서 추정한 끝점과 목표 나사의 거리를 비교해 접근과 이탈의 근거로 사용합니다. MediaPipe는 저장 영상에서 손 특징을 뽑는 오프라인 분석에 사용합니다. 이 특징과 도구, 마커 정보를 HMM과 Viterbi 분석에 활용했습니다. 현재 실시간 시연의 단계 전이는 다음 장의 시간 조건과 FSM이 담당합니다.';

  const s17 = presentation.slides.items[16];
  s17.images.items.slice().forEach(item => item.delete());
  replace(s17, 3, '실시간 안내와 오프라인 단계 분석');
  replace(s17, 5, 'Python 판단 서버 / Unity 양안 안내 / 웹 관제');
  text(s17, 'Live-label', '실시간 안내', 71, 110, 300, 30, 23, '#38577D', true);
  const input = node(s17, 'Camera', 'Beast 카메라', '작업 영상 입력', 71, 223, 190, 108);
  const pose = node(s17, 'Pose', 'ArUco, PnP', '카메라 자세 추정\n등록된 A~D 위치 투영', 311, 159, 240, 116);
  const tool = node(s17, 'Tool', 'YOLO', '도구 끝점 추정\n목표 나사와 거리 계산', 311, 311, 240, 116);
  const decision = node(s17, 'Decision', '시간 조건 + FSM', '접근, 유지, 이탈 확인\n현재 단계, 진행 정보 보존', 601, 223, 240, 130);
  const unity = node(s17, 'Unity', 'Unity → AR 안경', '눈별 투영, SBS 출력\n목표 원과 한글 행동 안내', 891, 159, 318, 116);
  const console = node(s17, 'Console', '웹 관제', '작업 영상, 현재 단계, 기록\n상자, 뚜껑, 최종 확인 입력', 891, 311, 318, 116);
  connect(s17, input, pose); connect(s17, input, tool);
  connect(s17, pose, decision); connect(s17, tool, decision);
  connect(s17, decision, unity); connect(s17, decision, console);
  text(s17, 'Http-label', 'HTTP', 843, 280, 48, 22, 13, '#687785');
  text(s17, 'Flow-note', '관측이 불안정하면 안내를 보류하고, 유효한 관측이 돌아오면 진행을 재확인합니다.', 71, 455, 1138, 28, 18);
  s17.shapes.add({ geometry: 'line', name: 'Offline-divider', position: { left: 71, top: 506, width: 1138, height: 0 }, fill: 'none', line: { fill: '#CCD6DF', width: 1 } });
  text(s17, 'Offline-label', '오프라인 분석', 71, 519, 300, 28, 22, '#687785', true);
  const saved = node(s17, 'Saved-video', '저장 영상', '과거 촬영 데이터', 71, 561, 250, 87, true);
  const features = node(s17, 'Features', 'MediaPipe + 도구, 마커 특징', '손 관절과 작업 특징 추출', 371, 561, 410, 87, true);
  const hmm = node(s17, 'HMM', 'HMM, Viterbi', '단계 순서 추정, 결과 평가', 831, 561, 378, 87, true);
  connect(s17, saved, features); connect(s17, features, hmm);
  s17.speakerNotes.text = '현재 시연은 위쪽의 실시간 경로로 동작합니다. 카메라 영상에서 마커와 도구를 검출하고, 목표와의 거리를 계산합니다. 관측의 유효성과 시간 조건을 확인한 뒤 FSM이 현재 단계를 갱신합니다. 결과는 로컬 HTTP 통신으로 Unity와 웹 관제에 전달됩니다. Unity는 눈별 보정을 적용해 안경에 목표 위치와 다음 행동을 표시합니다. 관제에서는 작업 영상과 진행 상황을 확인하고 상자, 뚜껑, 마지막 조립 상태를 직접 확인합니다. 아래쪽은 별도의 오프라인 분석입니다. 저장 영상에서 얻은 손과 도구, 마커 특징으로 HMM, Viterbi를 평가하며, 이 분석 결과가 현재 실시간 시연을 직접 제어하는 것은 아닙니다.';

  const s19 = presentation.slides.items[18];
  replace(s19, 19, '드라이버 끝을 나사 B에 맞춰주세요');
  shape(s19, 19).text.fontSize = 21;
  replace(s19, 23, '접근, 작업 중, 이탈 안내');
  replace(s19, 27, '현재 목표와 전체 작업 순서');
  s19.speakerNotes.text = '작업자는 안경에서 다음 행동을 확인하고, 옆에서 지켜보는 사람은 관제에서 전체 진행 상황을 확인합니다. 같은 단계 정보가 두 화면에 함께 표시됩니다. 관제에는 현재 작업과 작업대 영상, 단계가 바뀐 기록이 남습니다. 상자와 뚜껑, 마지막 조립 상태는 작업자가 직접 확인합니다. 이를 통해 작업자에게 긴 설명을 띄우지 않으면서도 주변에서는 흐름을 확인할 수 있습니다.';

  const s20 = presentation.slides.items[19];
  s20.images.items.slice().forEach(item => item.delete());
  s20.shapes.items.slice().filter(item => !['2', '3', '4'].includes(item.id)).forEach(item => item.delete());
  replace(s20, 3, '상태 설명보다 지금 할 행동을 먼저');
  replace(s20, 4, '사용자 피드백을 바탕으로 문구, 색상, 진행 보존을 정리했습니다.');
  const columns = [71, 425, 805];
  text(s20, 'Feedback-head-1', '불편했던 점', columns[0], 160, 300, 30, 22, '#38577D', true);
  text(s20, 'Feedback-head-2', '반영한 내용', columns[1], 160, 330, 30, 22, '#38577D', true);
  text(s20, 'Feedback-head-3', '작업자가 보는 안내', columns[2], 160, 404, 30, 22, '#38577D', true);
  const rows = [
    ['영문 상태 설명이 많음', '한글 행동 안내 한 줄로 정리', '드라이버 끝을 나사 A에\n맞춰주세요', '#B47511'],
    ['작업 중인데 완료처럼 느껴짐', '작업 중 파란색, 이탈 안내는\n2초 늦춰 표시', '나사 A를 조여주세요', '#167DA2'],
    ['잠깐 끊기면 다시 시작하는 느낌', '짧은 관측 단절에서 진행 보존\n복귀 후 유효 관측 재확인', '드라이버를 떼어주세요', '#22805A']
  ];
  rows.forEach((row, i) => {
    const y = 221 + i * 122;
    s20.shapes.add({ geometry: 'line', name: `Feedback-rule-${i}`, position: { left: 71, top: y - 14, width: 1138, height: 0 }, fill: 'none', line: { fill: '#DAE2E8', width: 1 } });
    text(s20, `Feedback-problem-${i}`, row[0], columns[0], y, 320, 88, 23, '#34495E', true);
    text(s20, `Feedback-change-${i}`, row[1], columns[1], y, 340, 88, 22);
    text(s20, `Feedback-action-${i}`, row[2], columns[2], y, 404, 88, 24, row[3], true);
  });
  text(s20, 'Feedback-footnote', '나사 A 안내 문구 예시 / 실제 UI 적용 내용', 71, 617, 1138, 28, 16, '#687785');
  s20.speakerNotes.text = '사용자에게 직접 보여주면서 글이 많다는 의견을 들었습니다. 그래서 내부 상태를 설명하는 대신 지금 할 행동을 한 줄로 표시하도록 바꿨습니다. 접근할 때는 드라이버 끝을 목표 나사에 맞추라고 안내하고, 작업 중에는 파란색으로 조임 동작을 안내합니다. 초록색 이탈 안내는 2초 늦춰, 작업 중인데 벌써 끝났다는 느낌을 줄였습니다. 짧게 추적이 끊기더라도 진행을 보존하고, 다시 관측되면 재확인해 이어가도록 수정했습니다. 초록색은 드라이버 이탈 안내이며, 실제 체결 강도를 측정한 결과를 뜻하지는 않습니다.';

  presentation.slides.items[21].hidden = true;
  return { editedSlides: [16, 17, 19, 20], hiddenSlide: 22, originalSlideCount: presentation.slides.items.length };
}
