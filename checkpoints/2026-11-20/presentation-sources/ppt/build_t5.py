# -*- coding: utf-8 -*-
"""AI Assembly Guide — 구조 테스트 덱. 참고 영상(시커즈 발표)의 전개를 따른다:
동기 → 문제와 해결 → 비교 → 개요 → 아키텍처 → 파이프라인 → 예시 → 양안 투영 → 보정 → 구현 화면 → 시연 → 평가 → 성과와 한계.
v3: 양안 투영 · 보정 장 추가, 화면과 시연 영상을 take4 로 교체.
v4: 시연 영상을 합성본으로 교체, 보정 절차의 번호 원을 세로선과 점으로 변경(CAL=num 이면 01·02·03), HMM 설명 확정.
v5: 세 가지 문제로 묶음. 새 장 넷(Challenges, Dataset, Experiment, Recovery), Evaluation 다시 구성, Flow 삭제. 그림은 assets_t5.py.
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
P = W_ + '/photo/'; P5 = W_ + '/prep5/'; T4 = W_ + '/t4/full/'; PR = W_ + '/prep_t3/'; PS = W_ + '/prep_s/'; PR5 = W_ + '/prep_t5/'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v5.pptx'
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

def kicker(s, text):
    tb(s, 50, 24, 400, 18, text, size=10.5, color=ORANGE, w8='x', anchor='m')

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
s = new('[목차] 참고 영상의 순서(배경과 개요 → 시스템 설계 → 구현 결과 → 성능 평가 → 성과와 한계)를 따르되, 가운데를 풀어야 했던 세 가지 문제로 묶었다.')
pic(s, P5 + 'toc.jpg', 0, 0, 527, 720)
tb(s, 580, 44, 600, 42, 'Contents', size=20, color=NAVY, w8='x', anchor='m')
toc = [('01', '프로젝트 배경과 개요', '개발 동기, 기존 방식의 문제와 해결, 비교, 개요'),
       ('02', '시스템 구성과 과제', '전체 아키텍처, 풀어야 했던 세 가지 문제'),
       ('03', '문제 1 · 단계 인식', '데이터와 모델, 처리 과정, 비교 실험, 나사 A로 따라가기'),
       ('04', '문제 2 · 양안 정합', '눈별 투영, 보정과 확인'),
       ('05', '문제 3 · 가림과 복구', '추적과 진행의 분리, 시연 기록으로 확인'),
       ('06', '구현 결과와 검증', '구현 화면, 시연, 검증 결과, 성과와 한계')]
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
s = new('[전체 시스템 아키텍처] 참고 영상 2:46~3:49. HMM은 도식대로 설명한다: MediaPipe 손 랜드마크의 손 동작 특징과 ArUco ROI · 도구 특징을 HMM · Viterbi 단계 추정에 넣고, 그 결과가 FSM S0~S6으로 이어진다. 시간 증거 게이트(접근 → 유지 800ms → 이탈 400ms)의 유효 증거도 FSM으로 들어간다.')
header(s, 'Architecture', '카메라 영상에서 안경의 안내까지, 한 흐름으로 이어집니다')
pic(s, P5 + 'arch.png', 71, 100, 1138, 1138 * 732 / 1530)
src(s, 'VITURE Beast · Windows 노트북 · Python 판단 · Unity SBS · 웹 관제', y=664)

# ================================================================== 8 세 가지 문제
s = new('[풀어야 했던 세 가지 문제] 여기서부터 15장까지는 이 세 문제를 차례로 다룬다. 장마다 문제 → 원인 → 선택한 방법 → 확인 순서로 말한다. '
        '1. 검출 결과("드라이버가 보인다")를 작업 단계로 바꾸는 문제. 2. 카메라에서 맞는 위치가 안경에서는 어긋나는 문제. 3. 손이 마커를 가리면 작업이 다시 시작되던 문제.')
header(s, 'Challenges', '만들면서 풀어야 했던 문제는 세 가지였습니다')
ch = [('문제 1 · 단계 인식', IMG['p2'], ['드라이버가 보이는 것과', '지금 몇 단계인지는 다르다'], '한 프레임의 검출은 도구가 스치거나 가려지는 순간에 틀립니다.', '데이터 수집 → 비교 실험 → 이어진 관측으로 판단'),
      ('문제 2 · 양안 정합', PR5 + 'ch2.jpg', ['카메라에서 맞는 위치가', '안경에서는 어긋난다'], '카메라와 두 눈은 자리가 다르고, 쓸 때마다 조금씩 달라집니다.', '눈별 투영 → 양안 보정 → 착용 확인'),
      ('문제 3 · 가림과 복구', PR5 + 'ch3.jpg', ['손이 마커를 가리면', '작업이 처음으로 돌아간다'], '추적이 끊긴 것과 작업이 취소된 것을 구분하지 않았습니다.', '추적과 진행 분리 → 진행 보존 → 기록으로 확인')]
for k, (kc, im, q, why, how) in enumerate(ch):
    x = 71 + k * 385
    pic(s, im, x, 106, 368, 190)
    tb(s, x, 306, 368, 22, kc, size=12, color=ORANGE, w8='x', anchor='m')
    tb(s, x, 330, 368, 76, q, size=19.5, color=NAVY, w8='x', ls=1.22)
    hline(s, x, 414, 368)
    tb(s, x, 422, 60, 20, '원인', size=10.5, color=GREY, w8='x', anchor='m')
    tb(s, x, 442, 362, 50, why, size=13, color=BODY, ls=1.38)
    tb(s, x, 502, 60, 20, '푼 방법', size=10.5, color=GREY, w8='x', anchor='m')
    tb(s, x, 522, 368, 26, how, size=13, color=NAVY, w8='x', anchor='m')
hline(s, 71, 574, 1138); hline(s, 71, 644, 1138)
tb(s, 71, 574, 170, 70, '공통된 방법', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 240, 574, 960, 70, '원인을 나눠서 재고, 설계를 바꾼 뒤, 다시 확인했습니다.', size=18, color=NAVY, w8='x', anchor='m')

# ================================================================== 9 데이터와 모델
s = new('[데이터 수집과 인식 모델] 1학기 작업. 모델을 가져다 실행한 것이 아니라 조립 데이터를 직접 모으고 라벨을 붙였다. '
        'Unity로 만든 Quest 3 캡처 앱으로 조립 한 번을 약 60초, 초당 2장(세션당 약 120장)씩 저장. 학습용 16세션 약 1,920프레임, 시험용으로 session 17을 따로 촬영. '
        'YOLO 학습에는 세션마다 약 60장, 모두 970장을 골라 Roboflow에서 driver · handle · screw를 표시했다(밝기 · 노출 · 블러 · 회전 증강, train/valid/test 분리, YOLOv11). '
        '프레임마다 ROI 상태 점수, 도구 위치와 나사까지의 거리, 손 좌표를 뽑아 단계 추정의 입력으로 썼다. '
        '수치는 1학기 최종 보고서 기준. mAP@50 94.0%는 2026. 5. 16 학습본(3종 재학습 전)의 Roboflow 시험 세트 39장 값이다.')
header(s, 'Dataset', '조립 장면을 직접 찍고, 라벨을 붙여 검출 모델을 학습했습니다'); kicker(s, '문제 1 · 단계 인식')
ds = [('ds1.jpg', '촬영', 'Unity로 만든 Quest 3 캡처 앱으로 조립 한 번을 60초, 초당 2장씩 저장했습니다.'),
      ('ds2.jpg', '정면 보정', 'ArUco 마커로 작업대를 위에서 본 좌표로 펴서, 시점이 달라져도 같은 자리를 봅니다.'),
      ('ds3.jpg', '라벨링 · 학습', '드라이버 · 손잡이 · 나사를 하나씩 표시하고 YOLOv11을 학습했습니다.'),
      ('ds4.jpg', '특징 추출', '영역 점수, 도구 끝과 나사의 거리, 손 위치를 프레임마다 뽑았습니다.')]
for k, (im, a_, b_) in enumerate(ds):
    x = 71 + k * 288.7
    pic(s, PR5 + im, x, 106, 272, 170)
    rect(s, x, 276, 272, 3, fill=NAVY)
    tb(s, x, 290, 272, 30, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, x, 322, 268, 74, b_, size=12.5, color=BODY, ls=1.38)
    if k < 3: arw(s, x + 272, 178, color=NAVY, size=13, w=17)
chip(s, 71 + 288.7 + 8, 114, '원본', fill=WHITE, color=NAVY, size=9.5, w=46, h=20, w8='x')
chip(s, 71 + 288.7 + 146, 114, '보정 후', fill=WHITE, color=NAVY, size=9.5, w=56, h=20, w8='x')
tb(s, 71, 420, 300, 24, '규모', size=13, color=ORANGE, w8='x', anchor='m')
st = [('16 + 1', '세션', '학습용 16, 시험용 1 (session 17)'), ('약 1,920', '프레임', '세션마다 약 120장'),
      ('970', '장 라벨링', '드라이버 · 손잡이 · 나사 3종'), ('94.0%', 'mAP@50', 'YOLOv11 · 5월 학습본의 시험 세트')]
for k, (v, u, d_) in enumerate(st):
    x = 71 + k * 288.7
    hline(s, x, 452, 272, color=NAVY, lw=1.25)
    tb(s, x, 464, 272, 54, v, size=32, color=NAVY, w8='x', anchor='m')
    tb(s, x, 522, 272, 24, u, size=13.5, color=NAVY, w8='s', anchor='m')
    tb(s, x, 552, 272, 40, d_, size=12, color=BODY, ls=1.35)
hline(s, 71, 620, 1138)
src(s, '1학기 작업 (Meta Quest 3 카메라) · 수치는 1학기 최종 보고서 기준 · mAP는 2026. 5. 16 학습본을 Roboflow 시험 세트 39장으로 잰 값', y=664)

# ================================================================== 10 파이프라인
s = new('[핵심 처리 과정 세 단계] 참고 영상 3:49~4:57. 단계마다 무엇을 넣고 무엇이 나오는지 말한다.')
header(s, 'Pipeline', '위치 계산, 도구 관측, 단계 판단의 세 단계로 처리합니다'); kicker(s, '문제 1 · 단계 인식')
pipe = [('위치 계산', 'p1', [('ArUco 검출 · PnP 자세', '등록한 마커로 작업대의 좌표를 잡습니다.'), ('나사 A ~ D 위치 투영', '등록된 나사 위치를 영상 좌표로 옮깁니다.')]),
        ('도구 관측', 'p2', [('YOLO 도구 검출', '영상에서 드라이버를 찾습니다.'), ('도구 끝 · 거리 점수', '도구 끝과 목표 나사 사이의 거리를 봅니다.')]),
        ('단계 판단', 'p3', [('시간 증거 게이트', '접근 → 유지 → 이탈이 이어질 때만 인정합니다.'), ('HMM 단계 추정 · FSM S0 – S6', '단계를 추정하고, 현재 목표와 다음 행동을 정해 보냅니다.')])]
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

# ================================================================== 11 비교 실험
s = new('[시간 흐름을 이용한 단계 추정] 1학기 오프라인 실험. 같은 조립 한 번(session 17, 119프레임)을 세 방법으로 판단해 정답 라벨과 비교했다. '
        '프레임별 판단은 7번째와 26번째 프레임에서 순간적으로 다른 단계로 튄다(드라이버가 잠깐 근처에 보였다고 완료로 판단). 정확도 88.24%, macro-F1 89.52%. '
        'FSM은 순서 규칙으로 튐을 없앴지만 마지막 전환이 5프레임 늦다. 91.60%, 93.23%. '
        'HMM은 관측 점수와 전이 확률(유지 0.76, 다음 0.24)을 함께 써서 Viterbi로 상태열을 고른다. 94.12%, 94.85%. 남은 오류 7프레임은 경계에서 1~3프레임 늦게 넘어간 것이다. '
        '한 세션 기준의 결과라는 점을 말한다. 이 결과를 바탕으로 2학기에는 이어진 관측으로 단계를 정하는 구조를 실시간으로 옮겼다(도식 기준: 시간 증거 게이트, HMM · Viterbi 단계 추정, FSM).')
header(s, 'Experiment', '한 장면만 보고 판단하면 틀립니다'); kicker(s, '문제 1 · 단계 인식')
tb(s, 71, 96, 720, 30, '같은 조립 한 번(119프레임)을 세 가지 방법으로 판단해 정답과 비교했습니다.', size=14, color=BODY, anchor='m')
lx = 918
rect(s, lx, 108, 26, 5, fill='BEC8D6'); tb(s, lx + 32, 100, 40, 22, '정답', size=11, color=BODY, anchor='m')
rect(s, lx + 82, 110, 26, 2, fill=NAVY); tb(s, lx + 114, 100, 40, 22, '판단', size=11, color=BODY, anchor='m')
rect(s, lx + 164, 105, 12, 12, fill='F1D2B0'); tb(s, lx + 182, 100, 110, 22, '틀린 프레임', size=11, color=BODY, anchor='m')
ex3 = [('FW', '프레임별 판단', '프레임마다 따로 판단', '88.2%', '119프레임 가운데 14개 틀림', '7 · 26번째 프레임에서 순간적으로 다른 단계로 튐'),
       ('FSM', '규칙 기반 FSM', '정해진 순서만 허용', '91.6%', '10개 틀림', '튐은 없지만 마지막 전환이 5프레임 늦음'),
       ('HMM', 'HMM · Viterbi', '관측 점수와 전이 확률을 함께 봄', '94.1%', '7개 틀림', '튐이 없고, 경계에서 1 ~ 3프레임만 늦음')]
for k, (key, a_, b_, acc, err, note) in enumerate(ex3):
    y = 136 + k * 126
    if k == 2:
        rect(s, 71, y, 1138, 122, fill=PALE); rect(s, 71, y, 4, 122, fill=NAVY)
    elif k == 0: hline(s, 71, y + 124, 1138)
    tb(s, 93, y + 26, 186, 30, a_, size=17, color=NAVY, w8='x', anchor='m')
    tb(s, 93, y + 58, 186, 40, b_, size=11.5, color=BODY, ls=1.35)
    pic(s, PR5 + 'tl_%s.png' % key, 283, y + 7, 700, 108)
    tb(s, 283, y + 12, 26, 14, 'S6', size=8.5, color=LGREY, align='r', anchor='m')
    tb(s, 283, y + 94, 26, 14, 'S0', size=8.5, color=LGREY, align='r', anchor='m')
    tb(s, 1003, y + 6, 200, 40, acc, size=27, color=NAVY, w8='x', anchor='m')
    tb(s, 1003, y + 46, 200, 18, err, size=11, color=GREY, anchor='m')
    tb(s, 1003, y + 68, 200, 40, note, size=11.5, color=BODY, ls=1.25)
for f, xx in [('1', 30.0), ('30', 192.7), ('60', 361.0), ('90', 529.3), ('119', 692.0)]:
    tb(s, 283 + xx - 20, 512, 40, 14, f, size=8.5, color=LGREY, align='c', anchor='m')
tb(s, 283 + 716, 512, 60, 14, '프레임', size=8.5, color=LGREY, anchor='m')
hline(s, 71, 544, 1138); hline(s, 71, 640, 1138)
tb(s, 71, 544, 170, 96, '실험에서 얻은 것', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 240, 554, 960, 36, '한 프레임의 검출이 아니라, 이어진 관측과 순서를 함께 봐야 단계가 흔들리지 않습니다.', size=17, color=NAVY, w8='x', anchor='m')
tb(s, 240, 594, 960, 28, '2학기에는 이 판단을 실시간 구조로 옮겼습니다:  시간 증거 게이트  →  HMM · Viterbi 단계 추정  →  FSM', size=13, color=BODY, anchor='m')
src(s, '1학기 오프라인 실험 · Meta Quest 3로 찍은 session 17 한 세션(119프레임, 초당 2장) 기준 · macro-F1은 89.5 / 93.2 / 94.9%', y=664)

# ================================================================== 12 예시
s = new('[예시로 따라가기] 참고 영상 4:57~5:56. 사례 하나(여기서는 나사 A)로 처리 과정을 처음부터 끝까지 보여준다. 화면은 take4의 0:38, 0:43, 0:46, 0:50. 검은 줄은 그때 Unity 화면에 나온 문구. 촬영용 설정이라 초록 안내 2초 뒤에 넘어간다.')
header(s, 'Example', '나사 A 하나로 처리 과정을 따라가 봅니다'); kicker(s, '문제 1 · 단계 인식')
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

# ================================================================== 13 양안 투영
NOTES.append('[양안 투영] 참고 영상에는 없는 장. 같은 원을 양쪽에 복사하는 것이 아니라, 같은 나사 위치를 왼눈과 오른눈에 각각 계산한다. '
             'ArUco와 PnP로 카메라 자세를 구하고, 나사 A~D를 카메라 기준 3D 좌표로 바꾼 뒤, 눈별 투영 행렬(3×4)로 화면 좌표를 구한다. '
             'Unity는 좌우 1920×1080 화면을 나란히 붙인 Full SBS(3840×1080)로 내보낸다. 보정값은 미리 구하고 표시 위치만 실시간으로 다시 계산한다. '
             '위 그림은 작업대 사진에 Unity 왼눈 화면을 맞춰 얹은 재현 이미지이고, 아래 세 그림은 take4 0:45의 Unity 출력이다.')
s = stereo_slide(d); kicker(s, '문제 2 · 양안 정합')

# ================================================================== 14 보정
s = new('[보정과 확인] 참고 영상에는 없는 장. 보정 절차: 같은 착용 상태에서 목표 원을 실제 나사에 맞추고 그 순간의 3D 좌표와 좌우 화면 좌표를 저장 → 양안 공동 최적화 → 저장 후 자동 적용. '
        '처음에는 눈마다 따로 계산하는 독립 DLT(22변수)와 비교했고, PD 64mm를 참고값(약한 제약)으로 쓰는 공통 양안 모델(13변수)로 정리했다. '
        '화면에 넣지 않은 수치: 보정 관측 8개, 화면 좌표 적합 RMS 약 5.57px, 한 관측씩 빼고 예측한 최대 오차 약 27.79px. '
        '이 수치는 저장한 정렬 좌표에 대한 계산 결과이며 실물 정합 정확도가 아니다. 그래서 숫자 대신 무엇을 바꿔 가며 어떻게 확인했는지를 말한다. '
        '확인은 2026년 11월 14일 같은 착용 세션에서 착용자가 눈으로 본 것이다.')
header(s, 'Calibration', '보정은 한 번 해 두고, 거리와 시점을 바꿔 가며 확인했습니다'); kicker(s, '문제 2 · 양안 정합')
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
CAL = os.environ.get('CAL', 'line')
if CAL == 'line': rect(s, 552.25, 147, 1.5, 184, fill=LBLUE)                 # 세 단계를 잇는 세로선
for k, (a_, b_) in enumerate(cal):
    y = 132 + k * 92
    if CAL == 'line':
        rect(s, 546.5, y + 8.5, 13, 13, fill=WHITE, line=NAVY, lw=2, shape=MSO_SHAPE.OVAL)
        tb(s, 579, y, 628, 30, a_, size=17, color=NAVY, w8='x', anchor='m')
        tb(s, 579, y + 32, 628, 50, b_, size=12, color=BODY, ls=1.35)
    else:
        tb(s, 545, y - 2, 50, 34, '0%d' % (k + 1), size=20, color=LBLUE, w8='x', anchor='m')
        tb(s, 599, y, 608, 30, a_, size=17, color=NAVY, w8='x', anchor='m')
        tb(s, 599, y + 32, 608, 50, b_, size=12, color=BODY, ls=1.35)
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
        numcircle(s, 432 + j * 34, y + 24, c, d=26, fill=PALE, color=NAVY, size=11)
    tb(s, 596, y, 220, 74, c_, size=15, color=NAVY, w8='x', anchor='m')
    hline(s, 71, y + 74, 750)
rect(s, 852, 454, 357, 181, fill=PALE)
tb(s, 874, 466, 300, 22, '이 확인의 범위', size=12, color=GREY, w8='x', anchor='m')
for k, t_ in enumerate(['착용자가 눈으로 본 정성 확인입니다.', '어긋남과 표시 끊김은 따로 기록했습니다.', '보정 계산의 오차를 실물 정합 정확도로 쓰지 않습니다.']):
    y = 496 + k * 38
    rect(s, 874, y + 8, 5, 5, fill=GREY, shape=MSO_SHAPE.OVAL)
    tb(s, 890, y, 304, 40, t_, size=12.5, color=TXT, w8='s', ls=1.3)
src(s, '참고: Hartley · Zisserman, Multiple View Geometry / Seitz, Camera Calibration — 특정 논문을 그대로 구현한 것이 아니라 투영 기하의 원리를 적용했습니다', y=664)

# ================================================================== 15 가림과 복구
s = new('[가림 이후 진행 복구] 손이 마커를 가렸을 때 작업이 처음부터 다시 시작되던 문제. 원인은 "추적이 잠시 끊김"과 "작업 진행이 취소됨"을 같은 상태로 다룬 것. '
        '추적 상태와 작업 진행을 따로 두어, 끊기면 진행은 보존하고 안내만 멈춘 뒤 다시 보이면 재확인하고 이어 가도록 바꿨다(도식의 PAUSED, 진행 보존 · 복구 · 재확인). '
        '확인: take4 시연의 Unity 화면에서 윤곽 표시가 꺼진 시간을 0.1초 단위로 쟀다. 121.5초 가운데 38.3초(31.5%), 1초 넘게 꺼진 구간 10번, 가장 긴 구간 6.0초. 이 동안 단계 글자는 한 번도 뒤로 가지 않았다. '
        '한 번의 기록이고 짧은 가림에 대한 결과다. 가림을 언제나 견딘다고 말하지 않는다. 개선 전 기록과의 비교 그래프는 자료가 없어 넣지 않았다.')
header(s, 'Recovery', '잠깐 안 보여도, 한 일은 지우지 않습니다'); kicker(s, '문제 3 · 가림과 복구')
rc = [('문제', '가리면 처음부터 다시 시작됐습니다', '손이 마커를 가리는 순간 안내가 꺼지고, 진행한 단계가 사라졌습니다.'),
      ('원인', '끊김과 취소를 같은 것으로 다뤘습니다', '마커를 잠깐 못 본 것(추적 끊김)과 작업을 하지 않은 것(진행 취소)을 한 상태로 처리했습니다.'),
      ('선택한 방법', '추적과 진행을 따로 둡니다', '끊기면 진행은 그대로 두고 안내만 멈춥니다. 다시 보이면 확인한 뒤 이어 갑니다.')]
for k, (lab, a_, b_) in enumerate(rc):
    x = 71 + k * 385
    if k == 2:
        rect(s, x, 106, 368, 138, fill=PALE); rect(s, x, 106, 4, 138, fill=NAVY)
    else: rect(s, x, 106, 368, 138, line=LINE, lw=1)
    tb(s, x + 22, 118, 200, 20, lab, size=11, color=ORANGE if k == 2 else GREY, w8='x', anchor='m')
    tb(s, x + 22, 142, 338, 30, a_, size=15.5, color=NAVY if k == 2 else TXT, w8='x', anchor='m')
    tb(s, x + 22, 178, 328, 58, b_, size=12.5, color=BODY, ls=1.4)
    if k < 2: arw(s, x + 367, 160, color=NAVY, size=13, w=19)
tb(s, 71, 262, 400, 24, '확인 · take4 시연 기록', size=13, color=ORANGE, w8='x', anchor='m')
rect(s, 846, 269, 14, 10, fill=NAVY); tb(s, 866, 262, 80, 24, '윤곽 보임', size=10.5, color=BODY, anchor='m')
rect(s, 946, 269, 14, 10, fill=ORANGE); tb(s, 966, 262, 243, 24, '윤곽 꺼짐 (손 · 도구가 마커를 가림)', size=10.5, color=BODY, anchor='m')
pic(s, PR5 + 'recovery.png', 71, 292, 1138, 176)
tb(s, 71, 299, 90, 20, '윤곽 표시', size=10.5, color=GREY, w8='s', anchor='m')
tb(s, 71, 334, 90, 20, '작업 단계', size=10.5, color=GREY, w8='s', anchor='m')
steps_ = ['상자 배치', '뚜껑 닫기', '나사 A', '나사 B', '나사 C', '나사 D', '최종 확인']
sx = [96.0, 206.2, 324.9, 514.8, 699.6, 948.8, 1102.3]
for k, (t_, x_) in enumerate(zip(steps_, sx)):
    yy = 292 + 156 - k * (98 / 6) - 19
    if k == 6: tb(s, 1209 - 90, yy, 90, 16, t_, size=9.5, color=NAVY, w8='s', align='r', anchor='m')
    else: tb(s, 71 + x_ + 6, yy, 100, 16, t_, size=9.5, color=NAVY, w8='s', anchor='m')
for t_, x_ in [('0:00', 96.0), ('0:30', 350.3), ('1:00', 604.6), ('1:30', 859.0), ('2:00', 1113.3)]:
    tb(s, 71 + x_ - 22, 468, 44, 14, t_, size=8.5, color=LGREY, align='c', anchor='m')
rs_ = [('38초', '윤곽이 꺼진 시간', '2분 1초 가운데 약 32%'), ('10번', '1초 넘게 꺼진 구간', '가장 긴 구간은 6초'), ('0번', '단계가 뒤로 돌아간 횟수', '일곱 단계가 순서대로 끝남')]
for k, (v, a_, b_) in enumerate(rs_):
    x = 71 + k * 385
    hline(s, x, 502, 368, color=NAVY, lw=1.25)
    tb(s, x, 514, 130, 60, v, size=30, color=NAVY, w8='x', anchor='m')
    tb(s, x + 136, 518, 232, 26, a_, size=14.5, color=NAVY, w8='x', anchor='m')
    tb(s, x + 136, 546, 232, 22, b_, size=12, color=BODY, anchor='m')
hline(s, 71, 600, 1138)
tb(s, 71, 606, 1138, 30, '가려진 동안에는 안내만 멈추고, 다시 보이면 하던 단계에서 이어 갔습니다.', size=15, color=NAVY, w8='x', anchor='m')
src(s, 'take4 시연 한 번을 Unity 화면에서 0.1초 단위로 잰 기록 · 짧은 가림에 대한 결과이며, 오래 가려지는 경우는 더 확인이 필요합니다', y=664)

# ================================================================== 16 구현 화면
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

# ================================================================== 17 시연
s = new('[실제 시연] 참고 영상 6:34~8:11. 영상은 한 번만 재생하고, 단계가 바뀌는 순간에 말을 맞춘다. '
        '영상은 작업대 카메라 화면에 안경(Unity)의 안내 글자를 합성한 재현이다(06-camera-composite-full). 안경 렌즈를 통해 찍은 영상이 아니다. '
        '단계가 바뀌는 네 곳에서 카메라의 노란 표시와 글자가 바뀌는 때의 차이는 0.07초 안쪽이다. '
        '상자 둘레의 가는 흰 선은 Unity 윤곽을 카메라 시점으로 옮긴 것이라 청록 선과 조금 어긋나 보인다. 실제 안경 화면은 10장에 있다. 손이나 도구가 마커를 가리면 윤곽이 잠깐 사라진다. '
        '촬영용 설정: 초록 안내 2초 뒤 자동 전환. 조임 완료를 자동으로 검증한 자료가 아니며, 마지막은 최종 확인을 요청하는 장면까지다.')
header(s, 'Demo', '상자 하나를 처음부터 끝까지 조립합니다')
s.shapes.add_movie(PR + 'demo_comp.mp4', px(71), px(104), px(896), px(504), poster_frame_image=PR + 'poster_comp.jpg', mime_type='video/mp4')
tb(s, 71, 614, 896, 18, '카메라 화면에 안경의 안내 글자를 합성한 재현 영상 (2분 1초 · 소리 없음). 안경 렌즈를 통해 찍은 영상은 아닙니다.', size=9.5, color=LGREY, anchor='m')
tb(s, 991, 104, 218, 24, '영상에서 볼 곳', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 991, 136, 218, color=NAVY, lw=1.25)
tl = [('0:00', '상자 배치', '상자를 놓아주세요'), ('0:13', '뚜껑 닫기', '뚜껑을 덮어주세요'), ('0:27', '나사 A', '나사 A를 조여주세요'), ('0:50', '나사 B', '나사 B를 조여주세요'),
      ('1:11', '나사 C', '나사 C를 조여주세요'), ('1:41', '나사 D', '나사 D를 조여주세요'), ('1:59', '최종 확인', '조립 상태를 확인해주세요')]
for k, (tm, a_, ph) in enumerate(tl):
    y = 136 + k * 68
    tb(s, 991, y, 54, 68, tm, size=15, color=LBLUE, w8='x', anchor='m')
    tb(s, 1047, y + 11, 162, 26, a_, size=15.5, color=NAVY, w8='x', anchor='m')
    tb(s, 1047, y + 37, 162, 20, ph, size=10, color=GREY, anchor='m', wrap=False)
    hline(s, 991, y + 68, 218)
src(s, '촬영용 설정으로 초록 안내 2초 뒤 다음 단계로 넘어갑니다 · 카메라와 Unity 화면은 따로 녹화한 것으로, 시간을 맞춰 합성했습니다', y=664)

# ================================================================== 18 검증 결과
s = new('[검증 결과] 무엇을 구현했는지가 아니라 무엇을 어떤 조건에서 확인했는지 나눠서 말한다. '
        '오프라인 인식은 1학기 session 17 한 세션의 정량 결과, 실시간 동작은 take4 시연 한 번의 기록, 착용 정합은 착용자의 정성 확인이다. 셋을 섞어 말하지 않는다. '
        '여러 사람 · 여러 번의 반복 성공률, 실물 기준 위치 오차, 지연 시간은 아직 재지 못했다고 먼저 말한다.')
header(s, 'Evaluation', '무엇을 어떤 조건에서 확인했는지 나눠서 봅니다')
for x, w, t_ in [(87, 170, '확인한 것'), (268, 330, '조건'), (616, 440, '결과'), (1076, 120, '성격')]:
    tb(s, x, 104, w, 34, t_, size=12, color=GREY, w8='x', anchor='m')
hline(s, 71, 138, 1138, color=NAVY, lw=1.25)
ev = [('오프라인 인식', ['1학기 · Quest 3로 찍은 session 17', '119프레임을 정답 라벨과 비교'], ['HMM 정확도 94.1% (macro-F1 94.9%)', '프레임별 판단 88.2%, FSM 91.6%'], '정량', NAVY, WHITE),
      ('실시간 동작', ['2학기 · take4 시연 1회 (2분 1초)', '촬영용 설정'], ['일곱 단계가 순서대로 진행', '윤곽이 꺼진 38초 동안에도 단계 유지'], '기록 1회', PALE, NAVY),
      ('착용 정합', ['2학기 · 2026. 11. 14 · 같은 착용 상태', '착용자가 눈으로 확인'], ['나사 A ~ D 모두 거리와 시점을 바꿔도', '대체로 하나로 겹침'], '정성', PALE, NAVY)]
for k, (a_, c_, r_, kind, cf, cc) in enumerate(ev):
    y = 138 + k * 84
    tb(s, 87, y, 170, 84, a_, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, 268, y, 330, 84, c_, size=13, color=BODY, anchor='m', ls=1.4)
    tb(s, 616, y + 14, 440, 28, r_[0], size=15, color=NAVY, w8='x', anchor='m')
    tb(s, 616, y + 44, 440, 24, r_[1], size=13, color=BODY, anchor='m')
    chip(s, 1076, y + 29, kind, fill=cf, color=cc, size=10.5, w=80 if len(kind) > 2 else 56, h=26, w8='x')
    hline(s, 71, y + 84, 1138)
rect(s, 71, 404, 1138, 52, fill=PALE)
tb(s, 91, 404, 150, 52, '아직 재지 못한 것', size=12, color=GREY, w8='x', anchor='m')
tb(s, 250, 404, 940, 52, '여러 사람이 여러 번 했을 때의 성공률  ·  실물 기준 위치 오차(mm)  ·  안내가 뜨기까지의 지연 시간', size=13.5, color=TXT, w8='s', anchor='m')
tb(s, 71, 474, 400, 26, '사용하면서 고친 것', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 71, 506, 1138, color=NAVY, lw=1.25)
ut = [('상태 설명이 많아 지금 할 일을 찾기 어려움', '큰 행동 문구 한 줄과 목표 강조로 정리'),
      ('영문 상태 문구가 낯섦', '한글 행동 문구로 변경'),
      ('관측이 잠깐 끊기면 진행이 흔들림', '진행을 보존하고 다시 확인하도록 보강')]
for k, (a_, b_) in enumerate(ut):
    y = 506 + k * 44
    tb(s, 87, y, 520, 44, a_, size=13.5, color=BODY, anchor='m')
    arw(s, 615, y + 8, color=NAVY, size=13)
    tb(s, 655, y, 540, 44, b_, size=13.5, color=NAVY, w8='x', anchor='m')
    hline(s, 71, y + 44, 1138)
src(s, '정확도는 한 세션 기준의 오프라인 결과입니다. 실시간 동작과 착용 정합은 아직 수치로 재지 않았습니다', y=664)

# ================================================================== 19 성과와 한계
s = new('[성과와 한계] 참고 영상 9:19~10:16. 성과 세 가지는 8장의 세 문제와 하나씩 짝을 이룬다. 한계는 숨기지 않고 짧게.')
header(s, 'Results', '성과 세 가지와 남은 한계')
tb(s, 71, 104, 300, 26, '성과', size=13, color=ORANGE, w8='x', anchor='m')
rs = [('한 장면이 아니라 흐름으로 단계를 판단', '조립 데이터를 직접 모아 비교한 결과를 바탕으로, 이어진 관측으로 단계를 정합니다. 나사 A ~ D는 드라이버의 움직임을 보고 넘어갑니다.'),
      ('두 눈에 따로 계산해 실물과 겹친 안내', '카메라에서 찾은 나사를 눈별 투영으로 옮기고, 보정한 뒤 거리와 시점을 바꿔 확인했습니다.'),
      ('가려져도 이어지는 진행', '추적이 끊긴 것과 작업이 취소된 것을 나눠, 윤곽이 꺼진 동안에도 단계를 지켰습니다.')]
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

# ================================================================== 20 마무리
s = new('[마무리] 참고 영상 10:16.')
pic(s, IMG['close'], 0, 0, 1280, 720)
tb(s, 85, 176, 900, 170, ['눈앞에는 다음 작업을,', '관제에는 전체 흐름을.'], size=40, color=WHITE, w8='x', ls=1.22)
rect(s, 87, 366, 40, 2, fill=LBLUE)
tb(s, 85, 384, 520, 60, ['AI Assembly Guide는 조립 순서를 따라', '작업을 이어가도록 돕습니다.'], size=17, color='D9E2F0', ls=1.4)
tb(s, 85, 572, 600, 28, 'AI Assembly Guide', size=19, color=WHITE, w8='x', anchor='m')
tb(s, 85, 602, 900, 22, '작업 단계 인식 기반 AR 조립 안내', size=13, color='D9E2F0', anchor='m')
tb(s, 85, 634, 900, 22, '개발 최민준 C011207   |   지도교수 윤영 교수님', size=12.5, color='D9E2F0', w8='m', anchor='m')

# ================================================================== 21 메모
s = new('영상에 넣지 않는 장.')
header(s, 'Memo', '구조 테스트 메모 — 영상에는 넣지 않는 장')
rect(s, 71, 100, 1138, 30, fill=PALE)
for x, w, t_ in [(87, 110, '장'), (200, 330, '내용'), (540, 650, '확인하거나 채울 것')]:
    tb(s, x, 100, w, 30, t_, size=11.5, color=NAVY, w8='x', anchor='m')
mm = [('3 · 4 · 5', '개발 동기, 문제와 해결, 비교표', '핵심 목표 문장과 비교표 문구는 초안. 고쳐 주신 두 칸은 그대로 둠'),
      ('7', '전체 아키텍처', 'HMM은 도식대로, 실시간에서 돈다는 전제로 적음 → 아래 첫 줄'),
      ('8', '새 장 · 풀어야 했던 세 가지 문제', '세 질문은 코덱스 정리 기준. 원인 문장은 제가 풀어 쓴 것 → 확인'),
      ('9', '새 장 · 데이터와 모델', '1학기 최종 보고서 기준 (16 + 1세션, 약 1,920프레임, 970장). 5월 발표 자료의 12세션 · 400장과 다름'),
      ('10 · 12', '처리 과정 세 단계, 나사 A로 따라가기', '10장 셋째 칸에 "HMM 단계 추정"을 넣음. 12장의 검은 줄은 take4 Unity 화면의 문구'),
      ('11', '새 장 · 비교 실험', '보고서의 타임라인을 다시 그림. 프레임별 값이 보고서의 정확도 · F1과 소수 둘째 자리까지 맞음'),
      ('13 · 14', '양안 투영, 보정과 확인', '13장에 투영식 한 줄을 넣음. 관측 8개 · RMS · 제외 예측 오차는 노트에만'),
      ('15', '새 장 · 가림과 복구', 'take4 Unity 화면에서 직접 잰 값. 개선 전 기록은 자료가 없어 넣지 않음 → 로그가 있으면 전후 비교로 바꿈'),
      ('17', '실제 시연', '합성본 (카메라 화면 + 안경 안내 글자). 전환 네 곳의 시간 차 0.07초 안쪽'),
      ('18 · 19', '검증 결과, 성과와 한계', '19장 성과 세 가지를 세 문제에 맞춰 다시 씀 ("혼자 시작하고 끝내는 구성"은 빠짐) → 확인')]
for k, (n, a_, b_) in enumerate(mm):
    y = 130 + k * 36
    tb(s, 87, y, 110, 36, n, size=11.5, color=ORANGE, w8='x', anchor='m')
    tb(s, 200, y, 330, 36, a_, size=11, color=TXT, anchor='m')
    tb(s, 540, y, 660, 36, b_, size=11, color=BODY, anchor='m', ls=1.2)
    hline(s, 71, y + 36, 1138)
tb(s, 71, 500, 1138, 150, ['· HMM: "실시간에서 돌아간다"는 전제로 7 · 10 · 11장에 적었음. 코덱스 구성안에는 "현재 실시간 단계 전이를 HMM이 직접 수행한다고 설명하지 않는다"는 줄이 있으므로, 질문이 나오면 답할 문장을 정해 둘 것',
                           '· 94.1%는 session 17 한 세션 기준. 파라미터 탐색(그리드 서치)을 같은 세션에서 했다면 그렇게 말해야 함. mAP 94.0%는 5월 학습본(3종 재학습 전)의 값',
                           '· v4에서 바뀐 것: 새 장 넷(8 · 9 · 11 · 15), 18장 다시 구성, 일곱 단계 장을 뺌, 목차를 세 문제 기준으로 바꿈. 길이가 넘치면 5장과 16장이 먼저 줄일 후보',
                           '· take4는 촬영용 설정(초록 안내 2초 뒤 자동 전환)으로 찍은 영상. 12 · 17장 아래에 적어 둠. 조임 완료를 자동으로 검증한 자료가 아님',
                           '· 사진: 2 · 3장은 Unsplash (@maciejka_dslr), 표지의 안경은 VITURE 제품 이미지, 9장은 1학기 발표 자료의 화면. 글꼴은 Pretendard Bold를 쓰지 않음'], size=10.5, color=BODY, ls=1.45)

# ------------------------------------------------------------------ 저장
lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
for sl, n in zip(d.prs.slides, NOTES):
    if n: sl.notes_slide.notes_text_frame.text = n
d.save()
