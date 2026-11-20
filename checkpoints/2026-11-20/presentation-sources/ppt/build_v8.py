# -*- coding: utf-8 -*-
"""사용자가 올린 v7(user_v7/u.pptx, 19장)을 그대로 두고 장별로 디자인만 손본다 → v8.
3 Motivation(핵심 목표의 번호 원 → 숫자와 윗줄), 9 Dataset(아래 블록 간격), 11 Example(번호 원 → 숫자),
13 Calibration(스테레오 그림을 덱 색과 글꼴로 다시 그림), 16 Evaluation(줄머리에 그림), 19 Memo(장 번호 갱신)."""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip
from pptx import Presentation
W_ = '/home/claude/grad'; PR3 = W_ + '/prep_t3/'; PV = W_ + '/prep_v8/'; BODY = '333333'; BLACK = '0B0F14'
SRC = W_ + '/user_v7/u.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v8.pptx'
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
def kicker(s, text): tb(s, 50, 24, 400, 18, text, size=10.5, color=ORANGE, w8='x', anchor='m')
def arw(s, x, y, color=LBLUE, size=15, h=28, w=26): tb(s, x, y, w, h, '→', size=size, color=color, w8='s', align='c', anchor='m', wrap=False)

# ------------------------------------------------------------------ 3 Motivation
s = S[2]; assert title_of(s) == ['Motivation']; clear(s)
header(s, 'Motivation', '설명서를 보지 않아도, 작업 위치에서 다음 행동을 알 수 있게')
pic(s, PR3 + 'mot.jpg', 71, 108, 440, 360)
rows = [('배경', '조립 작업은 설명서에 의존합니다', '익숙하지 않은 작업자는 설명서와 부품을 번갈아 확인하며 순서를 따라갑니다.'),
        ('문제', '손을 멈추는 사이 순서를 놓칩니다', '시선이 설명서와 작업대를 오가고, 어디까지 했는지 다시 찾아야 합니다.'),
        ('목표', '작업 위치에서 다음 행동을 확인합니다', '작업할 위치와 다음 행동을 AR 안경으로 눈앞에 보여줍니다.')]
for k, (lab, t_, d_) in enumerate(rows):
    y = 112 + k * 124
    chip(s, 545, y + 6, lab, fill=NAVY if k == 2 else PALE, color=WHITE if k == 2 else NAVY, size=11, w=56, h=26, w8='x')
    tb(s, 617, y, 590, 38, t_, size=19, color=NAVY, w8='x', anchor='m')
    tb(s, 617, y + 44, 590, 48, d_, size=13.5, color=BODY, ls=1.45)
    if k < 2: hline(s, 545, y + 106, 664)
tb(s, 71, 500, 300, 26, '핵심 목표', size=13, color=ORANGE, w8='x', anchor='m')
for k, (t_, d_) in enumerate([('작업 위치에 직접 안내', '마커로 계산한 위치에 목표를 표시합니다.'), ('작업 단계를 따라가는 안내', '도구의 움직임을 보고 다음 단계로 넘어갑니다.'), ('혼자서도 쓸 수 있는 구성', '안경과 노트북으로 시작하고 끝냅니다.')]):
    x = 71 + k * 385
    hline(s, x, 538, 368, color=NAVY, lw=1.25)
    tb(s, x, 552, 46, 40, '0%d' % (k + 1), size=21, color=LBLUE, w8='x', anchor='m')
    tb(s, x + 52, 552, 316, 40, t_, size=17.5, color=NAVY, w8='x', anchor='m')
    tb(s, x + 52, 596, 316, 26, d_, size=13, color=BODY, anchor='m')

# ------------------------------------------------------------------ 9 Dataset : '규모' 아래 블록을 조금 내림
s = S[8]; assert title_of(s) == ['Dataset']
for sh in s.shapes:
    if px(416) <= sh.top < px(660): sh.top = sh.top + px(8)

# ------------------------------------------------------------------ 11 Example : 번호 원 → 숫자
s = S[10]; assert title_of(s) == ['Example']; clear(s)
header(s, 'Example', '나사 A 하나로 처리 과정을 따라가 봅니다'); kicker(s, '문제 1 · 단계 인식')
lead(s, '시연 영상의 실제 화면입니다. 노란 표시가 지금 작업할 나사이고, 검은 줄은 그때 안경에 나온 문구입니다.', y=96, h=30)
ex = [(38, '목표 표시', 'A 위치에 노란 표시를 올립니다.', '나사 A · 1/4', 'FFFFFF'),
      (43, '접근', '드라이버 끝이 A에 가까워집니다.', '드라이버 끝을 나사 A에 맞춰주세요', 'EBBD5B'),
      (46, '유지', '일정 시간 머물면 작업 중으로 봅니다.', '나사 A를 조여주세요', '59C9E6'),
      (50, '전환', '초록 안내 뒤 B로 넘어갑니다.', '드라이버를 떼어주세요', '5CEE89')]
for k, (t, a_, b_, ph, pc) in enumerate(ex):
    x = 71 + k * 288.7
    pic(s, PR3 + 'ex%d.jpg' % t, x, 134, 272, 230)
    rect(s, x, 364, 272, 4, fill=NAVY)
    tb(s, x, 379, 40, 34, '0%d' % (k + 1), size=18, color=LBLUE, w8='x', anchor='m')
    tb(s, x + 42, 379, 226, 34, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, x, 420, 272, 26, b_, size=13, color=BODY, anchor='m')
    r = rect(s, x, 458, 272, 32, fill=BLACK, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .5
    tb(s, x, 458, 272, 32, ph, size=11, color=pc, w8='s', align='c', anchor='m', wrap=False)
    if k < 3: arw(s, x + 272, 234, color=NAVY, size=13, w=17)
rect(s, 71, 518, 1138, 114, fill=PALE)
for k, (a_, b_) in enumerate([('위치', '마커에서 계산한 A의 좌표'), ('관측', '드라이버 끝과 A 사이의 거리'), ('판단', '접근과 유지가 이어지면 다음 나사로')]):
    x = 99 + k * 372
    tb(s, x, 528, 80, 94, a_, size=14, color=ORANGE, w8='x', anchor='m')
    tb(s, x + 70, 528, 290, 94, b_, size=15, color=NAVY, w8='x', anchor='m')

# ------------------------------------------------------------------ 13 Calibration : 그림만 교체
s = S[12]; assert title_of(s) == ['Calibration']
pics = [sh for sh in s.shapes if sh.shape_type == 13]; assert len(pics) == 1
drop_pic(s, pics[0])
pic(s, PV + 'stereo_geo_redraw.png', 71, 96, 440, 300)

# ------------------------------------------------------------------ 16 Evaluation : 줄머리에 그림
s = S[15]; assert title_of(s) == ['Evaluation']; clear(s)
header(s, 'Evaluation', '무엇을 어떤 조건에서 확인했는지 나눠서 봅니다')
for x, w, t_ in [(253, 150, '확인한 것'), (412, 300, '조건'), (722, 350, '결과'), (1090, 110, '방법')]:
    tb(s, x, 104, w, 34, t_, size=12, color=GREY, w8='x', anchor='m')
hline(s, 71, 138, 1138, color=NAVY, lw=1.25)
ev = [('ev1.jpg', '오프라인 인식', ['1학기 · Quest 3로 찍은 session 17', '119프레임을 정답 라벨과 비교'], 'HMM 정확도 94.1%', '프레임별 판단 88.2%, FSM 91.6%', '정답 라벨 비교', NAVY, WHITE, 112),
      ('ev2.jpg', '실시간 동작', ['2학기 · take4 시연 (2분 1초)', '일곱 단계를 처음부터 끝까지'], '일곱 단계가 순서대로 진행', '10번 가려지고, 10번 모두 하던 단계에서 이어 감', '시연 기록', PALE, NAVY, 84),
      ('ev3.jpg', '착용 정합', ['2학기 · 2026. 11. 14 · 같은 착용 상태', '착용자가 눈으로 확인'], '나사 A ~ D 모두 대체로 하나로 겹침', '거리와 시점을 바꿔 가며 확인', '착용 확인', PALE, NAVY, 84)]
for k, (im, a_, c_, r1, r2, kind, cf, cc, cw) in enumerate(ev):
    y = 138 + k * 100
    pic(s, PV + im, 87, y + 8, 150, 84)
    tb(s, 253, y, 150, 100, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, 412, y, 300, 100, c_, size=13, color=BODY, anchor='m', ls=1.45)
    tb(s, 722, y + 20, 356, 30, r1, size=16.5, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, 722, y + 54, 356, 26, r2, size=13, color=BODY, anchor='m')
    chip(s, 1090, y + 37, kind, fill=cf, color=cc, size=10.5, w=cw, h=26, w8='x')
    hline(s, 71, y + 100, 1138)
tb(s, 71, 466, 400, 26, '사용하면서 고친 것', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 71, 498, 1138, color=NAVY, lw=1.25)
ut = [('상태 설명이 많아 지금 할 일을 찾기 어려움', '큰 행동 문구 한 줄과 목표 강조로 정리'), ('영문 상태 문구가 낯섦', '한글 행동 문구로 변경')]
for k, (a_, b_) in enumerate(ut):
    y = 498 + k * 60
    tb(s, 87, y, 520, 60, a_, size=14.5, color=BODY, anchor='m')
    arw(s, 615, y + 16, color=NAVY, size=14)
    tb(s, 655, y, 540, 60, b_, size=14.5, color=NAVY, w8='x', anchor='m')
    hline(s, 71, y + 60, 1138)

# ------------------------------------------------------------------ 19 Memo : 장 번호를 지금 덱에 맞춤
s = S[18]; assert title_of(s) == ['Memo']; clear(s)
header(s, 'Memo', '구조 테스트 메모 — 영상에는 넣지 않는 장')
rect(s, 71, 100, 1138, 30, fill=PALE)
for x, w, t_ in [(87, 110, '장'), (200, 300, '내용'), (510, 690, '바뀐 것 · 확인할 것')]:
    tb(s, x, 100, w, 30, t_, size=11.5, color=NAVY, w8='x', anchor='m')
mm = [('3', '개발 동기', 'v8: 핵심 목표의 번호 원을 숫자와 윗줄로 바꿈'),
      ('4 · 5 · 6', '비교표, 개요, 관제 화면', '비교표는 사진 머리로 다시 디자인. 6장 메뉴 설명 가운데 작업 기록 · 연결·진단 · 설정은 이름을 보고 쓴 것 → 확인'),
      ('7 · 8', '전체 아키텍처, 세 가지 문제', 'HMM은 도식대로, 실시간에서 돈다는 전제 → 아래 셋째 줄. 8장은 고쳐 주신 문구 그대로'),
      ('9', '데이터와 모델', 'v8: "규모" 아래 간격을 조금 띄움. 넷째 칸은 1학기 검출 영상 10초'),
      ('10 · 11', '비교 실험, 나사 A로 따라가기', 'v8: 11장의 번호 원을 숫자로 바꿈'),
      ('12 · 13', '양안 투영, 보정과 확인', 'v8: 13장 그림을 덱 색과 글꼴로 다시 그림 (내용은 주신 그림 그대로). 12장의 "재현 이미지" 표시는 빼신 대로 둠'),
      ('14 · 15', '가림과 복구, 실제 시연', '14장 영상은 0:30 ~ 0:38, 15장은 나사 B · C 구간만 2배속 (1분 36초)'),
      ('16', '검증 결과', 'v8: 줄마다 그림을 붙임 (1학기 검출 화면, 시연 장면, 좌우 눈 화면을 겹친 그림)'),
      ('17', '성과', '"다음 단계" 둘째 줄(다른 작업대로 확장)은 제가 쓴 문장 → 확인')]
for k, (n, a_, b_) in enumerate(mm):
    y = 130 + k * 38
    tb(s, 87, y, 110, 38, n, size=11.5, color=ORANGE, w8='x', anchor='m')
    tb(s, 200, y, 300, 38, a_, size=11, color=TXT, anchor='m')
    tb(s, 510, y, 690, 38, b_, size=11, color=BODY, anchor='m', ls=1.2)
    hline(s, 71, y + 38, 1138)
tb(s, 71, 484, 1138, 160, ['· 화면에서 뺀 단서는 장마다 발표자 노트에 "화면에서 뺀 단서"로 남겨 둠: 촬영용 설정(초록 안내 2초 뒤 자동 전환), 조임 품질을 재지 않는다는 점, 꺼진 시간 38초, 아직 재지 못한 항목, 한계 다섯 줄',
                           '· 남아 있는 표시: "재현 영상"(14 · 15장), "session 17 한 세션"(10 · 16 · 17장), 확인 날짜와 "착용자가 확인"(13 · 16장). 12장 위쪽 그림은 작업대 사진에 Unity 화면을 얹은 재현',
                           '· HMM: "실시간에서 돌아간다"는 전제로 7 · 10장에 적었음. 코덱스 구성안에는 "현재 실시간 단계 전이를 HMM이 직접 수행한다고 설명하지 않는다"는 줄이 있으므로 답할 문장을 정해 둘 것',
                           '· 94.1%: 그리드 서치를 같은 세션에서 했다면 그렇게 말해야 함. mAP 94.0%는 5월 학습본(3종 재학습 전)의 값. 개선 전 가림 로그가 있으면 14장을 전후 비교로 바꿈',
                           '· 사진: 2 · 3장 Unsplash @maciejka_dslr, 4장 @shaikhulud · @tomspentys, 표지의 안경은 VITURE 제품 이미지, 9장은 1학기 발표 자료의 화면. 글꼴은 Pretendard Bold를 쓰지 않음'], size=10.5, color=BODY, ls=1.45)

# ------------------------------------------------------------------ 노트의 장 번호 (관제 화면 장이 하나 늘어 뒤가 하나씩 밀림)
fix = {8: [('여기서부터 13장까지', '여기서부터 14장까지')], 15: [('실제 안경 화면은 11장에 있다', '실제 안경 화면은 12장에 있다')], 17: [('7장의 세 문제', '8장의 세 문제')]}
for n, pairs in fix.items():
    tf = S[n - 1].notes_slide.notes_text_frame; t = tf.text
    for a, b in pairs:
        assert a in t, (n, a); t = t.replace(a, b)
    tf.text = t
prs.save(OUT); print('saved', OUT, len(prs.slides))
