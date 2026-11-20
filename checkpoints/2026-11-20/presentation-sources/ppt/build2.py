# -*- coding: utf-8 -*-
"""AI Assembly Guide — 졸업프로젝트 영상용 PPT v2 (센티언트 하우스 스타일: 흰 바탕 · 네이비 · Pretendard).
표지는 AR 테크 교육 제안서 v8과 같은 구성. 발표자 노트는 v1에서 가져온다. 사용: python3 build2.py [OUT.pptx]
"""
import sys, os, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip, numcircle
from prep import make
import numpy as np
from PIL import Image
from pptx import Presentation
from pptx.enum.dml import MSO_LINE_DASH_STYLE

W_ = '/home/claude/grad'
A = '/mnt/user-data/uploads/AI_Assembly_Video_Pack_20261115/'
P = W_ + '/photo/'; FR = W_ + '/frames/'; PR = W_ + '/prep2/'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_영상용_v2.pptx'
os.makedirs(PR, exist_ok=True)
BLUE = '2F7FE0'; GREEN = '2FA35B'; BLACK = '0B0F14'; BODY = '333333'

# ------------------------------------------------------------------ 이미지 준비
def cover(src, w, h, fx=.5, fy=.5, scale=2):
    im = (Image.open(src) if isinstance(src, str) else src).convert('RGB'); Wd, Hd = int(w * scale), int(h * scale)
    r = max(Wd / im.width, Hd / im.height); im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x = int((im.width - Wd) * fx); y = int((im.height - Hd) * fy)
    return im.crop((x, y, x + Wd, y + Hd))

def shade(im, left=0, bottom=0, flat=0, top=0, c=(22, 38, 64)):
    a = np.asarray(im).astype(np.float32); h, w = a.shape[:2]
    xs = np.linspace(0, 1, w)[None, :, None]; ys = np.linspace(0, 1, h)[:, None, None]
    k = flat + left * np.clip(1 - xs / .72, 0, 1) ** 1.3 + bottom * np.clip((ys - .35) / .65, 0, 1) ** 1.3 + top * np.clip(1 - ys / .4, 0, 1) ** 1.5
    k = np.clip(k, 0, .96); cc = np.array(c, np.float32)[None, None, :]
    return Image.fromarray((a * (1 - k) + cc * k).astype(np.uint8))

IMG = {}
def sv(name, im, q=90):
    IMG[name] = PR + name + '.jpg'; im.save(IMG[name], quality=q); return IMG[name]

# 표지: 왼쪽 남색 → 오른쪽 청회색 바탕에 VITURE Beast 제품 사진을 곱해 얹는다 (테크 교육 제안서 표지와 같은 구성)
cw, ch = 2560, 1440
xs = np.linspace(0, 1, cw)[None, :, None]; ys = np.linspace(0, 1, ch)[:, None, None]
t = np.clip((xs - .26) / .74, 0, 1) ** 1.05
bg = (np.array([27, 46, 76], np.float32) * (1 - t) + np.array([138, 158, 180], np.float32) * t) * (1 - .22 * ys)
be = Image.open(A + '05_기기_로고/VITURE_Beast_사선_제품사진.jpg').convert('RGB'); sc = .72
be = be.resize((int(be.width * sc), int(be.height * sc)), Image.LANCZOS)
lay = Image.new('RGB', (cw, ch), 'white'); lay.paste(be, (470, -230))
sv('cover', Image.fromarray(np.clip(bg * np.asarray(lay).astype(np.float32) / 255, 0, 255).astype(np.uint8)), 92)

sv('toc', cover(P + 'maciejka_dslr-manual_parts.jpg', 527, 720, fx=.5))
sv('intro', shade(cover(P + 'maciejka_dslr-manual_blocks.jpg', 1280, 720), bottom=.9, flat=.3, top=.25))
sv('ar', cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 700, 467))
sv('ar_s', cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 500, 333))
sv('old', cover(W_ + '/scratch/pimg-002.png', 500, 333))
sv('aud1', cover(P + 'helloimnik-assemble_b.jpg', 368, 230))
sv('aud2', cover(P + 'helloimnik-assemble_a.jpg', 368, 230))
_c = Image.open(P + 'helloimnik-assemble_c.jpg').convert('RGB')
sv('aud3', cover(_c.crop((0, int(_c.height * .3), int(_c.width * .9), _c.height)), 368, 230, fy=1.0))
for k, (f, kw) in {'div2': ('redd_francisco-glasses_hold.jpg', {}), 'div3': ('steve_j-screwdriver.jpg', {}),
                   'div4': ('qiu_dexing-3dmodel.jpg', {'fy': .62}), 'div5': ('myblu-worktable.jpg', {})}.items():
    sv(k, shade(cover(P + f, 1280, 720, **kw), left=.55, flat=.42))
be2 = Image.open(A + '05_기기_로고/VITURE_Beast_사선_제품사진.jpg').convert('RGB')
sv('beast', cover(be2.crop((int(be2.width * .12), int(be2.height * .05), int(be2.width * .9), int(be2.height * .98))), 368, 245), 92)
sv('top', cover(A + '02_작업대_사진/작업대_위에서_원본.png', 368, 170, fy=.45))
sv('ready', cover(A + '04_관제/노트북_실행준비_화면.png', 739, 462, fy=0), 92)
sv('ctl', cover(A + '04_관제/관제_B_저장상태_발표용.png', 780, 418, fy=0), 92)
for k in ('aruco', 'yolo', 'mediapipe'):
    sv(k, cover(A + '03_AI_검출/검출_%s.png' % k, 368, 245))
sv('poster', Image.open(A + '03_AI_검출/원본영상_프레임_048.png').convert('RGB'))
g = Image.open(A + '01_Unity_안내/몸체_뚜껑_단계별_기하미리보기.png').convert('RGB')
for i in range(4):
    sv('geo%d' % i, g.crop((i * 480, 66, i * 480 + 480, 410)), 92)
h_ = Image.open(A + '01_Unity_안내/AR_B_투명_HUD_디자인.png').convert('RGBA')
b_ = Image.new('RGBA', h_.size, (11, 15, 20, 255)); b_.alpha_composite(h_); sv('hud', b_.convert('RGB'), 92)
def frame(n, name, w=380, h=214):
    sv(name, cover(Image.open(FR + 'f_%02d.png' % n).convert('RGB').crop((0, 24, 440, 360)), w, h))
frame(2, 'fr_box'); frame(12, 'fr_end')
sv('yolo_s', cover(A + '03_AI_검출/검출_yolo.png', 380, 214, fy=.3))
sv('near', shade(cover(A + '02_작업대_사진/작업대_편집용_크롭.png', 368, 300), bottom=.85, top=.45, c=(11, 15, 20)))
sv('far', shade(cover(A + '02_작업대_사진/작업대_카메라_원본.png', 368, 300, fx=.45), bottom=.85, top=.45, c=(11, 15, 20)))
sv('topv', shade(cover(A + '02_작업대_사진/작업대_위에서_원본.png', 368, 300, fx=.35), bottom=.85, top=.45, c=(11, 15, 20)))
sv('t_aruco', cover(A + '03_AI_검출/검출_aruco.png', 96, 56, fy=.6, scale=3))
sv('t_yolo', cover(A + '03_AI_검출/검출_yolo.png', 96, 56, fy=.3, scale=3))
sv('t_ar', cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 96, 56, fy=.3, scale=3))
sv('close', shade(cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 1280, 720, fy=.3), left=.75, flat=.45, top=.6, bottom=.9))
LOGO = lambda n: A + '05_기기_로고/logo_%s.png' % n

# ------------------------------------------------------------------ 도우미
d = Deck(out=OUT)

def credit(s, text, x=71, color=LGREY):
    tb(s, x, 692, 900, 18, text, size=8, color=color)

def tag(s, x, y, text, w=None):
    chip(s, x, y, text, fill=ORANGE, color=WHITE, size=10, w=w or (len(text) * 11 + 24), h=24, w8='b')

def dotc(s, x, y, dd=28, fill=NAVY, line=None, n='', color=WHITE, size=11.5):
    rect(s, x, y, dd, dd, fill=fill, line=line, lw=1.5, shape=MSO_SHAPE.OVAL)
    if n != '': tb(s, x, y, dd, dd, str(n), size=size, color=color, w8='x', align='c', anchor='m', wrap=False)

def arw(s, x, y, color=LBLUE, size=15, h=28):
    tb(s, x, y, 26, h, '→', size=size, color=color, w8='s', align='c', anchor='m', wrap=False)

def slot(s, x, y, w, h, title, desc=None, img=None, tagtext='녹화 영상 자리', imgnote=None, pad=0):
    r = rect(s, x, y, w, h, fill=BLACK, line=ORANGE, lw=1.5, name='SLOT'); r.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    if img:
        im = Image.open(img); ar = im.width / im.height; iw, ih = w - 2 * pad, h - 2 * pad
        pw, ph = (iw, iw / ar) if ar > iw / ih else (ih * ar, ih)
        pic(s, img, x + (w - pw) / 2, y + (h - ph) / 2, pw, ph)
    tag(s, x + 12, y + 12, tagtext)
    tb(s, x + 16, y + h - (54 if desc else 34), w - 32, 22, title, size=13, color=WHITE, w8='b', anchor='m')
    if desc: tb(s, x + 16, y + h - 32, w - 32, 20, desc, size=10.5, color='C9D3DD', anchor='m')
    if imgnote: tb(s, x + w - 316, y + 14, 300, 20, imgnote, size=9.5, color='8894A0', align='r', anchor='m')

# ================================================================== 1 표지
s = d.new()
pic(s, IMG['cover'], 0, 0, 1280, 720)
tb(s, 85, 92, 700, 28, '졸업프로젝트', size=14, color=LBLUE, w8='s', anchor='m')
rect(s, 85, 128, 40, 2, fill=LBLUE)
tb(s, 85, 150, 640, 130, ['AI Assembly Guide,', '눈앞에서 따라 하는 조립'], size=34, color=WHITE, w8='x', ls=1.18)
tb(s, 85, 296, 640, 30, '작업 단계 인식 기반 AR 조립 안내', size=16, color='D9E2F0', w8='m', anchor='m')
tb(s, 85, 640, 800, 24, '2026. 11   |   최민준 (C011207)   |   지도교수 윤영 교수님', size=12, color='D9E2F0')
credit(s, '이미지: VITURE (VITURE Beast 제품 이미지)', x=12, color='8FA3BC')

# ================================================================== 2 목차
s = d.new()
pic(s, IMG['toc'], 0, 0, 527, 720)
tb(s, 580, 44, 600, 42, 'Contents', size=20, color=NAVY, w8='x', anchor='m')
toc = [('01', '프로젝트 소개', '조립할 때 겪는 일, 완성된 안내, 누구를 위해 만들었나'),
       ('02', '사용 준비와 전체 흐름', '안경과 노트북 준비, 일곱 단계'),
       ('03', '핵심 시연', '상자와 뚜껑, 나사 A 한 사이클, 나사 B ~ D와 최종 확인, 공간 안내'),
       ('04', 'AI와 구현', '검출 영상, 검출 결과, 처리 흐름'),
       ('05', '관제와 개선', '관제 화면, 사용자 피드백과 개선')]
for k, (n, t_, sub) in enumerate(toc):
    y = 120 + k * 112
    tb(s, 580, y, 90, 56, n, size=32, color=LBLUE, w8='x', anchor='m')
    tb(s, 680, y, 500, 32, t_, size=19, color=NAVY, w8='x', anchor='m')
    tb(s, 680, y + 34, 520, 24, sub, size=12, color=GREY, anchor='m')
    hline(s, 580, y + 84, 630)
credit(s, 'Photo: @maciejka_dslr / Unsplash', x=12, color='C9D6E6')

# ================================================================== 3 도입
s = d.new()
pic(s, IMG['intro'], 0, 0, 1280, 720)
tb(s, 85, 60, 600, 24, '01  프로젝트 소개', size=13, color=LBLUE, w8='s', anchor='m')
tb(s, 85, 410, 1100, 150, ['어디부터, 어떤 순서로', '작업해야 할까요?'], size=38, color=WHITE, w8='x', ls=1.2)
tb(s, 85, 584, 1100, 28, '조립이 익숙하지 않으면 설명서와 부품을 번갈아 확인하게 됩니다.', size=17, color='D9E2F0', anchor='m')
credit(s, 'Photo: @maciejka_dslr / Unsplash', x=12, color='C9D6E6')

# ================================================================== 4 완성된 안내 먼저
s = d.new()
header(s, 'Guide', '지금 할 작업이 눈앞에 보입니다')
lead(s, '작업할 위치와 다음 행동을 AR 안경으로 보여줍니다.', y=96, h=30)
pic(s, IMG['ar'], 71, 140, 700, 467)
tag(s, 83, 152, '새 Unity 녹화로 교체')
pts = [('현재 나사만 강조', '작업할 나사 위치에 표시합니다.'), ('작은 단계 표시', '나사 B · 2/4'), ('행동 한 줄', '"나사 B를 조여주세요"')]
for k, (a_, b_) in enumerate(pts):
    y = 150 + k * 128
    numcircle(s, 805, y + 2, k + 1, d=30, size=13)
    tb(s, 849, y, 360, 34, a_, size=18, color=NAVY, w8='x', anchor='m')
    tb(s, 849, y + 38, 360, 26, b_, size=13.5, color=BODY, anchor='m')
    if k < 2: hline(s, 805, y + 96, 404)
rect(s, 805, 527, 404, 80, fill=PALE)
tb(s, 825, 527, 364, 80, '작업자는 눈앞의 안내를 따라가고, 관제 화면에서는 전체 진행을 확인합니다.', size=12.5, color=NAVY, w8='s', anchor='m', ls=1.45)
src(s, 'AR 안내 예시 · 실제 작업대 사진에 Unity 안내 디자인을 합친 설명용 이미지 (실시간 캡처 아님)', y=624)

# ================================================================== 5 누구를 위해
s = d.new()
header(s, 'Problem', '조립이 익숙하지 않은 작업자를 위해 만들었습니다')
lead(s, '조립 초보자와 실습자는 설명서를 반복해서 확인하고, 순서를 헷갈리기 쉽습니다.', y=96, h=30)
caps = [('설명서를 봅니다', '그림과 부품을 번갈아 확인합니다.'), ('부품을 맞춥니다', '손이 멈추면 순서를 다시 찾습니다.'), ('다시 설명서로 돌아갑니다', '어디까지 했는지 헷갈리기 쉽습니다.')]
for k, (a_, b_) in enumerate(caps):
    x = 71 + k * 385
    pic(s, IMG['aud%d' % (k + 1)], x, 140, 368, 230)
    rect(s, x, 370, 368, 4, fill=NAVY)
    numcircle(s, x, 388, k + 1, d=26, size=11.5)
    tb(s, x + 36, 386, 330, 30, a_, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, x + 36, 418, 330, 24, b_, size=12, color=BODY, anchor='m')
rect(s, 71, 476, 1138, 130, fill=NAVY)
rect(s, 640, 496, 1, 90, fill='5F7C9E')
for k, (a_, b_) in enumerate([('설명서를 보며 작업하면', '시선이 설명서와 작업대를 오갑니다.'), ('AR 안내로 작업하면', '작업 위치에서 다음 행동을 확인합니다.')]):
    x = 99 + k * 570
    tb(s, x, 496, 500, 24, a_, size=12.5, color='FFD2A6' if k else 'C5D5E8', w8='x', anchor='m')
    tb(s, x, 526, 520, 56, b_, size=21, color=WHITE, w8='x', anchor='m')
credit(s, 'Photo: @helloimnik / Unsplash')

# ================================================================== 6 간지 02
s = d.divider(IMG['div2'], '02', '사용 준비와 전체 흐름', '안경을 연결하고 작업을 시작하기까지')
credit(s, 'Photo: Redd Francisco / Unsplash', x=12, color='C9D6E6')

# ================================================================== 7 사용 준비
s = d.new()
header(s, 'Setup', '안경을 쓰고, 노트북에서 시작합니다')
pic(s, IMG['beast'], 71, 104, 368, 245)
rect(s, 71, 104, 368, 245, line=LINE, lw=.75)
tb(s, 71, 358, 368, 30, 'VITURE Beast', size=17, color=NAVY, w8='x', anchor='m')
tb(s, 71, 388, 368, 22, '양안 AR 표시 · Windows PC 연결', size=12, color=BODY, anchor='m')
pic(s, IMG['top'], 71, 428, 368, 170)
tb(s, 71, 604, 368, 18, '실제 작업대와 안경 (이전 배치 사진)', size=9.5, color=LGREY, anchor='m')
pic(s, IMG['ready'], 470, 104, 739, 462)
rect(s, 470, 104, 739, 462, line=LINE, lw=.75)
tb(s, 470, 572, 739, 18, '관제 준비 화면 캡처 (실행 전)', size=9.5, color=LGREY, anchor='m')
for k, t_ in enumerate(['안경을 연결하고 작업대를 봅니다', '연결을 확인합니다', '작업 시작을 누릅니다']):
    x = 470 + k * 250
    numcircle(s, x, 606, k + 1, d=26, size=11.5)
    tb(s, x + 36, 604, 210, 30, t_, size=12.5, color=NAVY, w8='x', anchor='m')
credit(s, '제품 이미지: VITURE')

# ================================================================== 8 전체 흐름
s = d.new()
header(s, 'Flow', '일곱 단계를 순서대로 안내합니다')
lead(s, '상자 배치와 뚜껑 닫기 뒤에 나사 A부터 D까지 작업하고, 최종 확인으로 마칩니다.', y=96, h=30)
tiles = [('1', '상자 배치', '몸체 윤곽'), ('2', '뚜껑 닫기', '뚜껑 윤곽'), ('3–6', '나사 A ~ D', '뚜껑 윤곽 + 현재 나사 강조'), ('7', '최종 확인', '전체 윤곽')]
TW = (1138 - 3 * 20) / 4
for k, (n, nm, d_) in enumerate(tiles):
    x = 71 + k * (TW + 20)
    rect(s, x, 140, TW, 200, fill=BLACK)
    pic(s, IMG['geo%d' % k], x + 4, 146, TW - 8, (TW - 8) * 344 / 480)
    chip(s, x + 10, 150, n, fill=WHITE, color=NAVY, size=11, w=48 if len(n) > 1 else 30, h=24, w8='x')
    tb(s, x, 348, TW, 28, nm, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, x, 376, TW, 20, d_, size=11.5, color=GREY, anchor='m')
rect(s, 110, 469, 1060, 2, fill=LINE)
steps = [('시작', None), ('상자 배치', 'u'), ('뚜껑 닫기', 'u'), ('나사 A', 'a'), ('나사 B', 'a'), ('나사 C', 'a'), ('나사 D', 'a'), ('최종 확인', 'u')]
for k, (nm, kind) in enumerate(steps):
    cx = 110 + k * (1060 / 7)
    if kind == 'a': dotc(s, cx - 15, 455, 30, n=k)
    elif kind == 'u': dotc(s, cx - 15, 455, 30, fill=WHITE, line=NAVY, n=k, color=NAVY)
    else: dotc(s, cx - 8, 462, 16, fill=LBLUE)
    tb(s, cx - 70, 492, 140, 22, nm, size=12.5, color=NAVY if kind else GREY, w8='x' if kind else 'r', align='c', anchor='m')
rect(s, 71, 544, 1138, 62, fill=PALE)
dotc(s, 95, 568, 14)
tb(s, 117, 544, 440, 62, '나사 A ~ D — 도구 관측에 따라 자동으로 넘어갑니다', size=12.5, color=NAVY, w8='s', anchor='m')
dotc(s, 640, 568, 14, fill=WHITE, line=NAVY)
tb(s, 662, 544, 520, 62, '상자 · 뚜껑 · 최종 확인 — 작업자가 확인하고 넘어갑니다', size=12.5, color=NAVY, w8='s', anchor='m')
src(s, '검은 칸은 윤곽 미리보기 도식이며, 카메라나 안경 화면 캡처가 아닙니다', y=624)

# ================================================================== 9 간지 03
s = d.divider(IMG['div3'], '03', '핵심 시연', '상자 하나를 처음부터 끝까지 조립합니다')
credit(s, 'Photo: @steve_j / Unsplash', x=12, color='C9D6E6')

# ================================================================== 10~12 핵심 시연
def demo(title, lead_, big_img, big_desc, imgnote, side_img, side_cap, capw):
    s = d.new(); header(s, 'Demo', title); lead(s, lead_, y=96, h=30)
    slot(s, 71, 140, 800, 450, 'Unity 안내 화면 (한쪽 눈)', big_desc, img=big_img, imgnote=imgnote, pad=44 if big_img else 0)
    pic(s, side_img, 889, 140, 320, 180)
    chip(s, 897, 290, side_cap, fill=BLACK, color=WHITE, size=9, w=capw, h=22)
    rect(s, 889, 336, 320, 254, fill=PALE)
    return s

s = demo('상자를 놓고, 뚜껑을 덮습니다', '놓을 자리와 덮을 자리를 윤곽으로 보여줍니다.', None,
         '몸체 윤곽 → 뚜껑 윤곽 · 한 번의 실행을 끊지 않고 녹화', '임시 이미지 · 윤곽 도식', IMG['fr_box'], '작업 장면 · 5월 개발 영상', 150)
pic(s, IMG['geo0'], 131, 232, 300, 215); pic(s, IMG['geo1'], 511, 232, 300, 215)
tb(s, 131, 450, 300, 20, '몸체 윤곽', size=11, color='8894A0', align='c', anchor='m'); tb(s, 511, 450, 300, 20, '뚜껑 윤곽', size=11, color='8894A0', align='c', anchor='m')
for k, (nm, ph) in enumerate([('상자 배치', '"상자를 놓아주세요"'), ('뚜껑 닫기', '"뚜껑을 덮어주세요"')]):
    y = 362 + k * 82
    numcircle(s, 909, y, k + 1, d=28)
    tb(s, 949, y - 3, 250, 28, nm, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, 949, y + 26, 250, 24, ph, size=13, color=BODY, anchor='m')
tb(s, 909, 550, 290, 20, '한글 안내 문구는 개선안 · 반영 후 녹화', size=10, color=ORANGE, w8='s', anchor='m')

s = demo('지금 작업할 나사만 밝게 표시합니다', '드라이버의 위치와 움직임에 따라 안내가 바뀌고, 다음 나사로 넘어갑니다.', IMG['hud'],
         '접근 전 → 파란 안내 → 초록 안내 → B 전환 · 중간을 자르지 않기', '임시 이미지 · 안내 디자인 예시 (나사 B)', IMG['yolo_s'], '작업 장면 · 5월 개발 영상 (검출 표시)', 212)
cyc = [('접근', '드라이버를 나사에 가져갑니다', LBLUE), ('작업 안내', '파란 강조', BLUE), ('이탈 안내', '초록 강조 · 드라이버를 뗍니다', GREEN), ('다음 나사', 'B로 이동', NAVY)]
for k, (nm, d_, c) in enumerate(cyc):
    y = 354 + k * 57
    dotc(s, 909, y + 5, 16, fill=c)
    tb(s, 939, y, 260, 26, nm, size=14.5, color=NAVY, w8='x', anchor='m')
    tb(s, 939, y + 25, 260, 22, d_, size=11.5, color=BODY, anchor='m')
    if k < 3: rect(s, 916, y + 24, 2, 35, fill=LINE)
src(s, '초록 안내는 도구의 접근 · 유지 · 이탈에 따른 안내이며, 조임 품질을 측정한 결과가 아닙니다', y=624)

s = demo('나사 B, C, D를 지나 최종 확인으로 마칩니다', '목표가 바뀌는 순간을 중심으로 보여줍니다.', None,
         '목표 전환 순간 위주 · 최종 확인과 완료 문구까지', '임시 이미지 · 윤곽 도식', IMG['fr_end'], '작업 장면 · 5월 개발 영상', 150)
pic(s, IMG['geo3'], 321, 222, 300, 215)
tb(s, 321, 440, 300, 20, '최종 확인 · 전체 윤곽', size=11, color='8894A0', align='c', anchor='m')
mx, my = 913, 358
rect(s, mx + 14, my + 14, 96, 76, line=LBLUE, lw=1.25)
for (lx, ly, nm, on) in [(0, 0, 'A', True), (96, 0, 'B', False), (0, 76, 'C', False), (96, 76, 'D', False)]:
    dotc(s, mx + lx, my + ly, 28, fill=NAVY if on else WHITE, line=None if on else NAVY, n=nm, color=WHITE if on else NAVY)
tb(s, mx - 10, my + 108, 144, 18, '작업자 쪽', size=10, color=GREY, align='c', anchor='m')
tb(s, 1062, 362, 140, 26, 'A → B → C → D', size=13.5, color=NAVY, w8='x', anchor='m', wrap=False)
tb(s, 1062, 392, 140, 44, ['한 번에 하나만', '강조합니다.'], size=11.5, color=BODY, ls=1.4)
hline(s, 909, 498, 280)
tb(s, 909, 510, 280, 28, '최종 확인', size=15, color=NAVY, w8='x', anchor='m')
tb(s, 909, 540, 280, 24, '작업자가 직접 확인합니다.', size=12, color=BODY, anchor='m')

# ================================================================== 13 공간 안내
s = d.new()
header(s, 'Tracking', '고개를 조금 움직여도 목표 위치를 따라갑니다')
lead(s, '같은 착용 상태에서 거리와 시선을 바꿔 가며 확인합니다.', y=96, h=30)
for k, (nm, d_) in enumerate([('가까운 거리', '작업대에 가까이'), ('원래 거리', '작업 자세 그대로'), ('작은 좌우 이동', '고개를 좌우로 조금')]):
    slot(s, 71 + k * 385, 140, 368, 300, nm, d_, img=IMG[('near', 'far', 'topv')[k]], tagtext='임시 사진 · 녹화로 교체')
rect(s, 71, 464, 1138, 110, fill=PALE)
tb(s, 99, 464, 160, 110, '볼 것', size=18, color=NAVY, w8='x', anchor='m')
tb(s, 250, 478, 930, 40, '현재 나사 강조가 실제 나사 위치에 머무는지', size=15.5, color=BODY, w8='s', anchor='m')
tb(s, 250, 520, 930, 40, '윤곽이 상자와 뚜껑의 가장자리를 따라가는지', size=15.5, color=BODY, w8='s', anchor='m')
src(s, '사진은 임시 (이전에 찍은 작업대 사진) · 세 칸 모두 실제 녹화로 교체', y=624)

# ================================================================== 14 간지 04
s = d.divider(IMG['div4'], '04', 'AI와 구현', '영상에서 도구와 위치를 찾아 단계를 판단합니다')
credit(s, 'Photo: QIU DEXING / Unsplash', x=12, color='C9D6E6')

# ================================================================== 15 AI 검출 영상
s = d.new()
header(s, 'Detection', 'AI는 영상에서 도구와 작업 위치를 찾습니다')
lead(s, '마커, 도구, 손을 각각 검출해 비교한 개발 영상입니다.', y=96, h=30)
s.shapes.add_movie(A + '03_AI_검출/AI_검출비교_원본_20260520.mp4', px(71), px(140), px(760), px(415), poster_frame_image=IMG['poster'], mime_type='video/mp4')
tb(s, 71, 562, 760, 18, '위 줄: 원본 영상 + 검출 · 아래 줄: 위에서 본 시점으로 편 영상 + 검출', size=9.5, color=LGREY, anchor='m')
for k, (lg, nm, d_) in enumerate([('opencv', 'ArUco', '마커로 작업대의 좌표를 잡습니다.'), ('yolo', 'YOLO', '영상에서 드라이버를 찾습니다.'), ('mediapipe', 'MediaPipe', '손 관절을 찾습니다. 별도의 오프라인 분석에 씁니다.')]):
    y = 140 + k * 144.5
    rect(s, 855, y, 354, 126, fill=PALE)
    pic(s, LOGO(lg), 875, y + 20, 34, 34)
    tb(s, 921, y + 18, 270, 38, nm, size=18, color=NAVY, w8='x', anchor='m')
    tb(s, 875, y + 66, 318, 48, d_, size=12.5, color=BODY, ls=1.4)
src(s, '2026년 5월 검출 비교 영상 (약 15초 · 소리 없음) · 최신 Unity 시연과 다른 영상', y=624)

# ================================================================== 16 검출 결과
s = d.new()
header(s, 'Detection', '도구의 위치와 나사의 위치를 비교합니다')
lead(s, '마커로 계산한 나사 위치에 드라이버가 다가오고, 머물고, 떠나는지를 봅니다.', y=96, h=30)
for k, (key, nm, role, d_, live) in enumerate([('aruco', 'ArUco · 마커', '작업대 좌표', '마커 좌표에서 나사 A ~ D의 위치를 계산합니다.', True),
                                               ('yolo', 'YOLO · 도구', '드라이버 위치', '드라이버를 찾아 목표 나사와의 관계를 봅니다.', True),
                                               ('mediapipe', 'MediaPipe · 손', '손 관절', '별도의 오프라인 분석 경로에서 사용합니다.', False)]):
    x = 71 + k * 385
    pic(s, IMG[key], x, 140, 368, 245)
    rect(s, x, 385, 368, 4, fill=NAVY if live else LBLUE)
    tb(s, x, 400, 368, 30, nm, size=17, color=NAVY, w8='x', anchor='m')
    chip(s, x, 438, '실시간 안내' if live else '오프라인 분석', fill=NAVY if live else PALE, color=WHITE if live else GREY, size=10.5, w=100 if live else 112, h=24, w8='b')
    tb(s, x + (112 if live else 124), 438, 240, 24, role, size=12, color=GREY, anchor='m')
    tb(s, x, 474, 360, 50, d_, size=13, color=BODY, ls=1.45)
src(s, '2026년 5월 개발 영상의 검출 결과', y=624)

# ================================================================== 17 처리 흐름
s = d.new()
header(s, 'Pipeline', '위치는 마커로, 단계는 도구의 움직임으로 판단합니다')
lead(s, '판단한 좌표와 단계를 안경과 관제 화면에 함께 전달합니다.', y=96, h=30)
def lane(y, label, boxes, logos=(), thumb=None):
    tb(s, 71, y - 24, 200, 20, label, size=12, color=NAVY, w8='x', anchor='m')
    pic(s, thumb, 71, y, 96, 56)
    x = 181
    for k, (t_, w, hi) in enumerate(boxes):
        r = rect(s, x, y, w, 56, fill=NAVY if hi else PALE, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .16
        tb(s, x, y, w, 56, t_, size=13, color=WHITE if hi else NAVY, w8='x' if hi else 's', align='c', anchor='m')
        x += w
        if k < len(boxes) - 1: arw(s, x + 2, y + 14); x += 30
    lx = 1209 - len(logos) * 40
    for k, lg in enumerate(logos): pic(s, LOGO(lg), lx + k * 40 + 8, y + 14, 28, 28)
    return x
lane(168, '위치', [('카메라', 96, False), ('ArUco 검출 · PnP', 180, False), ('나사 A ~ D 위치 계산', 200, True)], logos=('python', 'opencv'), thumb=IMG['t_aruco'])
lane(262, '단계', [('카메라', 96, False), ('YOLO 도구 검출', 150, False), ('도구와 목표의 관계', 168, False), ('시간 증거 · FSM', 150, False), ('현재 단계 · 다음 행동', 190, True)], logos=('yolo',), thumb=IMG['t_yolo'])
tb(s, 457, 320, 168, 18, '접근 · 유지 · 이탈', size=10, color=GREY, align='c', anchor='m')
hline(s, 71, 346, 1138)
xe = lane(380, '전달', [('좌표와 단계', 140, False), ('로컬 HTTP', 120, False), ('Unity 양안 안내', 170, True)], logos=('unity', 'csharp'), thumb=IMG['t_ar'])
tb(s, xe, 380, 30, 56, '+', size=18, color=LBLUE, w8='s', align='c', anchor='m')
r = rect(s, xe + 30, 380, 160, 56, fill=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .16
tb(s, xe + 30, 380, 160, 56, '브라우저 관제', size=13, color=WHITE, w8='x', align='c', anchor='m')
rect(s, 71, 468, 1138, 126, fill=PALE)
for k, (a_, b_) in enumerate([('시간 증거', '한 장면이 아니라 이어진 관측으로 단계를 넘깁니다. 관측이 잠깐 끊겼을 때 진행을 보존하고 다시 확인하도록 보강했습니다.'),
                              ('안내의 의미', '안내 색은 도구의 접근 · 유지 · 이탈을 나타냅니다. 체결 토크나 조임 품질을 측정한 결과가 아닙니다.')]):
    y = 480 + k * 52
    tb(s, 99, y, 130, 48, a_, size=13.5, color=NAVY, w8='x', anchor='m')
    tb(s, 236, y, 950, 48, b_, size=12.5, color=BODY, anchor='m', ls=1.35)
src(s, 'MediaPipe · HMM/Viterbi는 별도의 오프라인 분석 경로입니다', y=624)

# ================================================================== 18 간지 05
s = d.divider(IMG['div5'], '05', '관제와 개선', '전체 흐름을 확인하고, 화면은 더 단순하게')
credit(s, 'Photo: @myblu / Unsplash', x=12, color='C9D6E6')

# ================================================================== 19 관제
s = d.new()
header(s, 'Console', '관제 화면에서는 전체 진행을 확인합니다')
lead(s, '작업자는 눈앞의 안내를, 확인하는 사람은 전체 흐름을 봅니다.', y=96, h=30)
pic(s, IMG['ctl'], 71, 140, 780, 418)
tag(s, 83, 152, '실시간 관제 녹화로 교체')
for k, (a_, b_) in enumerate([('현재 작업', '나사 B'), ('다음 행동', '드라이버를 나사 B에 대어 주세요'), ('진행', '대상 접근 → 접근 유지 → 이탈 대기'), ('위치', 'A ~ D 중 어느 나사인지 그림으로')]):
    y = 140 + k * 108.7
    rect(s, 875, y, 334, 92, fill=PALE); rect(s, 875, y, 4, 92, fill=NAVY)
    tb(s, 897, y + 12, 300, 22, a_, size=11.5, color=GREY, w8='x', anchor='m')
    tb(s, 897, y + 36, 300, 44, b_, size=14.5, color=NAVY, w8='x', anchor='m', ls=1.3)
src(s, '저장한 상태를 다시 재생한 발표용 화면 · 작업대 영상은 별도 카메라 사진', y=624)

# ================================================================== 20 피드백과 개선
s = d.new()
header(s, 'Feedback', '상태 설명을 줄이고, 지금 할 행동 한 줄로')
lead(s, '사용자가 원한 것은 내부 상태가 아니라 지금 무엇을 해야 하는지였습니다.', y=96, h=30)
pic(s, IMG['old'], 71, 140, 500, 333); pic(s, IMG['ar_s'], 709, 140, 500, 333)
chip(s, 83, 152, '이전', fill=WHITE, color=GREY, size=11, w=56, h=26, w8='x')
chip(s, 721, 152, '개선안', fill=NAVY, color=WHITE, size=11, w=70, h=26, w8='x')
tb(s, 571, 140, 138, 333, '→', size=34, color=NAVY, w8='s', align='c', anchor='m', wrap=False)
tb(s, 71, 482, 500, 24, '영문 상태 문구가 여러 줄 · SCREW A | 1/4, MOVE CLEAR …', size=12.5, color=GREY, anchor='m')
tb(s, 709, 482, 500, 24, '작은 단계 표시 + 큰 행동 한 줄 + 목표 강조', size=13, color=NAVY, w8='x', anchor='m')
xs_ = 71
for t_, w in [('상자를 놓아주세요', 170), ('뚜껑을 덮어주세요', 170), ('나사 A를 조여주세요', 184), ('드라이버를 떼어주세요', 198), ('조립 상태를 확인해주세요', 216)]:
    chip(s, xs_, 540, t_, fill=PALE, color=NAVY, size=13, w=w, h=40, w8='x'); xs_ += w + 12
tag(s, xs_ + 4, 548, '반영 후 녹화')
src(s, '왼쪽: 기존 팜플렛의 안내 예시 · 오른쪽: 안내 디자인 예시 (설명용 합성) · 아래 문구는 개선안', y=624)

# ================================================================== 21 마무리
s = d.new()
pic(s, IMG['close'], 0, 0, 1280, 720)
tb(s, 85, 176, 900, 170, ['눈앞에는 다음 작업을,', '관제에는 전체 흐름을.'], size=40, color=WHITE, w8='x', ls=1.22)
rect(s, 87, 366, 40, 2, fill=LBLUE)
tb(s, 85, 386, 900, 32, 'AI Assembly Guide는 조립 순서를 따라 작업을 이어가도록 돕습니다.', size=17, color='D9E2F0', anchor='m')
tb(s, 85, 572, 600, 28, 'AI Assembly Guide', size=19, color=WHITE, w8='x', anchor='m')
tb(s, 85, 602, 900, 22, '작업 단계 인식 기반 AR 조립 안내', size=13, color='D9E2F0', anchor='m')
tb(s, 85, 634, 900, 22, '개발 최민준 (C011207)   |   지도교수 윤영 교수님', size=12.5, color='D9E2F0', w8='m', anchor='m')
credit(s, '배경: AR 안내 예시 (설명용 합성)', x=12, color='8FA3BC')

# ================================================================== 22 제작 메모 (영상 제외)
s = d.new()
header(s, 'Memo', '제작 메모 — 영상에는 넣지 않는 장')
rows = [('4', 'AR 안내 예시 (사진 + 안내 디자인 합성)', '새 Unity 녹화: 몸체 → 뚜껑 → 나사 강조를 짧게 연결'),
        ('7', '관제 준비 화면 캡처 (실행 전)', '최신 UI로 다시 캡처하거나 녹화'),
        ('10 · 11 · 12', '윤곽 도식, 안내 디자인 예시, 5월 개발 영상 장면', '같은 실행의 Unity 출력 + 관제 녹화 (약 3~4분). 나사 A 한 사이클은 자르지 않기'),
        ('10 · 20', '한글 안내 문구 ("상자를 놓아주세요" 등)', '개선안. 앱에 반영하고 확인한 문구만 남기기'),
        ('8 · 10', '상자 · 뚜껑은 작업자가 확인하고 넘어간다고 표기', '자동 확인이 구현 · 검증되면 범례와 대본 수정'),
        ('13', '이전에 찍은 작업대 사진 3장 (임시)', '가까운 거리 / 원래 거리 / 작은 좌우 이동 녹화 (30~50초). 제목은 녹화 결과에 맞추기'),
        ('15', '5월 검출 비교 영상이 들어 있음 (무음)', '한 번만 재생. 최신 시연과 다른 영상이라는 표기 유지'),
        ('19', '저장 상태 재생 화면', '실시간 관제 녹화: 시작 · 현재 단계 · 종료 · 작업 기록'),
        ('20', '기존 팜플렛 화면 vs 안내 디자인 예시', '간소화한 실제 화면 캡처로 교체')]
rect(s, 71, 100, 1138, 30, fill=NAVY)
for x, w, t_ in [(87, 110, '장'), (200, 400, '지금 들어간 것'), (630, 560, '바꾸거나 확인할 것')]:
    tb(s, x, 100, w, 30, t_, size=11.5, color=WHITE, w8='x', anchor='m')
for k, (n, a_, b_) in enumerate(rows):
    y = 130 + k * 42
    tb(s, 87, y, 110, 42, n, size=12.5, color=ORANGE, w8='x', anchor='m')
    tb(s, 200, y, 410, 42, a_, size=12, color=TXT, anchor='m')
    tb(s, 630, y, 570, 42, b_, size=12, color=BODY, anchor='m')
    hline(s, 71, y + 42, 1138)
tb(s, 71, 522, 1138, 24, '자료에 없어서 만들어 넣은 것', size=13, color=NAVY, w8='x', anchor='m')
tb(s, 71, 548, 1138, 120, ['· 각 장의 제목과 설명 문장, 5장 사진 아래 설명과 비교 문장, 11장의 사이클 표, 13장의 "볼 것" 두 줄, 표지 제목의 둘째 줄',
                           '· 발표자 노트의 대본 초안과 구간 시간 (구성안의 예시 문장과 시간표를 바탕으로 작성 · 실제 녹화 길이에 맞춰 확정)',
                           '· 2 · 3 · 5 · 6 · 9 · 14 · 18장의 사진은 Unsplash 무료 사진 (각 장 아래에 표기)이며 프로젝트에서 찍은 사진이 아님. 표지 · 7장의 안경은 VITURE 제품 이미지',
                           '· 주황 표시(녹화 영상 자리, 교체 표시)는 영상을 넣으면서 지우기. 정확도 같은 수치는 넣지 않았음',
                           '· 구성안은 어두운 바탕을 권했지만, 늘 쓰던 흰 바탕 · 네이비 양식으로 만들었음 (Unity 화면이 들어갈 자리만 검은 칸)'], size=11, color=BODY, ls=1.5)

# ------------------------------------------------------------------ 노트 (v1에서 가져옴) · 저장
lst = d.prs.slides._sldIdLst; first = lst[0]
d.prs.part.drop_rel(first.rId); lst.remove(first)
try:
    v1 = Presentation(W_ + '/out/AI Assembly Guide_영상용_v1.pptx')
    old = [sl.notes_slide.notes_text_frame.text if sl.has_notes_slide else '' for sl in v1.slides]
    for i, sl in enumerate(d.prs.slides, 1):
        t_ = old[0] if i == 1 else ('[목차] 영상에서는 2~3초만 보여주거나 건너뛴다. 사진은 무료 사진(프로젝트 촬영분 아님).' if i == 2 else old[i - 2])
        sl.notes_slide.notes_text_frame.text = t_
except Exception as e:
    print('notes skipped', e)
d.save()
