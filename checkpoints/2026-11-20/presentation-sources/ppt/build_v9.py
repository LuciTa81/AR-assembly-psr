# -*- coding: utf-8 -*-
"""사용자가 올린 v8(user_v8/u.pptx, 19장)을 그대로 두고 뒤쪽만 다시 짠다 → v9 (20장).
2  Contents      : 06 제목과 설명
16 Evaluation · Results : 평가와 결과를 한 장으로 (세 문제의 처음 → 지금 + 시연 숫자)
17 Expected Impact      : 왜 필요한가(현장 수치) → 누구에게 무엇을 → 선행 사례의 효과
18 Future Work (새 장)  : 후속 연구 + 예상되는 상업적 가치
19 마무리(그대로), 20 Memo(장 번호를 지금 덱에 맞춰 다시 씀)
외부 수치는 모두 출처를 확인한 값이고, 장 아래 출처 줄과 발표자 노트에 적는다."""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip
from pptx import Presentation
W_ = '/home/claude/grad'; PR = W_ + '/prep_r/'; BODY = '333333'
SRC = W_ + '/user_v8/u.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v9.pptx'
prs = Presentation(SRC); S = list(prs.slides); assert len(S) == 19
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
def title_of(s): return [sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.name == 'Title']
def drop_pic(s, sh):
    rids = [b.get(R_NS + 'embed') for b in sh._element.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}blip')]
    sh._element.getparent().remove(sh._element)
    for rid in rids:
        if rid and rid not in s.shapes._spTree.xml: s.part.drop_rel(rid)
def clear(s):
    for sh in list(s.shapes):
        if sh.shape_type == 13: drop_pic(s, sh)
        else: sh._element.getparent().remove(sh._element)
def arw(s, x, y, color=LBLUE, size=15, h=28, w=26): tb(s, x, y, w, h, '→', size=size, color=color, w8='s', align='c', anchor='m', wrap=False)
def sec(s, x, y, text, w=500): tb(s, x, y, w, 24, text, size=13, color=ORANGE, w8='x', anchor='m')
def set_text(sh, text):
    rs = sh.text_frame.paragraphs[0].runs; rs[0].text = text
    for r in rs[1:]: r._r.getparent().remove(r._r)
def note(s, text): s.notes_slide.notes_text_frame.text = text
def renote(s, a, b):
    tf = s.notes_slide.notes_text_frame; t = tf.text; assert a in t, a; tf.text = t.replace(a, b)

# ------------------------------------------------------------------ 2 Contents
s = S[1]; n = 0
for sh in s.shapes:
    if not sh.has_text_frame: continue
    t = sh.text_frame.text.strip()
    if t == '시연과 결과': set_text(sh, '시연, 결과와 가치'); n += 1
    elif t == '실제 시연, 검증 결과, 성과': set_text(sh, '실제 시연, 검증 결과, 기대효과, 후속 연구와 상업적 가치'); n += 1
assert n == 2

# ------------------------------------------------------------------ 16 Evaluation · Results (두 장을 한 장으로)
s = S[15]; assert title_of(s) == ['Evaluation']; clear(s)
header(s, 'Evaluation · Results', '세 문제가 풀렸는지, 숫자와 기록으로 확인했습니다')
CW = 368; VY = 136; VH = 190
cols = [dict(k='문제 1 · 단계 인식', was='첫 결과는 정확도 61.3%', big='94.1%', lab='단계 인식 정확도',
             sub='119프레임 중 틀린 프레임 46 → 7', cond='1학기 · session 17 · 정답 라벨과 비교'),
        dict(k='문제 2 · 양안 정합', was='카메라에서 맞는 위치가 안경에서는 어긋남', big='4 / 4', lab='나사 네 개가 실물 위에 하나로',
             sub='거리와 시점을 바꿔도 겹침 유지', cond='2학기 · 같은 착용 상태에서 눈으로 확인',
             img='ev_fit.jpg', tag='안내 윤곽이 실물과 겹침'),
        dict(k='문제 3 · 가림과 복구', was='손이 마커를 가리면 처음부터 다시 시작', big='10 / 10', lab='가려진 뒤 하던 단계에서 계속',
             sub='가장 길게는 6초 동안 가려져도 이어 감', cond='take4 시연 · 2분 1초 · Unity 화면 기준',
             img='ev_rec.jpg', tag='손이 마커를 가린 순간')]
for k, c in enumerate(cols):
    x = 71 + k * 385
    hline(s, x, 100, CW, color=NAVY, lw=1.25)
    tb(s, x, 108, CW, 22, c['k'], size=12, color=ORANGE, w8='x', anchor='m')
    if 'img' in c:
        pic(s, PR + c['img'], x, VY, CW, VH)
        chip(s, x + 8, VY + 8, c['tag'], fill=WHITE, color=NAVY, size=9.5, h=22, w8='x')
    else:                                                        # 정확도 막대: 0에서 시작, 마지막만 네이비
        rect(s, x, VY, CW, VH, fill=PALE)
        BASE = VY + 138; MAXH = 104; BW = 76
        data = [(61.3, '5월 첫 결과', '틀린 프레임 46'), (87.4, '파라미터 탐색 뒤', '틀린 프레임 15'), (94.1, '6월 최종', '틀린 프레임 7')]
        for j, (v, a_, b_) in enumerate(data):
            bx = x + 26 + j * 120; h = MAXH * v / 100; last = j == 2
            rect(s, bx, BASE - h, BW, h, fill=NAVY if last else LBLUE)
            tb(s, bx - 22, BASE - h - 30, BW + 44, 26, '%.1f%%' % v, size=17 if last else 13, color=NAVY if last else GREY, w8='x', align='c', anchor='b', wrap=False)
            tb(s, bx - 22, BASE + 7, BW + 44, 18, a_, size=10.5, color=TXT, w8='s', align='c', anchor='m', wrap=False)
            tb(s, bx - 22, BASE + 26, BW + 44, 16, b_, size=9.5, color=GREY, align='c', anchor='m', wrap=False)
            if j < 2: arw(s, bx + BW + 9, BASE - 62, color=GREY, size=12)
        hline(s, x + 14, BASE, CW - 28, color=LGREY)
    y = VY + VH + 12
    chip(s, x, y + 1, '처음', fill=PALE, color=GREY, size=9.5, w=42, h=20, w8='s')
    tb(s, x + 52, y, CW - 52, 22, c['was'], size=12, color=GREY, anchor='m', wrap=False)
    chip(s, x, y + 47, '지금', fill=NAVY, color=WHITE, size=9.5, w=42, h=20, w8='s')
    tb(s, x + 52, y + 26, CW - 52, 60, c['big'], size=40, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, y + 90, CW, 26, c['lab'], size=15, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, y + 116, CW, 22, c['sub'], size=12, color=BODY, anchor='m', wrap=False)
    tb(s, x, y + 140, CW, 18, c['cond'], size=9.5, color=LGREY, anchor='m', wrap=False)
sec(s, 71, 522, '시연에서 확인한 것')
hline(s, 71, 550, 1138, color=NAVY, lw=1.25)
stats = [('2분 1초', '상자 하나를 처음부터 끝까지'), ('7단계', '빠짐없이 순서대로 안내'), ('4 / 4', '버튼 없이 다음 나사로 넘어감'), ('안경 + 노트북', '다른 장비 없이 시작하고 끝냄')]
for k, (b_, l_) in enumerate(stats):
    x = 71 + k * 291.33
    if k: rect(s, x - 14, 562, 0.8, 68, fill=LINE)
    tb(s, x, 556, 264, 46, b_, size=26, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, 604, 264, 22, l_, size=12, color=BODY, anchor='m', wrap=False)
src(s, '시연 수치는 take4 한 번의 기록입니다 (2분 1초 · Unity 화면 기준)', y=664)
note(s, '[평가와 결과] 7장의 세 문제에 하나씩 답한다. 문제마다 "처음에는 이랬고, 지금은 이렇다"로 말한 뒤, 아래 줄로 시연 전체를 정리한다.\n'
        '문제 1: 같은 119프레임에서 HMM 정확도가 61.3%(73/119) → 87.4%(104/119) → 94.1%(112/119). 틀린 프레임은 46 → 15 → 7. '
        '앞의 두 값은 5월 발표 자료의 Before / After(grid search), 마지막 값은 6월 최종 보고서의 session 17 결과다. 참고로 최종 보고서 기준 프레임별 판단은 88.2%, FSM은 91.6%.\n'
        '문제 2: 2026년 11월 14일 같은 착용 상태에서, 거리(가까이 ↔ 기준 거리)와 시점(작은 측면 이동 → 정면 복귀)을 바꿔 가며 나사 A ~ D를 착용자가 눈으로 확인했다. '
        '기록은 거리에서 "대체로 하나로 겹침", 시점에서 "겹침 유지"다(12장에서 날짜와 표현을 고치신 데 맞춰 화면에는 날짜를 넣지 않았다). 가운데 그림은 작업대 사진에 Unity 왼눈 화면을 맞춰 얹은 재현이며, 안경 렌즈를 통해 찍은 사진이 아니다.\n'
        '문제 3: take4 시연(2분 1초)을 Unity 화면에서 0.1초 단위로 쟀다. 1초 넘게 가려진 구간 10번, 가장 긴 구간 6.0초, 10번 모두 하던 단계에서 이어 갔고 단계가 뒤로 간 적은 없다.\n'
        '아래 줄: take4 시연에서 일곱 단계를 2분 1초에 진행했고, 나사 네 개는 버튼을 누르지 않고 다음 나사로 넘어갔다. 장비는 안경(VITURE Beast)과 Windows 노트북이다.\n'
        '화면에서 뺀 것: "사용하면서 고친 것"(상태 설명이 많아 지금 할 일을 찾기 어려움 → 큰 행동 문구 한 줄과 목표 강조로 정리 / 영문 상태 문구가 낯섦 → 한글 행동 문구로 변경)은 말로만 덧붙인다.\n'
        '화면에서 뺀 단서: 세 결과는 조건이 다르다(오프라인 한 세션 · 시연 한 번 · 착용자 확인). 파라미터 탐색과 평가에 같은 세션을 썼는지 확인이 필요하다. 촬영용 설정이라 초록 안내 2초 뒤 자동으로 넘어간다. '
        '여러 사람 · 여러 번의 반복 성공률, 실물 기준 위치 오차(mm), 지연 시간은 아직 재지 못했다. 가려진 시간은 모두 38.3초다. 질문이 나오면 그대로 답한다.')

# ------------------------------------------------------------------ 17 Expected Impact (누구를 위해, 왜, 어떤 가치)
s = S[16]; assert title_of(s) == ['Results']; clear(s)
header(s, 'Expected Impact', '경력이 없어도, 처음 하는 사람이 바로 조립할 수 있게')
sec(s, 71, 100, '왜 필요한가')
why = [('46만 7천 명', '사람을 구하지 못한 빈자리', '사업체 부족인원 · 제조업이 9만 6천 명으로 가장 많음 (2026. 4)'),
       ('25.8%', '못 뽑는 이유 1위는 경력', '미충원 사유 1위: 요구하는 경력을 갖춘 지원자가 없음'),
       ('28만 7,424명', '역대 가장 많은 고용허가제 외국인 근로자', '이 가운데 22만 9,844명이 제조업 (2026. 7)')]
for k, (b_, l_, s_) in enumerate(why):
    x = 71 + k * 385
    hline(s, x, 128, 368, color=NAVY, lw=1.25)
    tb(s, x, 133, 368, 46, b_, size=27, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, 180, 368, 22, l_, size=13, color=TXT, w8='s', anchor='m', wrap=False)
    tb(s, x, 203, 368, 18, s_, size=10, color=GREY, anchor='m', wrap=False)
tb(s, 71, 232, 1138, 28, '경력자는 구하기 어렵고, 처음 하는 사람과 말이 다른 사람은 늘고 있습니다.', size=14.5, color=NAVY, w8='x', anchor='m')
sec(s, 71, 276, '누구에게 무엇을')
who = [('처음 하는 작업자', '외우지 않고 첫날부터', '다음 행동이 작업 위치 위에 보입니다. 순서를 외우지 않아도 끝까지 조립하고, 안내 문구는 다른 언어로 바꿀 수 있습니다.'),
       ('가르치는 숙련자', '옆에 붙어 있지 않아도', '한 사람씩 붙어 순서를 알려 주던 시간을 줄입니다. 진행은 관제 화면으로 확인합니다.'),
       ('현장 관리자', '빠뜨림 없이, 기록으로', '단계를 시스템이 따라가 순서를 건너뛰는 실수를 줄이고, 작업이 어떻게 진행됐는지 기록으로 남깁니다.')]
for k, (w_, t_, d_) in enumerate(who):
    x = 71 + k * 385
    rect(s, x, 304, 368, 160, fill=PALE)
    chip(s, x + 18, 318, w_, fill=TINT, color=NAVY, size=9.5, h=20, w8='s')
    tb(s, x + 18, 344, 332, 30, t_, size=17, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x + 18, 380, 332, 72, d_, size=12, color=BODY, ls=1.4)
sec(s, 71, 484, '선행 사례가 보여 준 AR 안내의 효과')
hline(s, 71, 512, 1138, color=NAVY, lw=1.25)
ev = [('약 30%', '조립 시간 단축', 'PDF 설명서 대비 · Boeing · Iowa State Univ.'),
      ('90% 가까이', '첫 시도 품질 개선', 'PDF 설명서 대비 · Boeing · Iowa State Univ.'),
      ('25%', '배선 작업 시간 단축', 'Boeing · 스마트 안경 작업 안내')]
for k, (b_, l_, s_) in enumerate(ev):
    x = 71 + k * 285
    tb(s, x, 518, 268, 44, b_, size=24, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, 563, 268, 22, l_, size=12.5, color=TXT, w8='s', anchor='m', wrap=False)
    tb(s, x, 586, 268, 18, s_, size=10, color=GREY, anchor='m', wrap=False)
rect(s, 926, 524, 283, 84, fill=PALE)
tb(s, 942, 532, 251, 22, '여기에 더한 것', size=12, color=ORANGE, w8='x', anchor='m')
tb(s, 942, 556, 251, 46, '버튼을 누르지 않아도 단계가 넘어가, 두 손이 작업에 남습니다.', size=12, color=NAVY, w8='s', ls=1.35)
tb(s, 71, 660, 1138, 34, ['출처: 고용노동부 2026년 상반기 직종별사업체노동력조사(2026. 6. 30) · 고용노동부 고용허가제 자료(2026. 7 기준)',
                          'Boeing · Iowa State Univ.(I/ITSEC 2014) · Boeing 항공기 배선 작업 사례'], size=9, color=LGREY, ls=1.25, name='Source')
note(s, '[기대효과] 누구를 위해, 왜 만들었고, 어떤 가치가 있는지를 위에서 아래로 말한다.\n'
        '왜 필요한가: 고용노동부 2026년 상반기 직종별사업체노동력조사(2026. 6. 30 발표). 2026년 4월 1일 기준 사업체 부족인원 46만 7천 명, 산업별로는 제조업이 9만 6천 명으로 가장 많다. '
        '1분기 미충원 사유 1위는 "사업체가 요구하는 경력을 갖춘 지원자가 없음"(25.8%). 고용허가제(E-9) 외국인 근로자는 2026년 7월 기준 28만 7,424명으로 역대 최대, 이 가운데 22만 9,844명이 제조업(고용노동부 자료, SBS Biz 2026. 9. 2 보도). '
        '"말이 다른 사람이 늘고 있다"는 이 수치를 보고 한 해석이다.\n'
        '누구에게 무엇을: 처음 하는 작업자(순서를 외우지 않음) → 가르치는 숙련자(옆에 붙어 있는 시간) → 현장 관리자(순서 누락, 작업 기록). 이 세 칸은 측정한 값이 아니라 이 구조에서 기대하는 것이다.\n'
        '선행 사례: Boeing과 Iowa State University의 날개 조립 실험(I/ITSEC 2014 발표)에서, AR 안내는 PDF 설명서에 비해 조립 시간을 약 30% 줄였고 첫 시도 품질이 90% 가까이 좋아졌다. '
        'Boeing 항공기 배선(wire harness) 작업에서는 스마트 안경 안내로 작업 시간이 25% 줄었다. GE Renewable Energy의 풍력 터빈 배선에서는 첫 사용에서 34% 빨라졌다는 보고도 있다. 모두 다른 회사의 결과이며, 이 프로젝트에서 잰 값이 아니다.\n'
        '화면에서 뺀 단서: 이 프로젝트에서 여러 사람을 대상으로 한 작업 시간 · 오류 비교는 아직 하지 않았다(18장 후속 연구 01). 안내 문구의 다른 언어 지원은 문구를 바꾸면 되는 구조라는 뜻이고, 아직 만들지 않았다.')

# ------------------------------------------------------------------ 18 Future Work (새 장: 후속 연구 + 예상되는 상업적 가치)
s = prs.slides.add_slide(S[16].slide_layout)
for ph in list(s.placeholders): ph._element.getparent().remove(ph._element)
s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb(WHITE)
lst = prs.slides._sldIdLst; el = lst[-1]; lst.remove(el); lst.insert(17, el)
header(s, 'Future Work', '상자 하나에서 확인한 구조를, 현장이 쓰는 제품으로 넓힙니다')
sec(s, 71, 100, '후속 연구')
hline(s, 71, 128, 470, color=NAVY, lw=1.25)
fw = [('현장 사용자 평가', '처음 하는 사람들을 대상으로 종이 설명서와 비교해, 작업 시간과 오류 수, 작업 부담을 잽니다.', '기대효과를 숫자로 확인'),
      ('조임 완료 판단', '도구가 닿고 머문 것에 더해, 나사가 끝까지 조여졌는지를 영상과 공구 신호로 판단합니다.', '안내에서 품질 확인까지'),
      ('작업 등록 도구와 마커 없는 추적', '새 부품과 순서를 화면에서 등록하고, 마커 없이 부품을 직접 찾는 방식으로 넓힙니다.', '다른 조립 · 정비 작업으로 확장'),
      ('장비 경량화', '판단을 가볍게 만들어, 노트북 대신 소형 기기나 안경 쪽에서 실행합니다.', '설치 부담과 도입 비용 축소')]
for k, (t_, d_, o_) in enumerate(fw):
    y = 129 + k * 127
    tb(s, 71, y + 12, 44, 28, '0%d' % (k + 1), size=17, color=LBLUE, w8='x', anchor='m')
    tb(s, 123, y + 12, 418, 28, t_, size=15, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, 123, y + 44, 418, 48, d_, size=12, color=BODY, ls=1.4)
    tb(s, 123, y + 95, 418, 20, [[('→  ', {'color': LBLUE}), (o_, {})]], size=11.5, color=NAVY, w8='s', anchor='m', wrap=False)
    if k < 3: hline(s, 71, y + 126, 470)
rect(s, 581, 100, 628, 536, fill=PALE)
sec(s, 605, 114, '예상되는 상업적 가치')
hline(s, 605, 142, 580, color=NAVY, lw=1.25)
biz = [('시장', '40만 대 미만 → 650만 대', 21, '제조 현장으로 나가는 AR 안경의 연간 출하량 전망입니다 (2024 → 2030, 연평균 59% 성장).'),
       ('시점', 'HoloLens 생산 종료 · Guides 지원 종료', 15.5, 'Microsoft는 2024년 말 HoloLens 생산을 멈췄고, 작업 안내 서비스 Dynamics 365 Guides의 지원은 2026년 12월에 끝납니다.'),
       ('비용', '549달러 안경 + 노트북', 21, '소비자용 XR 안경으로 구성했습니다. 산업용 헤드셋 HoloLens 2의 출시가는 3,500달러였습니다.'),
       ('사업 모델', '작업대 단위 구독 + 작업 등록', 15.5, '중소 제조사의 조립 라인, 직업 교육 · 훈련 기관, 정비 · AS 현장부터 시작합니다.')]
for k, (l_, v_, vs, d_) in enumerate(biz):
    y = 143 + k * 123
    tb(s, 605, y + 16, 84, 22, l_, size=11, color=GREY, w8='s', anchor='m')
    tb(s, 693, y + 10, 492, 36, v_, size=vs, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, 693, y + 50, 492, 50, d_, size=12, color=BODY, ls=1.4)
    if k < 3: hline(s, 605, y + 122, 580, color=LBLUE)
tb(s, 71, 660, 1138, 34, ['출처: ABI Research, AR Smart Glasses Shipments in Manufacturing(2026) · Directions on Microsoft(2026. 1. 26)',
                          'Road to VR(2026. 4. 27, VITURE Beast 출시가) · TechRadar(HoloLens 2 출시가)'], size=9, color=LGREY, ls=1.25, name='Source')
note(s, '[후속 연구와 상업적 가치] 왼쪽은 앞으로 할 연구, 오른쪽은 그 연구가 향하는 곳. 왼쪽 네 줄의 화살표가 오른쪽으로 이어진다고 말한다.\n'
        '후속 연구: 01 처음 하는 사람들을 대상으로 종이 설명서와 비교(작업 시간 · 오류 수 · 작업 부담). 02 지금은 도구가 닿고 머문 것(접근 → 유지 → 이탈)으로 판단하므로, 조임 완료 자체를 판단하도록 넓힌다. '
        '03 지금은 한 종류의 상자와 마커 작업대다. 새 작업을 등록하는 도구와 마커 없는 추적으로 대상을 넓힌다. 04 지금은 Windows 노트북에서 판단한다.\n'
        '상업적 가치: 시장 — ABI Research는 제조 분야 AR 안경의 연간 출하량이 2024년 40만 대 미만에서 2030년 650만 대로, 연평균 59% 늘 것으로 본다(제조는 소비자 다음으로 큰 분야). '
        '참고로 Spherical Insights는 제조 분야 AR 시장을 2025년 264.8억 달러에서 2035년 1,598.7억 달러(연평균 19.7%)로 전망한다. '
        '시점 — Microsoft는 2024년 말 HoloLens 생산을 멈췄고, 2025년 12월에 Dynamics 365 Guides와 Remote Assist의 지원 종료(2026년 12월)를 알렸으며 후속 제품은 발표하지 않았다. '
        '비용 — 이 프로젝트의 안경 VITURE Beast는 2026년 4월 27일 549달러에 출시됐다. HoloLens 2의 출시가는 3,500달러였다. 헤드셋은 단독으로 동작하고, 이 프로젝트는 노트북이 더 필요하다는 점은 다르다. '
        '사업 모델 — 작업대 단위 구독과 작업 등록 서비스, 대상 고객 세 곳은 예상이며 확인한 수요가 아니다.\n'
        '비슷한 방향의 상용 제품: PTC Vuforia Step Check(2023, AI로 조립 상태를 검사해 합격 · 불합격을 표시). 질문이 나오면 "고가 장비가 아닌 소비자용 안경에서, 검사가 아니라 작업 단계의 진행을 따라간다"는 점을 말한다.')

# ------------------------------------------------------------------ 노트의 장 번호 (사용자가 장 순서를 바꾼 것에 맞춤)
S2 = list(prs.slides); assert len(S2) == 20 and title_of(S2[17]) == ['Future Work']
renote(S2[6], '14장까지', '13장까지')
renote(S2[13], '12장에 있다', '11장에 있다')

# ------------------------------------------------------------------ 20 Memo
s = S2[19]; assert title_of(s) == ['Memo']; clear(s)
header(s, 'Memo', '구조 테스트 메모 — 영상에는 넣지 않는 장')
rect(s, 71, 100, 1138, 30, fill=PALE)
for x, w, t_ in [(87, 110, '장'), (200, 300, '내용'), (510, 690, '바뀐 것 · 확인할 것')]:
    tb(s, x, 100, w, 30, t_, size=11.5, color=NAVY, w8='x', anchor='m')
mm = [('2', '목차', 'v9: 06을 "시연, 결과와 가치"로 바꿈'),
      ('6 · 7', '전체 아키텍처, 세 가지 문제', 'HMM은 도식대로, 실시간에서 돈다는 전제 → 아래 둘째 줄'),
      ('11 · 12', '양안 투영, 보정과 확인', '11장 위쪽 그림은 작업대 사진에 Unity 화면을 얹은 재현'),
      ('13 · 14', '가림과 복구, 실제 시연', '13장 영상은 0:30 ~ 0:38, 14장은 나사 B · C 구간만 2배속 (1분 36초)'),
      ('15', '관제 화면', '메뉴 설명 가운데 작업 기록 · 연결·진단 · 설정은 이름을 보고 쓴 것 → 확인'),
      ('16', '평가와 결과', 'v9: 두 장을 한 장으로. "사용하면서 고친 것"은 발표자 노트로 옮김. 61.3%가 session 17의 값인지 → 확인'),
      ('17', '기대효과', 'v9 새 장. 위의 수치 셋과 아래 선행 사례는 출처를 확인한 값. "누구에게 무엇을" 세 칸은 제가 쓴 문장 → 확인'),
      ('18', '후속 연구 · 상업적 가치', 'v9 새 장. 시장 · 시점 · 비용은 출처를 확인한 값. 후속 연구 네 줄과 사업 모델은 제가 쓴 문장 → 확인')]
for k, (n, a_, b_) in enumerate(mm):
    y = 130 + k * 36
    tb(s, 87, y, 110, 36, n, size=11.5, color=ORANGE, w8='x', anchor='m')
    tb(s, 200, y, 300, 36, a_, size=11, color=TXT, anchor='m')
    tb(s, 510, y, 690, 36, b_, size=11, color=BODY, anchor='m', ls=1.2)
    hline(s, 71, y + 36, 1138)
tb(s, 71, 432, 1138, 220, ['· 화면에서 뺀 단서는 장마다 발표자 노트에 "화면에서 뺀 단서"로 남겨 둠: 촬영용 설정(초록 안내 2초 뒤 자동 전환), 조임 품질을 재지 않는다는 점, 꺼진 시간 38초, 아직 재지 못한 항목',
                           '· HMM: "실시간에서 돌아간다"는 전제로 6 · 9장에 적었음. 코덱스 구성안에는 "현재 실시간 단계 전이를 HMM이 직접 수행한다고 설명하지 않는다"는 줄이 있으므로 답할 문장을 정해 둘 것',
                           '· 94.1%: 그리드 서치를 같은 세션에서 했다면 그렇게 말해야 함. mAP 94.0%는 5월 학습본(3종 재학습 전)의 값. 개선 전 가림 로그가 있으면 13장을 전후 비교로 바꿈',
                           '· 17 · 18장의 외부 수치: 고용노동부 직종별사업체노동력조사(2026. 6. 30), 고용허가제 자료(2026. 7 기준, SBS Biz 2026. 9. 2 보도), Boeing · Iowa State(I/ITSEC 2014), ABI Research(2026), Directions on Microsoft(2026. 1. 26), Road to VR(2026. 4. 27). 선행 사례의 수치는 다른 회사의 결과이며 이 프로젝트에서 잰 값이 아님',
                           '· 17 · 18장에는 사진이 없음. 사람이나 현장 사진을 넣고 싶으면 후보를 장 크기로 보여 드림',
                           '· 사진: 2 · 3장 Unsplash @maciejka_dslr, 4장 @shaikhulud · @tomspentys, 표지의 안경은 VITURE 제품 이미지, 8장은 1학기 발표 자료의 화면. 글꼴은 Pretendard Bold를 쓰지 않음'], size=10.5, color=BODY, ls=1.4)
prs.save(OUT); print('saved', OUT, len(prs.slides))
