# -*- coding: utf-8 -*-
"""AI Assembly Guide — 구조 테스트 덱. 참고 영상(시커즈 발표)의 전개를 따른다:
동기 → 문제와 해결 → 비교 → 개요 → 아키텍처 → 파이프라인 → 예시 → 구현 화면 → 시연 → 평가 → 성과와 한계.
글꼴은 Pretendard r/m/s/x 만 쓴다 (Bold는 파일에 들어 있지 않아 PowerPoint 저장이 막힌다).
"""
import sys, os, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip, numcircle
import numpy as np
from PIL import Image

W_ = '/home/claude/grad'
A = '/mnt/user-data/uploads/AI_Assembly_Video_Pack_20261115/'
P = W_ + '/photo/'; P5 = W_ + '/prep5/'; TV = W_ + '/tv/full/'; PR = W_ + '/prep_t/'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v1.pptx'
BODY = '333333'; BLACK = '0B0F14'

def cover(src, w, h, fx=.5, fy=.5, scale=2, box=None):
    im = (Image.open(src) if isinstance(src, str) else src).convert('RGB')
    if box: im = im.crop(box)
    Wd, Hd = int(w * scale), int(h * scale)
    r = max(Wd / im.width, Hd / im.height); im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x = int((im.width - Wd) * fx); y = int((im.height - Hd) * fy); return im.crop((x, y, x + Wd, y + Hd))

def shade(im, left=0, flat=0, c=(22, 38, 64)):
    a = np.asarray(im).astype(np.float32); w = a.shape[1]
    k = np.clip(flat + left * np.clip(1 - np.linspace(0, 1, w)[None, :, None] / .72, 0, 1) ** 1.3, 0, .96)
    return Image.fromarray((a * (1 - k) + np.array(c, np.float32)[None, None, :] * k).astype(np.uint8))

IMG = {}
def sv(name, im, q=90):
    IMG[name] = PR + name + '.jpg'; im.save(IMG[name], quality=q); return IMG[name]

BOX = (360, 110, 1000, 590)                       # 테스트 영상에서 상자 둘레만 (4:3)
for t in (58, 66, 70, 74):
    sv('ex%d' % t, cover(TV + 't%d.jpg' % t, 272, 204, box=BOX))
for t in (10, 46, 58, 86, 102, 128, 150):
    sv('fl%d' % t, cover(TV + 't%d.jpg' % t, 272, 153))
sv('ov', cover(TV + 't58.jpg', 484, 272))
sv('scr1', cover(TV + 't86.jpg', 368, 207))
sv('scr2', cover(A + '04_관제/관제_B_저장상태_발표용.png', 368, 207, fy=0), 92)
sv('scr3', cover(A + '04_관제/노트북_실행준비_화면.png', 368, 207, fy=0), 92)
sv('p3', cover(TV + 't70.jpg', 368, 150, fy=.45))
sv('p1', cover(A + '03_AI_검출/검출_aruco.png', 368, 150, fy=.6))
sv('p2', cover(A + '03_AI_검출/검출_yolo.png', 368, 150, fy=.3))
sv('mot', cover(P + 'maciejka_dslr-manual_blocks.jpg', 440, 330))
sv('poster', Image.open(TV + 't70.jpg').convert('RGB'))
sv('close', shade(cover(TV + 't150.jpg', 1280, 720), left=.75, flat=.45))

d = Deck(out=OUT)
NOTES = []
def new(note=''):
    NOTES.append(note); return d.new()

def tag(s, x, y, text, w=None):
    chip(s, x, y, text, fill=ORANGE, color=WHITE, size=10, w=w or (len(text) * 11 + 24), h=24, w8='s')

def arw(s, x, y, color=LBLUE, size=15, h=28, w=26):
    tb(s, x, y, w, h, '→', size=size, color=color, w8='s', align='c', anchor='m', wrap=False)

# ================================================================== 1 표지
s = new('[표지] 참고 영상 0:01 인사에 해당.')
pic(s, P5 + 'cover.jpg', 0, 0, 1280, 720)
tb(s, 85, 92, 700, 28, '졸업프로젝트', size=14, color=LBLUE, w8='s', anchor='m')
rect(s, 85, 128, 40, 2, fill=LBLUE)
tb(s, 85, 150, 640, 130, ['AI Assembly Guide,', '눈앞에서 따라 하는 조립'], size=34, color=WHITE, w8='x', ls=1.18)
tb(s, 85, 296, 640, 30, '작업 단계 인식 기반 AR 조립 안내', size=16, color='D9E2F0', w8='m', anchor='m')
tb(s, 85, 640, 800, 24, '2026. 11   |   최민준 C011207   |   지도교수 윤영 교수님', size=12, color='D9E2F0')

# ================================================================== 2 목차
s = new('[목차] 참고 영상 0:17 "배경과 개요 → 시스템 설계 → 구현 결과 → 성능 평가 → 성과와 한계" 순서.')
pic(s, P5 + 'toc.jpg', 0, 0, 527, 720)
tb(s, 580, 44, 600, 42, 'Contents', size=20, color=NAVY, w8='x', anchor='m')
toc = [('01', '프로젝트 배경과 개요', '개발 동기, 기존 방식의 문제와 해결, 비교, 개요'),
       ('02', '시스템 구성', '전체 아키텍처'),
       ('03', '단계 인식 방식', '세 단계 처리 과정, 나사 A로 따라가기'),
       ('04', '구현 결과', '구현 화면, 시연, 일곱 단계'),
       ('05', '평가', '확인 항목, 사용성 피드백과 개선'),
       ('06', '성과와 한계', '성과 세 가지, 남은 한계')]
for k, (n, t_, sub) in enumerate(toc):
    y = 108 + k * 96
    tb(s, 580, y, 90, 52, n, size=28, color=LBLUE, w8='x', anchor='m')
    tb(s, 672, y - 2, 500, 30, t_, size=18, color=NAVY, w8='x', anchor='m')
    tb(s, 672, y + 28, 520, 22, sub, size=11.5, color=GREY, anchor='m')
    hline(s, 580, y + 72, 630)

# ================================================================== 3 개발 동기
s = new('[개발 동기] 참고 영상 0:29~1:04. 배경 → 문제 → 목표 → 핵심 목표 세 가지.')
header(s, 'Motivation', '설명서를 보지 않아도, 작업 위치에서 다음 행동을 알 수 있게')
pic(s, IMG['mot'], 71, 110, 440, 330)
rows = [('배경', '조립 작업은 설명서에 의존합니다', '익숙하지 않은 작업자는 설명서와 부품을 번갈아 확인하며 순서를 따라갑니다.'),
        ('문제', '손을 멈추는 사이 순서를 놓칩니다', '시선이 설명서와 작업대를 오가고, 어디까지 했는지 다시 찾아야 합니다.'),
        ('목표', '작업 위치에서 다음 행동을 확인합니다', '작업할 위치와 다음 행동을 AR 안경으로 눈앞에 보여줍니다.')]
for k, (lab, t_, d_) in enumerate(rows):
    y = 110 + k * 112
    chip(s, 545, y + 4, lab, fill=NAVY if k == 2 else PALE, color=WHITE if k == 2 else NAVY, size=11, w=56, h=26, w8='x')
    tb(s, 617, y, 590, 34, t_, size=18, color=NAVY, w8='x', anchor='m')
    tb(s, 617, y + 38, 590, 44, d_, size=13, color=BODY, ls=1.4)
    if k < 2: hline(s, 545, y + 96, 664)
hline(s, 71, 470, 1138)
tb(s, 71, 484, 300, 24, '핵심 목표', size=12.5, color=ORANGE, w8='x', anchor='m')
for k, (t_, d_) in enumerate([('작업 위치에 직접 안내', '마커로 계산한 위치에 목표를 표시합니다.'), ('작업 단계를 따라가는 안내', '도구의 움직임을 보고 다음 단계로 넘어갑니다.'), ('혼자서도 쓸 수 있는 구성', '안경과 노트북, 관제 화면으로 시작하고 끝냅니다.')]):
    x = 71 + k * 385
    numcircle(s, x, 524, k + 1, d=28)
    tb(s, x + 40, 520, 320, 34, t_, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, x + 40, 556, 320, 24, d_, size=12, color=BODY, anchor='m')
hline(s, 71, 606, 1138)

# ================================================================== 4 문제와 해결
s = new('[기존 방식의 문제와 해결] 참고 영상 1:04~1:47. 문제 세 가지를 각각의 해결과 짝지어 말한다.')
header(s, 'Approach', '기존 방식의 문제 세 가지와 해결 방법')
ps = [('안내가 작업 위치와 떨어져 있습니다', '설명서나 화면을 보려면 작업대에서 눈을 떼야 합니다.',
       '작업 위치 위에 안내를 겹쳐 표시', 'ArUco 마커로 작업대의 좌표를 잡고, 나사 A ~ D의 위치를 화면에 투영합니다.'),
      ('다음 단계는 작업자가 직접 넘겨야 합니다', '페이지를 넘기거나 화면을 누르려면 손을 멈춰야 합니다.',
       '도구의 움직임을 보고 단계를 넘김', 'YOLO로 드라이버를 찾고, 목표 나사에 접근 · 유지 · 이탈하면 다음 나사로 넘어갑니다.'),
      ('한 장면만 보고 판단하면 잘못 넘어갑니다', '도구가 스쳐 지나가거나 잠깐 가려지는 순간이 있습니다.',
       '이어진 관측으로 판단', '유지와 이탈이 일정 시간 확인될 때만 전환하고, 관측이 끊기면 진행을 보존합니다.')]
for k, (pt, pd, st, sd) in enumerate(ps):
    y = 108 + k * 138
    rect(s, 71, y, 510, 128, line=LINE, lw=1)
    tb(s, 95, y + 14, 200, 20, '문제 %d' % (k + 1), size=11, color=GREY, w8='x', anchor='m')
    tb(s, 95, y + 34, 470, 30, pt, size=16.5, color=TXT, w8='x', anchor='m')
    tb(s, 95, y + 70, 470, 46, pd, size=12.5, color=BODY, ls=1.4)
    arw(s, 587, y + 47, color=NAVY, size=20, h=34, w=46)
    rect(s, 639, y, 570, 128, fill=PALE); rect(s, 639, y, 4, 128, fill=NAVY)
    tb(s, 667, y + 14, 200, 20, '해결', size=11, color=ORANGE, w8='x', anchor='m')
    tb(s, 667, y + 34, 520, 30, st, size=16.5, color=NAVY, w8='x', anchor='m')
    tb(s, 667, y + 70, 520, 46, sd, size=12.5, color=BODY, ls=1.4)
hline(s, 71, 536, 1138); hline(s, 71, 596, 1138)
tb(s, 71, 536, 170, 60, '핵심 차별점', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 240, 536, 960, 60, '위치는 마커로, 단계는 도구의 움직임으로 판단해 작업 위치에 바로 안내합니다.', size=17, color=NAVY, w8='x', anchor='m')

# ================================================================== 5 비교
s = new('[기존 방식과 비교] 참고 영상 1:47~2:20. 표의 구분과 문구는 초안이므로 확인이 필요하다.')
header(s, 'Comparison', '안내가 보이는 곳과 단계를 넘기는 방법이 다릅니다')
cols = [(71, 228, '구분'), (299, 270, '종이 설명서'), (569, 270, '화면 설명서 (태블릿 · 영상)'), (839, 370, 'AI Assembly Guide')]
trs = [('안내가 보이는 곳', '책상 위 설명서', '옆에 둔 화면', '작업 위치 위 (AR 안경)'),
       ('다음 단계로 넘어가기', '직접 페이지를 넘김', '직접 누르거나 재생', '나사 A ~ D는 도구 관측으로 자동 전환'),
       ('작업 중 시선', '설명서와 작업대를 오감', '화면과 작업대를 오감', '작업대에 머묾'),
       ('진행 상황 확인', '작업자가 기억', '작업자가 기억', '관제 화면에 현재 단계와 다음 행동 표시')]
rect(s, 839, 110, 370, 62 + 4 * 84, fill=PALE); rect(s, 839, 110, 370, 4, fill=NAVY)
for (x, w, t_) in cols:
    tb(s, x + 16, 114, w - 24, 58, t_, size=14.5 if x == 839 else 13, color=NAVY if x == 839 else GREY, w8='x', anchor='m')
hline(s, 71, 172, 1138, color=NAVY, lw=1.25)
for r, row in enumerate(trs):
    y = 172 + r * 84
    for c, (x, w, _) in enumerate(cols):
        tb(s, x + 16, y, w - 24, 84, row[c], size=14 if c in (0, 3) else 13, color=NAVY if c in (0, 3) else BODY, w8='x' if c in (0, 3) else 'r', anchor='m', ls=1.35)
    hline(s, 71, y + 84, 1138)
src(s, '상자 배치 · 뚜껑 닫기 · 최종 확인은 작업자가 확인하고 넘어갑니다', y=536)

# ================================================================== 6 개요
s = new('[서비스 개요] 참고 영상 2:20~2:46. 대상 → 처리 흐름 → 제공하는 결과.')
header(s, 'Overview', '카메라 영상에서 위치와 단계를 판단해 안경에 안내합니다')
tb(s, 71, 118, 150, 26, '대상', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 71, 146, 620, 30, '상자 조립 일곱 단계', size=18, color=NAVY, w8='x', anchor='m')
tb(s, 71, 180, 620, 24, '상자 배치 → 뚜껑 닫기 → 나사 A · B · C · D → 최종 확인', size=13, color=BODY, anchor='m')
hline(s, 71, 224, 620)
tb(s, 71, 238, 200, 26, '핵심 처리 흐름', size=13, color=ORANGE, w8='x', anchor='m')
for k, t_ in enumerate(['카메라 영상', '마커로\n위치 계산', '도구 검출', '단계 판단', '안경 · 관제\n전달']):
    x = 71 + k * 127
    r = rect(s, x, 274, 112, 84, fill=NAVY if k == 4 else PALE, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .12
    tb(s, x + 8, 280, 40, 20, '0%d' % (k + 1), size=10.5, color='C5D5E8' if k == 4 else LBLUE, w8='x', anchor='m')
    tb(s, x, 296, 112, 56, t_.split('\n'), size=13, color=WHITE if k == 4 else NAVY, w8='x', align='c', anchor='m', ls=1.25)
    if k < 4: arw(s, x + 111, 302, size=11, w=17)
hline(s, 71, 384, 620)
tb(s, 71, 398, 200, 26, '안내 결과', size=13, color=ORANGE, w8='x', anchor='m')
for k, (a_, b_) in enumerate([('안경', '현재 나사 강조, 상자 · 뚜껑 윤곽, 행동 문구 (개선안)'), ('관제 화면', '현재 작업, 다음 행동, 진행 상태')]):
    y = 432 + k * 44
    tb(s, 71, y, 110, 36, a_, size=15, color=NAVY, w8='x', anchor='m')
    tb(s, 181, y, 510, 36, b_, size=13.5, color=BODY, anchor='m')
pic(s, IMG['ov'], 725, 118, 484, 272)
tb(s, 725, 396, 484, 18, '카메라 미리보기에 안내를 겹친 화면 (테스트 영상)', size=9.5, color=LGREY, anchor='m')
rect(s, 725, 432, 484, 80, fill=PALE)
tb(s, 745, 432, 444, 80, ['청록 선 — 상자와 뚜껑의 윤곽', '노란 표시 — 지금 작업할 나사'], size=13, color=NAVY, w8='s', anchor='m', ls=1.5)

# ================================================================== 7 아키텍처
s = new('[전체 시스템 아키텍처] 참고 영상 2:46~3:49. 확인: 도식은 HMM이 FSM으로 이어지게 그려져 있고, 코덱스 구성안은 오프라인 분석 경로라고 적고 있다.')
header(s, 'Architecture', '카메라 영상에서 안경의 안내까지, 한 흐름으로 이어집니다')
pic(s, P5 + 'arch.png', 71, 100, 1138, 1138 * 732 / 1530)
src(s, 'VITURE Beast · Windows 노트북 · Python 판단 · Unity SBS · 웹 관제', y=664)

# ================================================================== 8 파이프라인
s = new('[핵심 처리 과정 세 단계] 참고 영상 3:49~4:57. 단계마다 무엇을 넣고 무엇이 나오는지 말한다.')
header(s, 'Pipeline', '위치 계산, 도구 관측, 단계 판단의 세 단계로 처리합니다')
pipe = [('위치 계산', 'p1', [('ArUco 검출 · PnP 자세', '등록한 마커로 작업대의 좌표를 잡습니다.'), ('나사 A ~ D 위치 투영', '등록된 나사 위치를 영상 좌표로 옮깁니다.')]),
        ('도구 관측', 'p2', [('YOLO 도구 검출', '영상에서 드라이버를 찾습니다.'), ('도구 끝 · 거리 점수', '도구 끝과 목표 나사 사이의 거리를 봅니다.')]),
        ('단계 판단', 'p3', [('시간 증거 게이트', '접근 → 유지 → 이탈이 이어질 때만 인정합니다.'), ('FSM S0 – S6', '현재 목표와 다음 행동을 정해 안경과 관제에 보냅니다.')])]
for k, (t_, im, boxes) in enumerate(pipe):
    x = 71 + k * 385
    numcircle(s, x, 110, k + 1, d=30, size=13)
    tb(s, x + 42, 108, 320, 34, t_, size=19, color=NAVY, w8='x', anchor='m')
    pic(s, IMG[im], x, 154, 368, 150)
    for j, (a_, b_) in enumerate(boxes):
        y = 320 + j * 104
        rect(s, x, y, 368, 90, fill=PALE)
        tb(s, x + 18, y + 12, 332, 28, a_, size=15, color=NAVY, w8='x', anchor='m')
        tb(s, x + 18, y + 44, 332, 36, b_, size=12, color=BODY, ls=1.35)
        if j == 0: tb(s, x, y + 87, 368, 20, '↓', size=12, color=LBLUE, w8='s', align='c', anchor='m')
    if k < 2: arw(s, x + 367, 208, color=NAVY, size=15, w=19)
src(s, '왼쪽 · 가운데 그림은 2026년 5월 개발 영상의 검출 결과, 오른쪽은 테스트 영상', y=624)

# ================================================================== 9 예시
s = new('[예시로 따라가기] 참고 영상 4:57~5:56. 사례 하나(여기서는 나사 A)로 처리 과정을 처음부터 끝까지 보여준다.')
header(s, 'Example', '나사 A 하나로 처리 과정을 따라가 봅니다')
lead(s, '테스트 영상의 실제 화면입니다. 노란 표시가 지금 작업할 나사입니다.', y=96, h=30)
ex = [(58, '목표 표시', 'A의 위치를 계산해 노란 표시를 올립니다.'), (66, '접근', '드라이버 끝이 A에 가까워집니다.'), (70, '유지', '일정 시간 머물면 작업 중으로 봅니다.'), (74, '이탈 · 전환', '도구가 떠나면 목표가 B로 넘어갑니다.')]
for k, (t, a_, b_) in enumerate(ex):
    x = 71 + k * 288.7
    pic(s, IMG['ex%d' % t], x, 140, 272, 204)
    rect(s, x, 344, 272, 4, fill=NAVY)
    numcircle(s, x, 364, k + 1, d=28)
    tb(s, x + 38, 361, 230, 34, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, x, 402, 272, 44, b_, size=12.5, color=BODY, ls=1.4)
    if k < 3: arw(s, x + 272, 228, color=NAVY, size=13, w=17)
rect(s, 71, 470, 1138, 96, fill=PALE)
for k, (a_, b_) in enumerate([('위치', '마커에서 계산한 A의 좌표'), ('관측', '드라이버 끝과 A 사이의 거리'), ('판단', '유지와 이탈이 확인되면 다음 나사로')]):
    x = 99 + k * 372
    tb(s, x, 482, 80, 72, a_, size=14, color=ORANGE, w8='x', anchor='m')
    tb(s, x + 70, 482, 290, 72, b_, size=14.5, color=NAVY, w8='x', anchor='m')
src(s, '안내는 도구의 접근 · 유지 · 이탈을 본 결과이며, 조임 품질을 측정한 것이 아닙니다', y=624)

# ================================================================== 10 구현 화면
s = new('[구현 화면] 참고 영상 5:56~6:34. 화면마다 무엇을 볼 수 있는지 한 문장씩.')
header(s, 'Screens', '안내 표시와 관제 화면으로 구성했습니다')
scr = [('scr1', '안내 표시', '작업할 나사를 노란 표시로 강조하고, 상자와 뚜껑은 윤곽으로 보여줍니다.', '카메라 미리보기 (테스트 영상)'),
       ('scr2', '관제 화면', '현재 작업, 다음 행동, 진행 상태를 한 화면에서 확인합니다.', '저장 상태를 다시 재생한 화면'),
       ('scr3', '준비 화면', '안경 연결을 확인하고 작업을 시작하고 끝냅니다.', '실행 전 화면')]
for k, (im, a_, b_, c_) in enumerate(scr):
    x = 71 + k * 385
    rect(s, x - 1, 127, 370, 20, fill='1B2430')
    for j in range(3): rect(s, x + 9 + j * 13, 133, 7, 7, fill=('E0685F', 'E5B94A', '5FBF6B')[j], shape=MSO_SHAPE.OVAL)
    pic(s, IMG[im], x, 147, 368, 207)
    rect(s, x - 1, 127, 370, 228, line=LINE, lw=.75)
    tb(s, x, 372, 368, 34, a_, size=18, color=NAVY, w8='x', anchor='m')
    tb(s, x, 410, 360, 48, b_, size=13, color=BODY, ls=1.4)
    tb(s, x, 466, 368, 18, c_, size=9.5, color=LGREY, anchor='m')
hline(s, 71, 516, 1138); hline(s, 71, 586, 1138)
tb(s, 71, 516, 120, 70, '역할', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 190, 516, 1010, 70, '작업자는 눈앞의 안내를 따라가고, 관제 화면에서는 전체 진행을 확인합니다.', size=17, color=NAVY, w8='x', anchor='m')

# ================================================================== 11 시연
s = new('[실제 시연] 참고 영상 6:34~8:11. 영상은 한 번만 재생하고, 단계가 바뀌는 순간에 말을 맞춘다.')
header(s, 'Demo', '상자 하나를 처음부터 끝까지 조립합니다')
s.shapes.add_movie(PR + 'demo.mp4', px(71), px(108), px(800), px(450), poster_frame_image=IMG['poster'], mime_type='video/mp4')
tb(s, 71, 564, 800, 18, '테스트 영상 (2분 56초 · 소리 없음) · 카메라 미리보기에 안내를 겹친 화면', size=9.5, color=LGREY, anchor='m')
tb(s, 899, 108, 310, 26, '영상에서 볼 곳', size=13, color=ORANGE, w8='x', anchor='m')
for k, (tm, a_) in enumerate([('0:00', '상자 놓을 자리 표시'), ('0:27', '상자를 놓음'), ('0:48', '나사 A'), ('1:14', '나사 B'), ('1:34', '나사 C'), ('2:04', '나사 D'), ('2:22', '최종 확인')]):
    y = 142 + k * 58
    tb(s, 899, y, 70, 46, tm, size=15, color=LBLUE, w8='x', anchor='m')
    tb(s, 969, y, 240, 46, a_, size=15, color=NAVY, w8='x', anchor='m')
    hline(s, 899, y + 52, 310)
src(s, '시간은 대략이며, 최종 영상에 맞춰 고칩니다', y=624)

# ================================================================== 12 일곱 단계
s = new('[일곱 단계] 시연에 이어 단계별 화면을 한 장에 정리한다. 참고 영상에는 없는 장.')
header(s, 'Flow', '일곱 단계가 화면에서 이렇게 보입니다')
fl = [(10, '상자 배치', '놓을 자리의 윤곽', 'u'), (46, '뚜껑 닫기', '뚜껑의 윤곽', 'u'), (58, '나사 A', '왼쪽 위', 'a'), (86, '나사 B', '오른쪽 위', 'a'),
      (102, '나사 C', '왼쪽 아래', 'a'), (128, '나사 D', '오른쪽 아래', 'a'), (150, '최종 확인', '전체 윤곽', 'u')]
for k, (t, a_, b_, kind) in enumerate(fl):
    x = 71 + (k % 4) * 288.7; y = 108 + (k // 4) * 232
    pic(s, IMG['fl%d' % t], x, y, 272, 153)
    if kind == 'a': numcircle(s, x, y + 165, k + 1, d=26, size=11.5)
    else:
        rect(s, x, y + 165, 26, 26, fill=WHITE, line=NAVY, lw=1.5, shape=MSO_SHAPE.OVAL)
        tb(s, x, y + 165, 26, 26, str(k + 1), size=11.5, color=NAVY, w8='x', align='c', anchor='m', wrap=False)
    tb(s, x + 36, y + 162, 150, 32, a_, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, x + 150, y + 162, 122, 32, b_, size=11.5, color=GREY, align='r', anchor='m')
x = 71 + 3 * 288.7
rect(s, x, 340, 272, 153, fill=PALE)
numcircle(s, x + 18, 362, '', d=18)
tb(s, x + 46, 354, 214, 44, ['나사 A ~ D', '도구 관측으로 자동 전환'], size=11.5, color=NAVY, w8='s', ls=1.35)
rect(s, x + 18, 430, 18, 18, fill=WHITE, line=NAVY, lw=1.5, shape=MSO_SHAPE.OVAL)
tb(s, x + 46, 422, 214, 44, ['상자 · 뚜껑 · 최종 확인', '작업자가 확인하고 넘어감'], size=11.5, color=NAVY, w8='s', ls=1.35)
src(s, '테스트 영상의 실제 화면 (카메라 미리보기에 안내를 겹친 화면)', y=624)

# ================================================================== 13 평가
s = new('[평가] 참고 영상 8:11~9:19. 참고 영상은 정량 결과 두 가지와 사용성 테스트를 말한다. 우리 쪽 수치는 아직 없으므로 칸을 비워 두었다.')
header(s, 'Evaluation', '세 가지를 재고, 사용하면서 나온 문제를 고쳤습니다')
tag(s, 1041, 100, '수치는 측정 후 기입', w=168)
tb(s, 71, 100, 400, 26, '확인 항목', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 71, 132, 1138, color=NAVY, lw=1.25)
ev = [('단계 전환', '나사 A ~ D를 순서대로 조립하며 자동 전환에 성공한 횟수를 셉니다.', '○ / ○회'),
      ('목표 위치', '안내 표시와 실제 나사 위치의 차이를 화면에서 잽니다.', '○ px'),
      ('끊김 복구', '도구나 마커가 잠깐 가려진 뒤에도 진행이 유지되는지 봅니다.', '○ / ○회')]
for k, (a_, b_, c_) in enumerate(ev):
    y = 132 + k * 58
    tb(s, 87, y, 160, 58, a_, size=15, color=NAVY, w8='x', anchor='m')
    tb(s, 255, y, 700, 58, b_, size=13, color=BODY, anchor='m')
    tb(s, 985, y, 208, 58, c_, size=17, color=ORANGE, w8='x', align='r', anchor='m')
    hline(s, 71, y + 58, 1138)
tb(s, 71, 334, 400, 26, '사용성 피드백과 개선', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 71, 366, 1138, color=NAVY, lw=1.25)
tb(s, 87, 366, 500, 40, '발견한 문제', size=12, color=GREY, w8='x', anchor='m'); tb(s, 655, 366, 500, 40, '개선', size=12, color=GREY, w8='x', anchor='m')
hline(s, 71, 406, 1138)
ut = [('상태 설명이 많아 지금 할 일을 찾기 어려움', '큰 행동 문구 한 줄과 목표 강조로 정리 (개선안)'),
      ('영문 상태 문구가 낯섦', '한글 행동 문구로 변경 (개선안)'),
      ('관측이 잠깐 끊기면 진행이 흔들림', '진행을 보존하고 다시 확인하도록 보강')]
for k, (a_, b_) in enumerate(ut):
    y = 406 + k * 54
    tb(s, 87, y, 520, 54, a_, size=13.5, color=BODY, anchor='m')
    arw(s, 615, y + 13, color=NAVY, size=14)
    tb(s, 655, y, 540, 54, b_, size=13.5, color=NAVY, w8='x', anchor='m')
    hline(s, 71, y + 54, 1138)
src(s, '확인 항목과 방법은 초안입니다. 실제로 잰 항목과 수치로 바꿉니다', y=624)

# ================================================================== 14 성과와 한계
s = new('[성과와 한계] 참고 영상 9:19~10:16. 성과 세 가지를 먼저, 한계는 숨기지 않고 짧게.')
header(s, 'Results', '성과 세 가지와 남은 한계')
tb(s, 71, 104, 300, 26, '성과', size=13, color=ORANGE, w8='x', anchor='m')
rs = [('위치와 단계를 함께 판단하는 실시간 흐름', '카메라 영상에서 마커와 도구를 찾아 안경의 안내까지 한 흐름으로 연결했습니다.'),
      ('도구 관측에 따른 자동 진행', '나사 A ~ D는 드라이버의 접근 · 유지 · 이탈을 보고 다음 나사로 넘어갑니다.'),
      ('혼자 시작하고 끝내는 구성', '관제 화면에서 연결 확인, 작업 시작과 종료, 진행 확인을 할 수 있습니다.')]
for k, (a_, b_) in enumerate(rs):
    y = 142 + k * 130
    numcircle(s, 71, y + 4, k + 1, d=32, size=14)
    tb(s, 119, y, 560, 40, a_, size=19, color=NAVY, w8='x', anchor='m')
    tb(s, 119, y + 46, 560, 50, b_, size=13.5, color=BODY, ls=1.45)
    if k < 2: hline(s, 71, y + 112, 620)
rect(s, 735, 104, 474, 420, fill=PALE)
tb(s, 763, 122, 300, 26, '한계', size=13, color=GREY, w8='x', anchor='m')
for k, t_ in enumerate(['상자 배치 · 뚜껑 닫기 · 최종 확인은 작업자가 확인하고 넘어갑니다.', '안내는 조임 품질(토크)을 측정하지 않습니다.',
                        '마커가 보이는 한 종류의 작업대와 상자에서 확인했습니다.', '도구나 마커가 오래 가려지는 경우는 더 확인이 필요합니다.']):
    y = 164 + k * 86
    rect(s, 763, y + 14, 6, 6, fill=GREY, shape=MSO_SHAPE.OVAL)
    tb(s, 783, y, 400, 70, t_, size=14, color=TXT, w8='s', ls=1.45)
    if k < 3: hline(s, 763, y + 76, 418)

# ================================================================== 15 마무리
s = new('[마무리] 참고 영상 10:16.')
pic(s, IMG['close'], 0, 0, 1280, 720)
tb(s, 85, 176, 900, 170, ['눈앞에는 다음 작업을,', '관제에는 전체 흐름을.'], size=40, color=WHITE, w8='x', ls=1.22)
rect(s, 87, 366, 40, 2, fill=LBLUE)
tb(s, 85, 386, 900, 32, 'AI Assembly Guide는 조립 순서를 따라 작업을 이어가도록 돕습니다.', size=17, color='D9E2F0', anchor='m')
tb(s, 85, 572, 600, 28, 'AI Assembly Guide', size=19, color=WHITE, w8='x', anchor='m')
tb(s, 85, 602, 900, 22, '작업 단계 인식 기반 AR 조립 안내', size=13, color='D9E2F0', anchor='m')
tb(s, 85, 634, 900, 22, '개발 최민준 C011207   |   지도교수 윤영 교수님', size=12.5, color='D9E2F0', w8='m', anchor='m')

# ================================================================== 16 메모
s = new('영상에 넣지 않는 장.')
header(s, 'Memo', '구조 테스트 메모 — 영상에는 넣지 않는 장')
rect(s, 71, 100, 1138, 30, fill=PALE)
for x, w, t_ in [(87, 110, '장'), (200, 400, '참고 영상에서 가져온 것'), (630, 560, '확인하거나 채울 것')]:
    tb(s, x, 100, w, 30, t_, size=11.5, color=NAVY, w8='x', anchor='m')
mm = [('3', '개발 동기: 배경 → 문제 → 목표 → 핵심 목표 셋', '핵심 목표 세 가지는 제가 정리한 문장 → 확인'),
      ('4', '문제 세 가지를 해결과 짝지어 설명', '세 번째(이어진 관측)는 아키텍처 도식의 "시간 증거 게이트"를 풀어 쓴 것'),
      ('5', '기존 방식과 비교표', '비교 대상(종이 · 화면 설명서)과 칸의 문구는 초안. 근거 자료 없음'),
      ('7', '전체 아키텍처', '도식은 HMM이 FSM으로 이어짐, 구성안은 오프라인 분석 경로 → 대본 확인'),
      ('8 · 9', '핵심 처리 과정 세 단계와 사례 하나로 따라가기', '단계 이름과 설명은 도식을 바탕으로 정리. 9장의 유지 · 이탈 시간은 적지 않음'),
      ('11 · 12', '실제 시연', '테스트 영상을 줄여서 넣음 (9MB). 12장의 "왼쪽 위" 등 위치와 시간은 영상을 보고 적은 것'),
      ('13', '성능 평가와 사용성 테스트', '수치 없음 → 빈칸. 확인 항목은 초안. 피드백 세 줄은 구성안의 개선 내용에서 가져옴'),
      ('14', '성과 세 가지와 한계', '성과 문장은 구성안의 사실 범위 안에서 정리. 한계 네 줄 확인')]
for k, (n, a_, b_) in enumerate(mm):
    y = 130 + k * 46
    tb(s, 87, y, 110, 46, n, size=12, color=ORANGE, w8='x', anchor='m')
    tb(s, 200, y, 410, 46, a_, size=11.5, color=TXT, anchor='m')
    tb(s, 630, y, 570, 46, b_, size=11.5, color=BODY, anchor='m', ls=1.3)
    hline(s, 71, y + 46, 1138)
tb(s, 71, 512, 1138, 150, ['· 참고 영상에 있고 v4에 없던 것: 문제와 해결의 짝, 비교표, 사례 하나로 따라가기, 평가, 성과와 한계. v4에 있고 여기서 뺀 것: 간지 4장, 사용 준비, 공간 안내, 관제 단독 장',
                           '· 수정본에 적어 두신 의견 반영: 윤곽 도식 대신 실제 화면(6 · 9 · 10 · 12장), 관제 화면은 작업대 영상이 들어간 화면(10장), 마무리 배경 교체(15장), 사진 출처 줄 삭제',
                           '· 사진: 2 · 3장은 Unsplash (@maciejka_dslr), 표지의 안경은 VITURE 제품 이미지. 나머지는 테스트 영상과 프로젝트 자료',
                           '· 글꼴은 Pretendard Bold를 쓰지 않았음 (PowerPoint에서 저장이 막히던 원인)'], size=11, color=BODY, ls=1.5)

# ------------------------------------------------------------------ 저장
lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
for sl, n in zip(d.prs.slides, NOTES):
    if n: sl.notes_slide.notes_text_frame.text = n
d.save()
