# -*- coding: utf-8 -*-
"""AI Assembly Guide — 구조 테스트 덱. 참고 영상(시커즈 발표)의 전개를 따른다:
동기 → 문제와 해결 → 비교 → 개요 → 아키텍처 → 파이프라인 → 예시 → 양안 투영 → 보정 → 구현 화면 → 시연 → 평가 → 성과와 한계.
v3: 양안 투영 · 보정 장 추가, 화면과 시연 영상을 take4 로 교체.
글꼴은 Pretendard r/m/s/x 만 쓴다 (Bold는 파일에 들어 있지 않아 PowerPoint 저장이 막힌다).
"""
import sys, os, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip, numcircle
sys.path.insert(0, '/home/claude/grad')
from build_stereo import stereo_slide
import numpy as np
from PIL import Image

W_ = '/home/claude/grad'
A = '/mnt/user-data/uploads/AI_Assembly_Video_Pack_20261115/'
P = W_ + '/photo/'; P5 = W_ + '/prep5/'; T4 = W_ + '/t4/full/'; PR = W_ + '/prep_t3/'; PS = W_ + '/prep_s/'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v3.pptx'
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

EXB = (330, 40, 1130, 716)                       # take4 카메라 영상에서 상자와 드라이버 (272x230)
for t in (38, 43, 46, 50):
    sv('ex%d' % t, cover(T4 + 'c%d.jpg' % t, 272, 230, box=EXB))
FLB = (268, 80, 1164, 640)                       # 마커와 상자 (16:10)
for t in (2, 14, 38, 64, 80, 109, 121):
    sv('fl%d' % t, cover(T4 + 'c%d.jpg' % t, 272, 170, box=FLB))
sv('ov', cover(T4 + 'c46.jpg', 484, 272))
sv('scr1', cover(T4 + 'c64.jpg', 368, 230, box=FLB))
sv('scr2', cover(A + '04_관제/관제_B_저장상태_발표용.png', 368, 230, fy=0), 92)
sv('scr3', cover(A + '04_관제/노트북_실행준비_화면.png', 368, 230, fy=0), 92)
sv('p3', cover(T4 + 'c47.jpg', 368, 190, box=(160, 40, 1280, 618)))
sv('p1', cover(A + '03_AI_검출/검출_aruco.png', 368, 190, fy=.6))
sv('p2', cover(A + '03_AI_검출/검출_yolo.png', 368, 190, fy=.3))
sv('mot', cover(P + 'maciejka_dslr-manual_blocks.jpg', 440, 360))
sv('close', shade(cover(T4 + 'c121.jpg', 1280, 720, box=(25, 130, 925, 636)), left=.95, flat=.5))

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
       ('03', '단계 인식과 양안 표시', '세 단계 처리 과정, 나사 A로 따라가기, 양안 투영과 보정'),
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
pic(s, IMG['mot'], 71, 108, 440, 360)
rows = [('배경', '조립 작업은 설명서에 의존합니다', '익숙하지 않은 작업자는 설명서와 부품을 번갈아 확인하며 순서를 따라갑니다.'),
        ('문제', '손을 멈추는 사이 순서를 놓칩니다', '시선이 설명서와 작업대를 오가고, 어디까지 했는지 다시 찾아야 합니다.'),
        ('목표', '작업 위치에서 다음 행동을 확인합니다', '작업할 위치와 다음 행동을 AR 안경으로 눈앞에 보여줍니다.')]
for k, (lab, t_, d_) in enumerate(rows):
    y = 112 + k * 124
    chip(s, 545, y + 6, lab, fill=NAVY if k == 2 else PALE, color=WHITE if k == 2 else NAVY, size=11, w=56, h=26, w8='x')
    tb(s, 617, y, 590, 38, t_, size=19, color=NAVY, w8='x', anchor='m')
    tb(s, 617, y + 44, 590, 48, d_, size=13.5, color=BODY, ls=1.45)
    if k < 2: hline(s, 545, y + 106, 664)
hline(s, 71, 496, 1138)
tb(s, 71, 510, 300, 26, '핵심 목표', size=13, color=ORANGE, w8='x', anchor='m')
for k, (t_, d_) in enumerate([('작업 위치에 직접 안내', '마커로 계산한 위치에 목표를 표시합니다.'), ('작업 단계를 따라가는 안내', '도구의 움직임을 보고 다음 단계로 넘어갑니다.'), ('혼자서도 쓸 수 있는 구성', '안경과 노트북으로 시작하고 끝냅니다.')]):
    x = 71 + k * 385
    numcircle(s, x, 556, k + 1, d=30, size=13)
    tb(s, x + 42, 551, 320, 40, t_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, x + 42, 594, 320, 26, d_, size=12.5, color=BODY, anchor='m')
hline(s, 71, 644, 1138)

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
    y = 106 + k * 152
    rect(s, 71, y, 510, 138, line=LINE, lw=1)
    tb(s, 95, y + 16, 200, 20, '문제 %d' % (k + 1), size=11, color=GREY, w8='x', anchor='m')
    tb(s, 95, y + 42, 470, 32, pt, size=17, color=TXT, w8='x', anchor='m')
    tb(s, 95, y + 82, 470, 46, pd, size=13, color=BODY, ls=1.4)
    arw(s, 587, y + 52, color=NAVY, size=20, h=34, w=46)
    rect(s, 639, y, 570, 138, fill=PALE); rect(s, 639, y, 4, 138, fill=NAVY)
    tb(s, 667, y + 16, 200, 20, '해결', size=11, color=ORANGE, w8='x', anchor='m')
    tb(s, 667, y + 42, 520, 32, st, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, 667, y + 82, 520, 46, sd, size=13, color=BODY, ls=1.4)
hline(s, 71, 572, 1138); hline(s, 71, 644, 1138)
tb(s, 71, 572, 170, 72, '핵심 차별점', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 240, 572, 960, 72, '위치는 마커로, 단계는 도구의 움직임으로 판단해 작업 위치에 바로 안내합니다.', size=18, color=NAVY, w8='x', anchor='m')

# ================================================================== 5 비교
s = new('[기존 방식과 비교] 참고 영상 1:47~2:20. 표의 구분과 문구는 초안이므로 확인이 필요하다.')
header(s, 'Comparison', '안내가 보이는 곳과 단계를 넘기는 방법이 다릅니다')
cols = [(71, 228, '구분'), (299, 270, '종이 설명서'), (569, 270, '화면 설명서 (태블릿 · 영상)'), (839, 370, 'AI Assembly Guide')]
trs = [('안내가 보이는 곳', '책상 위 설명서', '옆에 둔 화면', '작업 위치 위 (AR 안경)'),
       ('다음 단계로 넘어가기', '직접 페이지를 넘김', '직접 누르거나 재생', '나사 A ~ D는 AI 관측으로 자동 전환'),
       ('작업 중 시선', '설명서와 작업대를 오감', '화면과 작업대를 오감', '작업대에 머묾, 시각적 피드백 명확'),
       ('진행 상황 확인', '작업자가 기억', '작업자가 기억', '관제 화면에 현재 단계와 다음 행동 표시')]
RH = 108
rect(s, 839, 106, 370, 70 + 4 * RH, fill=PALE); rect(s, 839, 106, 370, 4, fill=NAVY)
for (x, w, t_) in cols:
    tb(s, x + 16, 110, w - 24, 66, t_, size=16 if x == 839 else 13.5, color=NAVY if x == 839 else GREY, w8='x', anchor='m')
hline(s, 71, 176, 1138, color=NAVY, lw=1.25)
for r, row in enumerate(trs):
    y = 176 + r * RH
    for c, (x, w, _) in enumerate(cols):
        tb(s, x + 16, y, w - 24, RH, row[c], size=15 if c in (0, 3) else 14, color=NAVY if c in (0, 3) else BODY, w8='x' if c in (0, 3) else 'r', anchor='m', ls=1.35)
    hline(s, 71, y + RH, 1138)
src(s, '상자 배치 · 뚜껑 닫기 · 최종 확인은 작업자가 확인하고 넘어갑니다', y=626)

# ================================================================== 6 개요
s = new('[서비스 개요] 참고 영상 2:20~2:46. 대상 → 처리 흐름 → 제공하는 결과.')
header(s, 'Overview', '카메라 영상에서 위치와 단계를 판단해 안경에 안내합니다')
tb(s, 71, 106, 150, 26, '대상', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 71, 136, 620, 36, '상자 조립 일곱 단계', size=20, color=NAVY, w8='x', anchor='m')
tb(s, 71, 176, 620, 26, '상자 배치 → 뚜껑 닫기 → 나사 A · B · C · D → 최종 확인', size=13.5, color=BODY, anchor='m')
hline(s, 71, 224, 620)
tb(s, 71, 240, 200, 26, '핵심 처리 흐름', size=13, color=ORANGE, w8='x', anchor='m')
for k, t_ in enumerate(['카메라 영상', '마커로\n위치 계산', '도구 검출', '단계 판단', '안경 · 관제\n전달']):
    x = 71 + k * 127
    r = rect(s, x, 278, 112, 108, fill=NAVY if k == 4 else PALE, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .1
    tb(s, x + 10, 286, 40, 20, '0%d' % (k + 1), size=11, color='C5D5E8' if k == 4 else LBLUE, w8='x', anchor='m')
    tb(s, x, 306, 112, 70, t_.split('\n'), size=14, color=WHITE if k == 4 else NAVY, w8='x', align='c', anchor='m', ls=1.25)
    if k < 4: arw(s, x + 111, 318, size=11, w=17)
hline(s, 71, 412, 620)
tb(s, 71, 428, 200, 26, '안내 결과', size=13, color=ORANGE, w8='x', anchor='m')
for k, (a_, b_) in enumerate([('안경', '현재 나사 강조, 상자 · 뚜껑 윤곽, 행동 문구'), ('관제 화면', '현재 작업, 다음 행동, 진행 상태'), ('작업자', '상자 배치 · 뚜껑 닫기 · 최종 확인은 직접 확인')]):
    y = 464 + k * 58
    tb(s, 71, y, 110, 48, a_, size=15.5, color=NAVY, w8='x', anchor='m')
    tb(s, 181, y, 510, 48, b_, size=14, color=BODY, anchor='m')
    if k < 2: hline(s, 71, y + 53, 620)
pic(s, IMG['ov'], 725, 106, 484, 272)
tb(s, 725, 384, 484, 18, '카메라 화면에 안내를 겹친 모습 (시연 영상)', size=9.5, color=LGREY, anchor='m')
rect(s, 725, 428, 484, 206, fill=PALE)
tb(s, 749, 442, 300, 26, '화면 읽는 법', size=13, color=ORANGE, w8='x', anchor='m')
for k, (a_, b_) in enumerate([('청록 선', '상자와 뚜껑의 윤곽'), ('노란 표시', '지금 작업할 나사'), ('A · B · C · D', '나사 네 개의 위치')]):
    y = 478 + k * 48
    tb(s, 749, y, 150, 40, a_, size=15, color=NAVY, w8='x', anchor='m')
    tb(s, 899, y, 290, 40, b_, size=14, color=BODY, anchor='m')

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
    numcircle(s, x, 108, k + 1, d=30, size=13)
    tb(s, x + 42, 106, 320, 34, t_, size=19, color=NAVY, w8='x', anchor='m')
    pic(s, IMG[im], x, 152, 368, 190)
    for j, (a_, b_) in enumerate(boxes):
        y = 362 + j * 134
        rect(s, x, y, 368, 114, fill=PALE)
        tb(s, x + 20, y + 16, 328, 30, a_, size=16, color=NAVY, w8='x', anchor='m')
        tb(s, x + 20, y + 54, 328, 46, b_, size=13, color=BODY, ls=1.4)
        if j == 0: tb(s, x, y + 114, 368, 20, '↓', size=12, color=LBLUE, w8='s', align='c', anchor='m')
    if k < 2: arw(s, x + 367, 234, color=NAVY, size=15, w=19)
src(s, '왼쪽 · 가운데 그림은 2026년 5월 개발 영상의 검출 결과, 오른쪽은 시연 영상', y=664)

# ================================================================== 9 예시
s = new('[예시로 따라가기] 참고 영상 4:57~5:56. 사례 하나(여기서는 나사 A)로 처리 과정을 처음부터 끝까지 보여준다. 화면은 take4의 0:38, 0:43, 0:46, 0:50. 검은 줄은 그때 Unity 화면에 나온 문구. 촬영용 설정이라 초록 안내 2초 뒤에 넘어간다.')
header(s, 'Example', '나사 A 하나로 처리 과정을 따라가 봅니다')
lead(s, '시연 영상의 실제 화면입니다. 노란 표시가 지금 작업할 나사이고, 검은 줄은 그때 안경에 나온 문구입니다.', y=96, h=30)
ex = [(38, '목표 표시', 'A 위치에 노란 표시를 올립니다.', '나사 A · 1/4', 'FFFFFF'),
      (43, '접근', '드라이버 끝이 A에 가까워집니다.', '드라이버 끝을 나사 A에 맞춰주세요', 'EBBD5B'),
      (46, '유지', '일정 시간 머물면 작업 중으로 봅니다.', '나사 A를 조여주세요', '59C9E6'),
      (50, '전환', '초록 안내 뒤 B로 넘어갑니다.', '드라이버를 떼어주세요', '5CEE89')]
for k, (t, a_, b_, ph, pc) in enumerate(ex):
    x = 71 + k * 288.7
    pic(s, IMG['ex%d' % t], x, 134, 272, 230)
    rect(s, x, 364, 272, 4, fill=NAVY)
    numcircle(s, x, 382, k + 1, d=28)
    tb(s, x + 38, 379, 230, 34, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, x, 420, 272, 26, b_, size=13, color=BODY, anchor='m')
    r = rect(s, x, 458, 272, 32, fill=BLACK, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .5
    tb(s, x, 458, 272, 32, ph, size=11, color=pc, w8='s', align='c', anchor='m', wrap=False)
    if k < 3: arw(s, x + 272, 234, color=NAVY, size=13, w=17)
rect(s, 71, 518, 1138, 114, fill=PALE)
for k, (a_, b_) in enumerate([('위치', '마커에서 계산한 A의 좌표'), ('관측', '드라이버 끝과 A 사이의 거리'), ('판단', '접근과 유지가 이어지면 다음 나사로')]):
    x = 99 + k * 372
    tb(s, x, 528, 80, 94, a_, size=14, color=ORANGE, w8='x', anchor='m')
    tb(s, x + 70, 528, 290, 94, b_, size=15, color=NAVY, w8='x', anchor='m')
src(s, '촬영용 설정으로 초록 안내 2초 뒤 다음 나사로 넘어갑니다 · 안내는 도구의 움직임을 본 결과이며, 조임 품질을 측정한 것이 아닙니다', y=664)

# ================================================================== 10 양안 투영
NOTES.append('[양안 투영] 참고 영상에는 없는 장. 같은 원을 양쪽에 복사하는 것이 아니라, 같은 나사 위치를 왼눈과 오른눈에 각각 계산한다. '
             'ArUco와 PnP로 카메라 자세를 구하고, 나사 A~D를 카메라 기준 3D 좌표로 바꾼 뒤, 눈별 투영 행렬(3×4)로 화면 좌표를 구한다. '
             'Unity는 좌우 1920×1080 화면을 나란히 붙인 Full SBS(3840×1080)로 내보낸다. 보정값은 미리 구하고 표시 위치만 실시간으로 다시 계산한다. '
             '위 그림은 작업대 사진에 Unity 왼눈 화면을 맞춰 얹은 재현 이미지이고, 아래 세 그림은 take4 0:45의 Unity 출력이다.')
stereo_slide(d)

# ================================================================== 11 보정
s = new('[보정과 확인] 참고 영상에는 없는 장. 보정 절차: 같은 착용 상태에서 목표 원을 실제 나사에 맞추고 그 순간의 3D 좌표와 좌우 화면 좌표를 저장 → 양안 공동 최적화 → 저장 후 자동 적용. '
        '처음에는 눈마다 따로 계산하는 독립 DLT(22변수)와 비교했고, PD 64mm를 참고값(약한 제약)으로 쓰는 공통 양안 모델(13변수)로 정리했다. '
        '화면에 넣지 않은 수치: 보정 관측 8개, 화면 좌표 적합 RMS 약 5.57px, 한 관측씩 빼고 예측한 최대 오차 약 27.79px. '
        '이 수치는 저장한 정렬 좌표에 대한 계산 결과이며 실물 정합 정확도가 아니다. 그래서 숫자 대신 무엇을 바꿔 가며 어떻게 확인했는지를 말한다. '
        '확인은 2026년 11월 14일 같은 착용 세션에서 착용자가 눈으로 본 것이다.')
header(s, 'Calibration', '보정은 한 번 해 두고, 거리와 시점을 바꿔 가며 확인했습니다')
pic(s, PS + 'calib.png', 71, 104, 440, 300)
chip(s, 81, 114, '개념도', fill=WHITE, color=NAVY, size=9.5, w=58, h=22, w8='x')
tb(s, 311, 143, 170, 22, '나사의 3D 좌표', size=11.5, color=NAVY, w8='x', anchor='m')
tb(s, 153, 270, 72, 18, '왼눈 화면', size=10.5, color=NAVY, w8='s', anchor='m')
tb(s, 357, 270, 72, 18, '오른눈 화면', size=10.5, color=NAVY, w8='s', align='r', anchor='m')
tb(s, 143, 326, 52, 20, '왼눈', size=10.5, color=GREY, w8='s', align='r', anchor='m')
tb(s, 388, 326, 60, 20, '오른눈', size=10.5, color=GREY, w8='s', anchor='m')
tb(s, 211, 366, 160, 20, 'PD 64mm (참고값)', size=10.5, color=GREY, w8='s', align='c', anchor='m')
tb(s, 71, 410, 440, 18, '두 눈이 하나의 기하를 공유하고, 같은 나사가 눈마다 다른 자리에 찍힙니다.', size=9.5, color=LGREY, anchor='m')
tb(s, 545, 104, 300, 24, '보정 절차', size=13, color=ORANGE, w8='x', anchor='m')
cal = [('관측 수집', '같은 착용 상태에서 목표 원을 실제 나사에 맞추고, 그 순간의 3D 좌표와 좌우 화면 좌표를 저장합니다.'),
       ('양안 공동 최적화', '두 눈이 하나의 기하를 공유하도록 묶어, 좌우 투영 행렬을 함께 구합니다.'),
       ('저장 후 자동 적용', '보정값을 저장해 두고, 실행할 때 불러와 눈별 투영에 씁니다.')]
for k, (a_, b_) in enumerate(cal):
    y = 132 + k * 92
    numcircle(s, 545, y + 1, k + 1, d=30, size=13)
    tb(s, 589, y, 620, 30, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, 589, y + 32, 620, 50, b_, size=12, color=BODY, ls=1.35)
    if k < 2: hline(s, 545, y + 87, 664)
rect(s, 545, 392, 664, 40, fill=PALE)
tb(s, 561, 392, 40, 40, '처음', size=10.5, color=GREY, w8='x', anchor='m')
tb(s, 599, 392, 250, 40, '눈마다 따로 계산 · 독립 DLT 22변수', size=12, color=BODY, anchor='m')
arw(s, 846, 398, color=NAVY, size=14)
tb(s, 880, 392, 40, 40, '지금', size=10.5, color=ORANGE, w8='x', anchor='m')
tb(s, 918, 392, 290, 40, '공통 양안 모델 · 13변수, PD 64mm 참고', size=12, color=NAVY, w8='x', anchor='m')
hline(s, 71, 444, 1138)
tb(s, 71, 454, 200, 24, '정합 확인', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 371, 454, 450, 24, '2026. 11. 14 · 같은 착용 상태에서 착용자가 확인', size=10.5, color=GREY, align='r', anchor='m')
hline(s, 71, 486, 750, color=NAVY, lw=1.25)
chk = [('거리', '가까이 ↔ 기준 거리', '대체로 하나로 겹침'), ('시점', '작은 측면 이동 → 정면 복귀', '겹침 유지')]
for k, (a_, b_, c_) in enumerate(chk):
    y = 486 + k * 74
    tb(s, 87, y, 56, 74, a_, size=12, color=ORANGE, w8='x', anchor='m')
    tb(s, 143, y, 280, 74, b_, size=15, color=NAVY, w8='x', anchor='m')
    for j, c in enumerate('ABCD'):
        numcircle(s, 432 + j * 34, y + 24, c, d=26, size=11)
    tb(s, 596, y, 220, 74, c_, size=15, color=NAVY, w8='x', anchor='m')
    hline(s, 71, y + 74, 750)
rect(s, 852, 454, 357, 181, fill=PALE)
tb(s, 874, 466, 300, 22, '이 확인의 범위', size=12, color=GREY, w8='x', anchor='m')
for k, t_ in enumerate(['착용자가 눈으로 본 정성 확인입니다.', '어긋남과 표시 끊김은 따로 기록했습니다.', '보정 계산의 오차를 실물 정합 정확도로 쓰지 않습니다.']):
    y = 496 + k * 38
    rect(s, 874, y + 8, 5, 5, fill=GREY, shape=MSO_SHAPE.OVAL)
    tb(s, 890, y, 304, 40, t_, size=12.5, color=TXT, w8='s', ls=1.3)
src(s, '참고: Hartley · Zisserman, Multiple View Geometry / Seitz, Camera Calibration — 특정 논문을 그대로 구현한 것이 아니라 투영 기하의 원리를 적용했습니다', y=664)

# ================================================================== 12 구현 화면
s = new('[구현 화면] 참고 영상 5:56~6:34. 화면마다 무엇을 볼 수 있는지 한 문장씩.')
header(s, 'Screens', '안내 표시와 관제 화면으로 구성했습니다')
scr = [('scr1', '안내 표시', '작업할 나사를 노란 표시로 강조하고, 상자와 뚜껑은 윤곽으로 보여줍니다.', '카메라 미리보기 (시연 영상)'),
       ('scr2', '관제 화면', '현재 작업, 다음 행동, 진행 상태를 한 화면에서 확인합니다.', '저장 상태를 다시 재생한 화면'),
       ('scr3', '준비 화면', '안경 연결을 확인하고 작업을 시작하고 끝냅니다.', '실행 전 화면')]
for k, (im, a_, b_, c_) in enumerate(scr):
    x = 71 + k * 385
    rect(s, x - 1, 106, 370, 20, fill='1B2430')
    for j in range(3): rect(s, x + 9 + j * 13, 112, 7, 7, fill=('E0685F', 'E5B94A', '5FBF6B')[j], shape=MSO_SHAPE.OVAL)
    pic(s, IMG[im], x, 126, 368, 230)
    rect(s, x - 1, 106, 370, 251, line=LINE, lw=.75)
    tb(s, x, 376, 368, 36, a_, size=19, color=NAVY, w8='x', anchor='m')
    tb(s, x, 418, 360, 52, b_, size=13.5, color=BODY, ls=1.45)
    tb(s, x, 480, 368, 18, c_, size=9.5, color=LGREY, anchor='m')
hline(s, 71, 540, 1138); hline(s, 71, 644, 1138)
tb(s, 71, 540, 120, 104, '역할', size=14, color=ORANGE, w8='x', anchor='m')
tb(s, 190, 540, 1010, 104, '작업자는 눈앞의 안내를 따라가고, 관제 화면에서는 전체 진행을 확인합니다.', size=19, color=NAVY, w8='x', anchor='m')

# ================================================================== 13 시연
s = new('[실제 시연] 참고 영상 6:34~8:11. 영상은 한 번만 재생하고, 단계가 바뀌는 순간에 말을 맞춘다. '
        '왼쪽은 작업대 카메라(안내를 겹친 화면), 오른쪽은 같은 구간의 Unity 왼눈 화면이다. 안경 렌즈를 통해 찍은 영상이 아니다. '
        '두 영상은 따로 수집한 것이라 Unity 화면을 0.3초 늦춰 맞췄다. 단계가 바뀌는 네 곳에서 맞춘 뒤의 차이는 카메라 한 프레임(0.1초) 안쪽이다. 손이나 도구가 마커를 가리면 윤곽이 잠깐 사라진다. '
        '촬영용 설정: 초록 안내 2초 뒤 자동 전환. 조임 완료를 자동으로 검증한 자료가 아니며, 마지막은 최종 확인을 요청하는 장면까지다.')
header(s, 'Demo', '상자 하나를 처음부터 끝까지 조립합니다')
s.shapes.add_movie(PR + 'demo_sync.mp4', px(71), px(104), px(1138), px(320), poster_frame_image=PR + 'poster.jpg', mime_type='video/mp4')
tb(s, 71, 430, 569, 20, '작업대 카메라 — 안내를 겹친 화면', size=10.5, color=GREY, w8='m', anchor='m')
tb(s, 640, 430, 569, 20, 'Unity 왼눈 화면 — 안경으로 보내는 화면 (렌즈를 통해 찍은 영상은 아님)', size=10.5, color=GREY, w8='m', anchor='m')
hline(s, 71, 462, 1138)
tb(s, 71, 472, 200, 24, '영상에서 볼 곳', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 709, 472, 500, 24, '시간 · 단계 · 안경에 나오는 문구   |   2분 1초 · 소리 없음', size=10.5, color=GREY, align='r', anchor='m')
tl = [('0:00', '상자 배치', '상자를 놓아주세요', 'u'), ('0:13', '뚜껑 닫기', '뚜껑을 덮어주세요', 'u'), ('0:27', '나사 A', '나사 A를 조여주세요', 'a'), ('0:50', '나사 B', '나사 B를 조여주세요', 'a'),
      ('1:11', '나사 C', '나사 C를 조여주세요', 'a'), ('1:41', '나사 D', '나사 D를 조여주세요', 'a'), ('1:59', '최종 확인', '조립 상태를 확인해주세요', 'u')]
for k, (tm, a_, ph, kind) in enumerate(tl):
    x = 71 + k * 164.7
    rect(s, x, 508, 150, 3, fill=NAVY if kind == 'a' else LBLUE)
    tb(s, x, 518, 150, 28, tm, size=15, color=LBLUE, w8='x', anchor='m')
    tb(s, x, 546, 150, 32, a_, size=16.5, color=NAVY, w8='x', anchor='m')
    tb(s, x, 584, 150, 44, ph, size=11.5, color=BODY, ls=1.35)
hline(s, 71, 644, 1138)
src(s, '촬영용 설정으로 초록 안내 2초 뒤 다음 단계로 넘어갑니다 · 두 화면은 따로 녹화한 것으로, Unity 화면을 0.3초 늦춰 맞췄습니다', y=664)

# ================================================================== 14 일곱 단계
s = new('[일곱 단계] 시연에 이어 단계별 화면을 한 장에 정리한다. 참고 영상에는 없는 장. 화면은 take4의 0:02, 0:14, 0:38, 1:04, 1:20, 1:49, 2:01.')
header(s, 'Flow', '일곱 단계가 화면에서 이렇게 보입니다')
fl = [(2, '상자 배치', '놓을 자리의 윤곽', 'u'), (14, '뚜껑 닫기', '뚜껑 자리의 윤곽', 'u'), (38, '나사 A', '왼쪽 위', 'a'), (64, '나사 B', '오른쪽 위', 'a'),
      (80, '나사 C', '왼쪽 아래', 'a'), (109, '나사 D', '오른쪽 아래', 'a'), (121, '최종 확인', '전체 윤곽', 'u')]
for k, (t, a_, b_, kind) in enumerate(fl):
    x = 71 + (k % 4) * 288.7; y = 106 + (k // 4) * 272
    pic(s, IMG['fl%d' % t], x, y, 272, 170)
    if kind == 'a': numcircle(s, x, y + 184, k + 1, d=28, size=12)
    else:
        rect(s, x, y + 184, 28, 28, fill=WHITE, line=NAVY, lw=1.5, shape=MSO_SHAPE.OVAL)
        tb(s, x, y + 184, 28, 28, str(k + 1), size=12, color=NAVY, w8='x', align='c', anchor='m', wrap=False)
    tb(s, x + 38, y + 181, 150, 34, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, x + 150, y + 181, 122, 34, b_, size=12, color=GREY, align='r', anchor='m')
x = 71 + 3 * 288.7
rect(s, x, 378, 272, 170, fill=PALE)
numcircle(s, x + 20, 404, '', d=18)
tb(s, x + 50, 394, 210, 50, ['나사 A ~ D', '도구 관측으로 자동 전환'], size=12.5, color=NAVY, w8='s', ls=1.4)
rect(s, x + 20, 482, 18, 18, fill=WHITE, line=NAVY, lw=1.5, shape=MSO_SHAPE.OVAL)
tb(s, x + 50, 472, 210, 50, ['상자 · 뚜껑 · 최종 확인', '작업자가 확인하고 넘어감'], size=12.5, color=NAVY, w8='s', ls=1.4)
src(s, '시연 영상의 실제 화면 (카메라 화면에 안내를 겹친 모습)', y=664)

# ================================================================== 15 평가
s = new('[평가] 참고 영상 8:11~9:19. 참고 영상은 정량 결과 두 가지와 사용성 테스트를 말한다. 우리 쪽 수치는 아직 없으므로 칸을 비워 두었다.')
header(s, 'Evaluation', '세 가지를 재고, 사용하면서 나온 문제를 고쳤습니다')
tag(s, 1041, 104, '수치는 측정 후 기입', w=168)
tb(s, 71, 104, 400, 26, '확인 항목', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 71, 138, 1138, color=NAVY, lw=1.25)
ev = [('단계 전환', '나사 A ~ D를 순서대로 조립하며 자동 전환에 성공한 횟수를 셉니다.', '○ / ○회'),
      ('목표 위치', '안내 표시와 실제 나사 위치의 차이를 화면에서 잽니다.', '○ px'),
      ('끊김 복구', '도구나 마커가 잠깐 가려진 뒤에도 진행이 유지되는지 봅니다.', '○ / ○회')]
for k, (a_, b_, c_) in enumerate(ev):
    y = 138 + k * 68
    tb(s, 87, y, 160, 68, a_, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, 255, y, 700, 68, b_, size=14, color=BODY, anchor='m')
    tb(s, 985, y, 208, 68, c_, size=19, color=ORANGE, w8='x', align='r', anchor='m')
    hline(s, 71, y + 68, 1138)
tb(s, 71, 372, 400, 26, '사용성 피드백과 개선', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 71, 406, 1138, color=NAVY, lw=1.25)
tb(s, 87, 406, 500, 42, '발견한 문제', size=12, color=GREY, w8='x', anchor='m'); tb(s, 655, 406, 500, 42, '개선', size=12, color=GREY, w8='x', anchor='m')
hline(s, 71, 448, 1138)
ut = [('상태 설명이 많아 지금 할 일을 찾기 어려움', '큰 행동 문구 한 줄과 목표 강조로 정리'),
      ('영문 상태 문구가 낯섦', '한글 행동 문구로 변경'),
      ('관측이 잠깐 끊기면 진행이 흔들림', '진행을 보존하고 다시 확인하도록 보강')]
for k, (a_, b_) in enumerate(ut):
    y = 448 + k * 64
    tb(s, 87, y, 520, 64, a_, size=14.5, color=BODY, anchor='m')
    arw(s, 615, y + 18, color=NAVY, size=14)
    tb(s, 655, y, 540, 64, b_, size=14.5, color=NAVY, w8='x', anchor='m')
    hline(s, 71, y + 64, 1138)
src(s, '확인 항목과 방법은 초안입니다. 실제로 잰 항목과 수치로 바꿉니다', y=664)

# ================================================================== 16 성과와 한계
s = new('[성과와 한계] 참고 영상 9:19~10:16. 성과 세 가지를 먼저, 한계는 숨기지 않고 짧게.')
header(s, 'Results', '성과 세 가지와 남은 한계')
tb(s, 71, 104, 300, 26, '성과', size=13, color=ORANGE, w8='x', anchor='m')
rs = [('위치와 단계를 함께 판단하는 실시간 흐름', '카메라 영상에서 마커와 도구를 찾아, 눈마다 따로 계산한 안경 화면까지 한 흐름으로 연결했습니다.'),
      ('도구 관측에 따른 자동 진행', '나사 A ~ D는 드라이버의 접근 · 유지 · 이탈을 보고 다음 나사로 넘어갑니다.'),
      ('혼자 시작하고 끝내는 구성', '관제 화면에서 연결 확인, 작업 시작과 종료, 진행 확인을 할 수 있습니다.')]
for k, (a_, b_) in enumerate(rs):
    y = 148 + k * 166
    numcircle(s, 71, y + 4, k + 1, d=34, size=15)
    tb(s, 121, y, 560, 42, a_, size=20, color=NAVY, w8='x', anchor='m')
    tb(s, 121, y + 52, 560, 56, b_, size=14.5, color=BODY, ls=1.5)
    if k < 2: hline(s, 71, y + 138, 620)
rect(s, 735, 104, 474, 524, fill=PALE)
tb(s, 763, 124, 300, 26, '한계', size=13, color=GREY, w8='x', anchor='m')
for k, t_ in enumerate(['상자 배치 · 뚜껑 닫기 · 최종 확인은 작업자가 확인하고 넘어갑니다.', '안내는 조임 품질(토크)을 측정하지 않습니다.',
                        '마커가 보이는 한 종류의 작업대와 상자에서 확인했습니다.', '도구나 마커가 오래 가려지는 경우는 더 확인이 필요합니다.',
                        '두 눈 화면의 겹침은 한 착용 상태에서 눈으로 확인했습니다.']):
    y = 164 + k * 92
    rect(s, 763, y + 15, 6, 6, fill=GREY, shape=MSO_SHAPE.OVAL)
    tb(s, 783, y, 400, 66, t_, size=14.5, color=TXT, w8='s', ls=1.45)
    if k < 4: hline(s, 763, y + 78, 418)

# ================================================================== 17 마무리
s = new('[마무리] 참고 영상 10:16.')
pic(s, IMG['close'], 0, 0, 1280, 720)
tb(s, 85, 176, 900, 170, ['눈앞에는 다음 작업을,', '관제에는 전체 흐름을.'], size=40, color=WHITE, w8='x', ls=1.22)
rect(s, 87, 366, 40, 2, fill=LBLUE)
tb(s, 85, 384, 520, 60, ['AI Assembly Guide는 조립 순서를 따라', '작업을 이어가도록 돕습니다.'], size=17, color='D9E2F0', ls=1.4)
tb(s, 85, 572, 600, 28, 'AI Assembly Guide', size=19, color=WHITE, w8='x', anchor='m')
tb(s, 85, 602, 900, 22, '작업 단계 인식 기반 AR 조립 안내', size=13, color='D9E2F0', anchor='m')
tb(s, 85, 634, 900, 22, '개발 최민준 C011207   |   지도교수 윤영 교수님', size=12.5, color='D9E2F0', w8='m', anchor='m')

# ================================================================== 18 메모
s = new('영상에 넣지 않는 장.')
header(s, 'Memo', '구조 테스트 메모 — 영상에는 넣지 않는 장')
rect(s, 71, 100, 1138, 30, fill=PALE)
for x, w, t_ in [(87, 110, '장'), (200, 400, '참고 영상에서 가져온 것'), (630, 560, '확인하거나 채울 것')]:
    tb(s, x, 100, w, 30, t_, size=11.5, color=NAVY, w8='x', anchor='m')
mm = [('3', '개발 동기: 배경 → 문제 → 목표 → 핵심 목표 셋', '핵심 목표 세 가지는 제가 정리한 문장 → 확인'),
      ('4', '문제 세 가지를 해결과 짝지어 설명', '세 번째(이어진 관측)는 아키텍처 도식의 "시간 증거 게이트"를 풀어 쓴 것'),
      ('5', '기존 방식과 비교표', '비교 대상과 칸의 문구는 초안, 근거 자료 없음. 고쳐 주신 두 칸은 그대로 둠'),
      ('7', '전체 아키텍처', '도식은 HMM이 FSM으로 이어짐, 구성안은 오프라인 분석 경로 → 대본 확인'),
      ('8 · 9', '핵심 처리 과정 세 단계와 사례 하나로 따라가기', '9장의 검은 줄은 take4의 Unity 화면에서 읽은 문구 (같은 때의 화면, 1초 안쪽 차이)'),
      ('10', '참고 영상에 없음 — 양안 투영', '위 그림은 작업대 사진에 Unity 왼눈 화면을 나사 네 점에 맞춰 얹은 재현. 선은 굵게 처리'),
      ('11', '참고 영상에 없음 — 보정과 확인', '내용은 코덱스 정리 기준, 개념도는 새로 그림. 관측 8개 · RMS · 제외 예측 오차는 노트에만'),
      ('13 · 14', '실제 시연', 'take4의 카메라와 Unity 왼눈 화면을 나란히 붙임. Unity를 0.3초 늦춰 맞춤 (전환 네 곳 확인)'),
      ('15', '성능 평가와 사용성 테스트', '수치 없음 → 빈칸. 확인 항목은 초안. 피드백 세 줄은 구성안의 개선 내용에서 가져옴'),
      ('16', '성과 세 가지와 한계', '첫 성과 문장에 "눈마다 따로 계산한 안경 화면"을, 한계에 양안 확인 범위 한 줄을 더함 → 확인')]
for k, (n, a_, b_) in enumerate(mm):
    y = 130 + k * 36
    tb(s, 87, y, 110, 36, n, size=11.5, color=ORANGE, w8='x', anchor='m')
    tb(s, 200, y, 410, 36, a_, size=11, color=TXT, anchor='m')
    tb(s, 630, y, 570, 36, b_, size=11, color=BODY, anchor='m', ls=1.2)
    hline(s, 71, y + 36, 1138)
tb(s, 71, 500, 1138, 150, ['· v2에서 바뀐 것: 양안 투영(10장)과 보정(11장)을 넣음. 시연 영상을 take4로 바꾸고 Unity 왼눈 화면을 옆에 붙임. 6 · 8 · 9 · 12 · 14 · 17장의 화면도 take4로 바꿈',
                           '· take4는 촬영용 설정(초록 안내 2초 뒤 자동 전환)으로 찍은 영상이라 9 · 13장 아래에 적어 둠. 조임 완료를 자동으로 검증한 자료가 아님',
                           '· take4의 Unity 화면에 한글 행동 문구가 실제로 나오므로 6 · 15장의 "(개선안)" 표시를 뺌 → 확인',
                           '· Unity 화면은 손이나 도구가 마커를 가리면 윤곽이 사라짐 (전체의 3분의 1쯤). 시연 영상에 그대로 보임',
                           '· 사진: 2 · 3장은 Unsplash (@maciejka_dslr), 표지의 안경은 VITURE 제품 이미지. 글꼴은 Pretendard Bold를 쓰지 않음'], size=10.5, color=BODY, ls=1.45)

# ------------------------------------------------------------------ 저장
lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
for sl, n in zip(d.prs.slides, NOTES):
    if n: sl.notes_slide.notes_text_frame.text = n
d.save()
