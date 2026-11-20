# -*- coding: utf-8 -*-
"""AI Assembly Guide — 졸업프로젝트 10분 영상용 PPT (16:9, 어두운 바탕 · 청록 강조).
자료: /mnt/user-data/uploads/AI_Assembly_Video_Pack_20261115 (Codex 정리본). 사용: python3 build.py [OUT.pptx]
"""
import sys, os, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
import numpy as np
from PIL import Image
from pptx import Presentation
from pptx.util import Pt
from pptx.oxml.ns import qn
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from lib import px, rgb, tb, rect, pic

W_ = '/home/claude/grad'
A = '/mnt/user-data/uploads/AI_Assembly_Video_Pack_20261115/'
PR = W_ + '/prep/'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_영상용_v1.pptx'
os.makedirs(PR, exist_ok=True); os.makedirs(W_ + '/out', exist_ok=True)

BG = '0D1112'; PANEL = '161C1E'; PANEL2 = '1E2729'; LN = '2C383B'; BLACK = '070909'
WHITE = 'F4F7F7'; SUB = 'B7C2C5'; DIM = '7C898D'
ACC = '5FD0B5'; ACCD = '12332D'; AMBER = 'E3A84B'; BLUE = '4DA3FF'; GREEN = '62E38C'

# ------------------------------------------------------------------ 이미지 준비
def cover(src, w, h, fx=.5, fy=.5, scale=2):
    im = Image.open(src).convert('RGB'); Wd, Hd = int(w * scale), int(h * scale)
    r = max(Wd / im.width, Hd / im.height); im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x = int((im.width - Wd) * fx); y = int((im.height - Hd) * fy)
    return im.crop((x, y, x + Wd, y + Hd))

def shade(im, left=0, bottom=0, flat=0, top=0):
    a = np.asarray(im).astype(np.float32); h, w = a.shape[:2]
    xs = np.linspace(0, 1, w)[None, :, None]; ys = np.linspace(0, 1, h)[:, None, None]
    k = flat + left * np.clip(1 - xs / .72, 0, 1) ** 1.3 + bottom * np.clip((ys - .35) / .65, 0, 1) ** 1.3 + top * np.clip(1 - ys / .4, 0, 1) ** 1.5
    k = np.clip(k, 0, .96); c = np.array([13, 17, 18], np.float32)[None, None, :]
    return Image.fromarray((a * (1 - k) + c * k).astype(np.uint8))

def save(im, name, q=90):
    p = PR + name + '.jpg'; im.save(p, quality=q); return p

IMG = {}
IMG['cover'] = save(shade(cover(A + '02_작업대_사진/작업대_편집용_크롭.png', 1280, 720, fy=.55), left=.95, flat=.28), 'cover')
IMG['intro'] = save(shade(cover(A + '02_작업대_사진/작업대_위에서_원본.png', 1280, 720, fy=.5), bottom=.9, flat=.18, top=.35), 'intro')
P = W_ + '/photo/'; FR = W_ + '/frames/'
IMG['intro2'] = save(shade(cover(P + 'maciejka_dslr-manual_blocks.jpg', 1280, 720), bottom=.93, flat=.2, top=.3), 'intro2')
IMG['aud1'] = save(cover(P + 'helloimnik-assemble_b.jpg', 368, 250), 'aud1')
IMG['aud2'] = save(cover(P + 'helloimnik-assemble_a.jpg', 368, 250), 'aud2')
_c = Image.open(P + 'helloimnik-assemble_c.jpg').convert('RGB'); _c.crop((0, int(_c.height * .3), int(_c.width * .9), _c.height)).save(PR + '_c.png')
IMG['aud3'] = save(cover(PR + '_c.png', 368, 250, fy=1.0), 'aud3')
IMG['ch2'] = save(shade(cover(P + 'redd_francisco-glasses_hold.jpg', 1280, 720), left=.85, flat=.3), 'ch2')
IMG['ch3'] = save(shade(cover(P + 'steve_j-screwdriver.jpg', 1280, 720), left=.8, flat=.3), 'ch3')
IMG['ch4'] = save(shade(cover(P + 'qiu_dexing-3dmodel.jpg', 1280, 720, fy=.62), left=.85, flat=.3), 'ch4')
IMG['ch5'] = save(shade(cover(P + 'myblu-worktable.jpg', 1280, 720), left=.85, flat=.3), 'ch5')
IMG['top'] = save(cover(A + '02_작업대_사진/작업대_위에서_원본.png', 480, 320), 'top')
def frame(n, name, w=368, h=207, fy=.5):
    Image.open(FR + 'f_%02d.png' % n).convert('RGB').crop((0, 24, 440, 360)).save(PR + '_t.png')
    IMG[name] = save(cover(PR + '_t.png', w, h, fy=fy), name)
frame(2, 'fr_box'); frame(12, 'fr_end')
IMG['yolo_s'] = save(cover(A + '03_AI_검출/검출_yolo.png', 368, 207, fy=.3), 'yolo_s')
IMG['near'] = save(shade(cover(A + '02_작업대_사진/작업대_편집용_크롭.png', 368, 300), bottom=.9, top=.5), 'near')
IMG['far'] = save(shade(cover(A + '02_작업대_사진/작업대_카메라_원본.png', 368, 300, fx=.45), bottom=.9, top=.5), 'far')
IMG['topv'] = save(shade(cover(A + '02_작업대_사진/작업대_위에서_원본.png', 368, 300, fx=.35), bottom=.9, top=.5), 'topv')
IMG['t_aruco'] = save(cover(A + '03_AI_검출/검출_aruco.png', 96, 56, fy=.6, scale=3), 't_aruco')
IMG['t_yolo'] = save(cover(A + '03_AI_검출/검출_yolo.png', 96, 56, fy=.3, scale=3), 't_yolo')
IMG['t_ar'] = save(cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 96, 56, fy=.3, scale=3), 't_ar')
IMG['ar'] = save(cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 800, 533), 'ar')
IMG['ar_s'] = save(cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 520, 347), 'ar_s')
IMG['old'] = save(cover(W_ + '/scratch/pimg-002.png', 520, 347), 'old')
IMG['bench'] = save(cover(A + '02_작업대_사진/작업대_카메라_원본.png', 480, 330, fx=.45), 'bench')
IMG['close'] = save(shade(cover(A + '01_Unity_안내/AR_B_안내_디자인예시.png', 1280, 720, fy=.3), left=.9, flat=.45, top=.9, bottom=1.0), 'close')
IMG['ready'] = save(cover(A + '04_관제/노트북_실행준비_화면.png', 676, 422, fy=0), 'ready', 92)
IMG['ctl'] = save(cover(A + '04_관제/관제_B_저장상태_발표용.png', 836, 448, fy=0), 'ctl', 92)
IMG['ctl_s'] = save(cover(A + '04_관제/관제_B_저장상태_발표용.png', 368, 207, fy=0), 'ctl_s', 92)
for k in ('aruco', 'yolo', 'mediapipe'):
    IMG[k] = save(cover(A + '03_AI_검출/검출_%s.png' % k, 368, 245), k)
IMG['poster'] = save(Image.open(A + '03_AI_검출/원본영상_프레임_048.png').convert('RGB'), 'poster')
g = Image.open(A + '01_Unity_안내/몸체_뚜껑_단계별_기하미리보기.png').convert('RGB')
for i in range(4):
    t = g.crop((i * 480, 66, i * 480 + 480, 410)); IMG['geo%d' % i] = save(t, 'geo%d' % i, 92)
# HUD 디자인 레이어를 검은 바탕에 올린다(디자인 예시)
h_ = Image.open(A + '01_Unity_안내/AR_B_투명_HUD_디자인.png').convert('RGBA')
b_ = Image.new('RGBA', h_.size, (7, 9, 9, 255)); b_.alpha_composite(h_); IMG['hud'] = save(b_.convert('RGB'), 'hud', 92)
be = Image.open(A + '05_기기_로고/VITURE_Beast_사선_제품사진.jpg').convert('RGB'); be.thumbnail((1100, 800)); IMG['beast'] = save(be, 'beast', 92)
LOGO = lambda n: A + '05_기기_로고/logo_%s.png' % n

# ------------------------------------------------------------------ 도우미
prs = Presentation(SK + '/assets/template_cover.pptx')
BLANK = [l for l in prs.slide_layouts if l.name == 'Blank'][0]
COVER_TPL = prs.slides[0]

def new(bg=BG):
    s = prs.slides.add_slide(BLANK)
    for ph in list(s.placeholders): ph._element.getparent().remove(ph._element)
    s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb(bg)
    return s

def note(s, t):
    s.notes_slide.notes_text_frame.text = t

def head(s, kicker, title, sub=None):
    tb(s, 64, 44, 900, 20, kicker, size=12, color=ACC, w8='s', anchor='m')
    tb(s, 64, 68, 1152, 48, title, size=29, color=WHITE, w8='x', anchor='m')
    if sub: tb(s, 64, 120, 1152, 26, sub, size=15.5, color=SUB, anchor='m')

def foot(s, caption=None):
    tb(s, 64, 684, 300, 16, 'AI Assembly Guide', size=9.5, color=DIM, w8='s', anchor='m')
    if caption: tb(s, 380, 684, 836, 16, caption, size=9.5, color=DIM, align='r', anchor='m')

def credit(s, text):
    tb(s, 780, 690, 436, 16, text, size=9, color=DIM, align='r', anchor='m')

def chapter(num, title, sub, img, cred, memo):
    s = new(); pic(s, img, 0, 0, 1280, 720)
    tb(s, 84, 236, 400, 84, num, size=60, color=ACC, w8='x', anchor='m')
    tb(s, 84, 330, 900, 64, title, size=40, color=WHITE, w8='x', anchor='m')
    rect(s, 86, 410, 56, 3, fill=ACC)
    tb(s, 84, 428, 900, 32, sub, size=18, color=SUB, anchor='m')
    credit(s, cred); note(s, memo); return s

def chip(s, x, y, w, h, text, fill=None, color=SUB, line=LN, size=13, w8='s', name=None):
    r = rect(s, x, y, w, h, fill=fill, line=line, lw=1, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=name)
    r.adjustments[0] = .5
    tb(s, x, y, w, h, text, size=size, color=color, w8=w8, align='c', anchor='m', wrap=False, name=name)

def tag(s, x, y, text, w=None):
    w = w or (len(text) * 11.5 + 22)
    chip(s, x, y, w, 24, text, fill=AMBER, color='1A1407', line=None, size=10.5, w8='b', name='SLOT_TAG')

def arrow(s, x, y, color=DIM, size=16):
    tb(s, x, y, 28, 28, '→', size=size, color=color, w8='s', align='c', anchor='m', wrap=False)

def dot(s, x, y, n, d=28, fill=ACC, color='0B1513', size=12, line=None):
    rect(s, x, y, d, d, fill=fill, line=line, lw=1.25, shape=MSO_SHAPE.OVAL)
    if n != '': tb(s, x, y, d, d, str(n), size=size, color=color, w8='x', align='c', anchor='m', wrap=False)

def slot(s, x, y, w, h, title, desc=None, img=None, tagtext='녹화 영상 자리', imgnote=None, pad=0):
    r = rect(s, x, y, w, h, fill=BLACK, line=ACC, lw=1.25, name='SLOT')
    r.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    if img:
        im = Image.open(img); ar = im.width / im.height; iw, ih = w - 2 * pad, h - 2 * pad
        if ar > iw / ih: pw, ph = iw, iw / ar
        else: pw, ph = ih * ar, ih
        pic(s, img, x + (w - pw) / 2, y + (h - ph) / 2, pw, ph)
    tag(s, x + 12, y + 12, tagtext)
    tb(s, x + 16, y + h - (54 if desc else 34), w - 32, 22, title, size=13, color=WHITE, w8='b', anchor='m')
    if desc: tb(s, x + 16, y + h - 32, w - 32, 20, desc, size=11, color=SUB, anchor='m')
    if imgnote: tb(s, x + w - 316, y + 14, 300, 20, imgnote, size=10, color=DIM, align='r', anchor='m')

def panel(s, x, y, w, h, fill=PANEL, line=None):
    return rect(s, x, y, w, h, fill=fill, line=line, lw=1)

# ================================================================== 1 표지
s = new()
pic(s, IMG['cover'], 0, 0, 1280, 720)
tb(s, 84, 196, 700, 22, '졸업프로젝트', size=13, color=ACC, w8='s', anchor='m')
tb(s, 84, 228, 900, 84, 'AI Assembly Guide', size=56, color=WHITE, w8='x', anchor='m')
rect(s, 86, 326, 56, 3, fill=ACC)
tb(s, 84, 346, 900, 40, '작업 단계 인식 기반 AR 조립 안내', size=24, color=WHITE, w8='m', anchor='m')
tb(s, 84, 612, 900, 24, '최민준 (C011207)   |   지도교수 윤영 교수님', size=14, color=SUB, w8='m', anchor='m')
note(s, '[표지 · 영상 시작 전 또는 0:00] 내레이션 없음. 2~3초 정지 후 다음 장으로.')

# ================================================================== 2 도입
s = new()
pic(s, IMG['intro2'], 0, 0, 1280, 720)
tb(s, 84, 60, 600, 20, '01  도입', size=12, color=ACC, w8='s', anchor='m')
tb(s, 84, 408, 1100, 160, ['어디부터, 어떤 순서로', '작업해야 할까요?'], size=40, color=WHITE, w8='x', ls=1.2)
tb(s, 84, 590, 1100, 28, '조립이 익숙하지 않으면 설명서와 부품을 번갈아 확인하게 됩니다.', size=18, color=SUB, anchor='m')
credit(s, '사진: Unsplash @maciejka_dslr')
note(s, '[0:00~0:20 · 사진 도입]\n대본 초안: 조립이 익숙하지 않으면 설명서와 부품을 번갈아 확인하게 됩니다. 손을 멈추는 사이, 다음 작업이나 순서를 놓치기도 합니다.\n화면: 설명서와 부품 사진(무료 사진, 프로젝트 촬영분 아님). 실제 작업대 전경 영상으로 바꿔도 된다.')

# ================================================================== 3 완성된 안내 먼저
s = new()
tb(s, 64, 44, 340, 20, '01  AI Assembly Guide', size=12, color=ACC, w8='s', anchor='m')
tb(s, 64, 120, 340, 128, ['지금 할 작업이', '눈앞에 보입니다'], size=31, color=WHITE, w8='x', ls=1.22)
tb(s, 64, 262, 320, 56, '작업할 위치와 다음 행동을 AR 안경으로 보여줍니다.', size=15.5, color=SUB, ls=1.45)
pts = [('현재 나사만 강조', '작업할 나사 위치에 표시'), ('작은 단계 표시', '나사 B · 2/4'), ('행동 한 줄', '나사 B를 조여주세요')]
for k, (h_, d_) in enumerate(pts):
    y = 356 + k * 66
    dot(s, 64, y + 4, k + 1)
    tb(s, 106, y, 280, 24, h_, size=15.5, color=WHITE, w8='b', anchor='m')
    tb(s, 106, y + 25, 280, 22, d_, size=12.5, color=DIM, anchor='m')
pic(s, IMG['ar'], 416, 72, 800, 533)
tag(s, 428, 84, '새 Unity 녹화로 교체')
tb(s, 416, 612, 800, 18, 'AR 안내 예시 · 실제 작업대 사진에 Unity 안내 디자인을 합친 설명용 이미지', size=10.5, color=DIM, anchor='m')
foot(s)
note(s, '[0:20~0:50 · 완성된 안내 먼저 공개]\n대본 초안: AI Assembly Guide는 작업할 위치와 다음 행동을 AR 안경으로 보여줍니다. 작업자는 눈앞의 안내를 따라가고, 관제 화면에서는 전체 진행을 확인할 수 있습니다.\n교체: 새 Unity 녹화에서 몸체 → 뚜껑 → 나사 강조를 짧게 연결한 영상으로 바꾼다. 지금 이미지는 설명용 합성이므로 "AR 안내 예시" 표기를 유지한다.')

# ================================================================== 4 누구를 위해
s = new()
head(s, '01  누구를 위해', '조립이 익숙하지 않은 작업자를 위해 만들었습니다', '조립 초보자와 실습자는 설명서를 반복해서 확인하고, 순서를 헷갈리기 쉽습니다.')
caps = [('설명서를 봅니다', '그림과 부품을 번갈아 확인합니다.'), ('부품을 맞춥니다', '손이 멈추면 순서를 다시 찾습니다.'), ('다시 설명서로 돌아갑니다', '어디까지 했는지 헷갈리기 쉽습니다.')]
for k, (h_, d_) in enumerate(caps):
    x = 64 + k * 392
    pic(s, IMG['aud%d' % (k + 1)], x, 172, 368, 250)
    dot(s, x, 438, k + 1, d=26, size=11.5)
    tb(s, x + 36, 436, 330, 30, h_, size=17, color=WHITE, w8='b', anchor='m')
    tb(s, x + 36, 468, 330, 24, d_, size=13, color=SUB, anchor='m')
    if k < 2: tb(s, x + 368, 283, 24, 28, '→', size=15, color=ACC, w8='s', align='c', anchor='m', wrap=False)
panel(s, 64, 532, 568, 100); panel(s, 648, 532, 568, 100, fill=ACCD)
rect(s, 648, 532, 3, 100, fill=ACC)
tb(s, 92, 546, 520, 22, '설명서를 보며 작업하면', size=12.5, color=DIM, w8='b', anchor='m')
tb(s, 92, 572, 520, 44, '시선이 설명서와 작업대를 오갑니다.', size=19, color=WHITE, w8='b', anchor='m')
tb(s, 676, 546, 520, 22, 'AR 안내로 작업하면', size=12.5, color=ACC, w8='b', anchor='m')
tb(s, 676, 572, 520, 44, '작업 위치에서 다음 행동을 확인합니다.', size=19, color=WHITE, w8='b', anchor='m')
foot(s, '사진: Unsplash @helloimnik')
note(s, '[0:50~1:35 · 누구를 위해 만들었나]\n대본 초안: 이 프로젝트는 조립이 익숙하지 않은 작업자를 생각하며 만들었습니다. 설명서로 작업하면 시선이 설명서와 작업대를 오가고, 그 사이 순서를 헷갈리기 쉽습니다. 안내가 작업 위치에 보이면, 그 자리에서 다음 행동을 확인할 수 있습니다.\n주의: 사진은 설명용 무료 사진이며 프로젝트에서 찍은 장면이 아니다. 아래 비교 문장은 측정 결과가 아니다.')

chapter('02', '사용 준비와 전체 흐름', '안경을 연결하고 작업을 시작하기까지', IMG['ch2'], '사진: Unsplash · Redd Francisco', '[1:35 무렵 · 장 구분] 2~3초. 내레이션 없이 넘기거나 다음 장 첫 문장을 얹는다. 사진은 무료 사진(프로젝트 촬영분 아님).')

# ================================================================== 5 사용 준비
s = new()
rect(s, 0, 0, 480, 400, fill='FFFFFF')
pic(s, IMG['beast'], 50, 24, 380)
tb(s, 40, 296, 400, 28, 'VITURE Beast', size=19, color='111516', w8='x', anchor='m')
tb(s, 40, 326, 400, 22, '양안 AR 표시 · Windows PC 연결', size=13, color='5A666A', anchor='m')
tb(s, 40, 366, 400, 16, '제품 이미지 · VITURE', size=9.5, color='8B969A', anchor='m')
pic(s, IMG['top'], 0, 400, 480, 320)
chip(s, 16, 682, 214, 24, '실제 작업대와 안경 · 이전 배치 사진', fill='000000', color=WHITE, line=None, size=10, w8='s')
tb(s, 540, 44, 600, 20, '02  사용 준비', size=12, color=ACC, w8='s', anchor='m')
tb(s, 540, 68, 680, 48, '안경을 쓰고, 노트북에서 시작합니다', size=29, color=WHITE, w8='x', anchor='m')
pic(s, IMG['ready'], 540, 150, 676, 422)
rect(s, 540, 150, 676, 422, line=LN, lw=1)
tb(s, 540, 578, 676, 18, '관제 준비 화면 캡처 (실행 전)', size=10.5, color=DIM, anchor='m')
for k, t in enumerate(['안경을 연결하고 작업대를 봅니다', '연결을 확인합니다', '작업 시작을 누릅니다']):
    x = 540 + k * 228
    dot(s, x, 620, k + 1, d=26, size=11.5)
    tb(s, x + 36, 608, 186, 50, t, size=13, color=WHITE, w8='s', anchor='m', ls=1.3)
note(s, '[1:35~2:15 · 사용 준비]\n대본 초안: 준비는 간단합니다. 안경을 노트북에 연결하고 작업대를 바라봅니다. 관제 화면에서 연결을 확인한 뒤 작업 시작을 누르면 안내가 켜집니다.\n교체 권장: 준비 화면은 이후 UI 수정이 반영되지 않았을 수 있어 최종 영상에는 새 녹화를 쓴다.')

# ================================================================== 6 전체 흐름
s = new()
head(s, '02  전체 흐름', '일곱 단계를 순서대로 안내합니다', '상자 배치와 뚜껑 닫기 뒤에 나사 A부터 D까지 작업하고, 최종 확인으로 마칩니다.')
tiles = [('1', '상자 배치', '몸체 윤곽'), ('2', '뚜껑 닫기', '뚜껑 윤곽'), ('3–6', '나사 A ~ D', '뚜껑 윤곽 + 현재 나사 강조'), ('7', '최종 확인', '전체 윤곽')]
TW = (1152 - 3 * 21) / 4
for k, (n, nm, d_) in enumerate(tiles):
    x = 64 + k * (TW + 21)
    rect(s, x, 176, TW, 222, fill=BLACK, line=LN, lw=1)
    pic(s, IMG['geo%d' % k], x + 6, 196, TW - 12, (TW - 12) * 344 / 480)
    chip(s, x + 12, 186, 46 if len(n) > 1 else 30, 24, n, fill=ACC, color='0B1513', line=None, size=11.5, w8='x')
    tb(s, x, 406, TW, 26, nm, size=16, color=WHITE, w8='b', anchor='m')
    tb(s, x, 432, TW, 20, d_, size=12, color=DIM, anchor='m')
rect(s, 96, 520, 1088, 2, fill=LN)
steps = [('시작', None), ('상자 배치', 'u'), ('뚜껑 닫기', 'u'), ('나사 A', 'a'), ('나사 B', 'a'), ('나사 C', 'a'), ('나사 D', 'a'), ('최종 확인', 'u')]
for k, (nm, kind) in enumerate(steps):
    cx = 96 + k * (1088 / 7)
    if kind == 'a': dot(s, cx - 15, 506, k, d=30, size=12)
    elif kind == 'u': dot(s, cx - 15, 506, k, d=30, fill=BG, color=WHITE, size=12, line=SUB)
    else: dot(s, cx - 8, 513, '', d=16, fill=DIM)
    tb(s, cx - 70, 544, 140, 22, nm, size=13, color=WHITE if kind else DIM, w8='s', align='c', anchor='m')
dot(s, 64, 606, '', d=14)
tb(s, 86, 600, 420, 26, '나사 A ~ D — 도구 관측에 따라 자동으로 넘어갑니다', size=12.5, color=SUB, anchor='m')
dot(s, 560, 606, '', d=14, fill=BG, line=SUB)
tb(s, 582, 600, 520, 26, '상자 · 뚜껑 · 최종 확인 — 작업자가 확인하고 넘어갑니다', size=12.5, color=SUB, anchor='m')
foot(s, '윤곽 미리보기 도식 · 카메라나 안경 화면 캡처가 아님')
note(s, '[2:00~2:15 · 전체 흐름]\n대본 초안: 안내는 일곱 단계로 진행됩니다. 상자를 놓고, 뚜껑을 덮고, 나사 A부터 D까지 조인 뒤, 조립 상태를 확인하고 마칩니다.\n사실 확인: 현재 성공본에서 상자·뚜껑·최종 검사는 사용자 확인, A~D는 도구 관측에 따른 자동 진행. 상자·뚜껑 자동 확인이 구현·검증되면 아래 범례를 고친다.')

chapter('03', '핵심 시연', '상자 하나를 처음부터 끝까지 조립합니다', IMG['ch3'], '사진: Unsplash @steve_j', '[2:15 무렵 · 장 구분] 2~3초. 사진은 무료 사진(프로젝트 촬영분 아님).')

# ================================================================== 7~9 핵심 시연
def demo(kicker, title, sub, big_img, big_title, big_desc, imgnote, side_img, side_cap, capw):
    s = new(); head(s, kicker, title, sub)
    slot(s, 64, 166, 768, 432, big_title, big_desc, img=big_img, imgnote=imgnote, pad=40 if big_img else 0)
    pic(s, side_img, 848, 166, 368, 207)
    rect(s, 848, 166, 368, 207, line=LN, lw=1)
    chip(s, 858, 341, capw, 22, side_cap, fill='000000', color=WHITE, line=None, size=9.5, w8='s')
    panel(s, 848, 389, 368, 209)
    return s

s = demo('03  핵심 시연 · 상자와 뚜껑', '상자를 놓고, 뚜껑을 덮습니다', '놓을 자리와 덮을 자리를 윤곽으로 보여줍니다.',
         None, 'Unity 안내 화면 (한쪽 눈)', '몸체 윤곽 → 뚜껑 윤곽 · 한 번의 실행을 끊지 않고 녹화', None, IMG['fr_box'], '작업 장면 · 5월 개발 영상', 160)
pic(s, IMG['geo0'], 124, 250, 300, 215); pic(s, IMG['geo1'], 470, 250, 300, 215)
tb(s, 124, 470, 300, 20, '몸체 윤곽', size=11.5, color=DIM, align='c', anchor='m'); tb(s, 470, 470, 300, 20, '뚜껑 윤곽', size=11.5, color=DIM, align='c', anchor='m')
tb(s, 516, 180, 300, 20, '임시 이미지 · 윤곽 도식', size=10, color=DIM, align='r', anchor='m')
for k, (n, nm, ph) in enumerate([('1', '상자 배치', '상자를 놓아주세요'), ('2', '뚜껑 닫기', '뚜껑을 덮어주세요')]):
    y = 408 + k * 74
    dot(s, 868, y, n, d=28)
    tb(s, 908, y - 2, 290, 24, nm, size=15, color=WHITE, w8='b', anchor='m')
    tb(s, 908, y + 24, 290, 22, '"' + ph + '"', size=13, color=ACC, w8='s', anchor='m')
tb(s, 868, 562, 330, 20, '한글 안내 문구는 개선안 · 반영 후 녹화', size=10.5, color=DIM, anchor='m')
foot(s)
note(s, '[2:15~3:00 · 핵심 시연 ①]\n대본 초안: 먼저 상자를 놓을 자리가 윤곽으로 표시됩니다. 상자를 놓으면 뚜껑을 덮을 자리가 이어서 보입니다.\n교체: Unity 한쪽 눈 화면. 같은 실행의 관제 화면을 오른쪽 위 사진 자리에 화면 속 화면으로 넣을 수 있다. 상자·뚜껑 자동 확인이 검증되지 않았다면 사용자 확인을 그대로 보여주고, 수동 조작을 자동 인식처럼 보이게 편집하지 않는다.')

s = demo('03  핵심 시연 · 나사 A', '지금 작업할 나사만 밝게 표시합니다', '드라이버의 위치와 움직임에 따라 안내가 바뀌고, 다음 나사로 넘어갑니다.',
         IMG['hud'], 'Unity 안내 화면 (한쪽 눈)', '접근 전 → 파란 안내 → 초록 안내 → B 전환 · 중간을 자르지 않기', '임시 이미지 · 안내 디자인 예시 (나사 B)', IMG['yolo_s'], '작업 장면 · 5월 개발 영상 (검출 표시)', 226)
cyc = [('접근', '드라이버를 나사에 가져갑니다', SUB), ('작업 안내', '파란 강조', BLUE), ('이탈 안내', '초록 강조 · 드라이버를 뗍니다', GREEN), ('다음 나사', 'B로 이동', ACC)]
for k, (nm, d_, c) in enumerate(cyc):
    y = 404 + k * 46
    dot(s, 868, y + 4, '', d=16, fill=c)
    tb(s, 898, y, 110, 24, nm, size=14, color=WHITE, w8='b', anchor='m')
    tb(s, 1000, y, 204, 24, d_, size=12, color=SUB, anchor='m')
    if k < 3: rect(s, 875, y + 22, 2, 26, fill=LN)
foot(s, '초록 안내는 도구의 접근 · 유지 · 이탈에 따른 안내이며, 조임 품질을 측정한 결과가 아닙니다')
note(s, '[3:00~4:15 · 핵심 시연 ② 나사 A 한 사이클]\n대본 초안: 지금 작업할 나사만 밝게 표시됩니다. 드라이버의 위치와 움직임을 관찰해 안내를 바꾸고, 이탈이 확인되면 다음 나사로 이동합니다.\n편집: 접근 전부터 B 전환까지 실제 동작 길이 그대로. 단계가 바뀌는 순간 앞뒤로 말을 잠깐 멈춘다. 파란색/초록색은 실제 Unity 색을 그대로 쓴다(이 장의 색 점은 설명용).')

s = demo('03  핵심 시연 · 나사 B ~ D와 최종 확인', '나사 B, C, D를 지나 최종 확인으로 마칩니다', '목표가 바뀌는 순간을 중심으로 보여줍니다.',
         None, 'Unity 안내 화면 (한쪽 눈)', '목표 전환 순간 위주 · 최종 확인과 완료 문구까지', None, IMG['fr_end'], '작업 장면 · 5월 개발 영상', 160)
pic(s, IMG['geo3'], 298, 236, 300, 215)
tb(s, 298, 456, 300, 20, '최종 확인 · 전체 윤곽', size=11.5, color=DIM, align='c', anchor='m')
tb(s, 516, 180, 300, 20, '임시 이미지 · 윤곽 도식', size=10, color=DIM, align='r', anchor='m')
mx, my = 878, 412
rect(s, mx + 14, my + 14, 96, 76, line=LN, lw=1.25)
for (lx, ly, nm, on) in [(0, 0, 'A', True), (96, 0, 'B', False), (0, 76, 'C', False), (96, 76, 'D', False)]:
    dot(s, mx + lx, my + ly, nm, d=28, fill=ACC if on else BG, color='0B1513' if on else WHITE, line=None if on else SUB, size=11.5)
tb(s, mx - 10, my + 110, 144, 18, '작업자 쪽', size=10.5, color=DIM, align='c', anchor='m')
tb(s, 1024, 404, 180, 24, 'A → B → C → D', size=15, color=WHITE, w8='b', anchor='m')
tb(s, 1024, 432, 180, 24, '한 번에 하나만 강조합니다.', size=12.5, color=SUB, anchor='m')
tb(s, 1024, 496, 180, 24, '최종 확인', size=15, color=WHITE, w8='b', anchor='m')
tb(s, 1024, 524, 180, 24, '작업자가 직접 확인합니다.', size=12.5, color=SUB, anchor='m')
foot(s)
note(s, '[4:15~5:25 · 핵심 시연 ③]\n대본 초안: 같은 방식으로 B, C, D를 차례로 안내합니다. 네 나사를 마치면 전체 윤곽이 표시되고, 작업자가 조립 상태를 확인하면 안내를 마칩니다.\n편집: B~D는 목표가 바뀌는 순간과 동작만 보여주고 반복 설명은 줄인다.')

# ================================================================== 10 공간 안내
s = new()
head(s, '03  공간 안내', '고개를 조금 움직여도 목표 위치를 따라갑니다', '같은 착용 상태에서 거리와 시선을 바꿔 가며 확인합니다.')
for k, (nm, d_) in enumerate([('가까운 거리', '작업대에 가까이'), ('원래 거리', '작업 자세 그대로'), ('작은 좌우 이동', '고개를 좌우로 조금')]):
    x = 64 + k * 392
    slot(s, x, 180, 368, 300, nm, d_, img=IMG[('near', 'far', 'topv')[k]], tagtext='임시 사진 · 녹화로 교체')
panel(s, 64, 512, 1152, 100)
tb(s, 96, 512, 200, 100, '볼 것', size=18, color=ACC, w8='x', anchor='m')
tb(s, 240, 524, 940, 36, '현재 나사 강조가 실제 나사 위치에 머무는지', size=16, color=WHITE, w8='s', anchor='m')
tb(s, 240, 562, 940, 36, '윤곽이 상자와 뚜껑의 가장자리를 따라가는지', size=16, color=WHITE, w8='s', anchor='m')
foot(s, '사진은 임시 (이전에 찍은 작업대 사진) · 세 칸 모두 실제 녹화로 교체')
note(s, '[5:25~6:15 · 공간 안내를 자세히]\n대본 초안: 안내는 화면에 고정된 그림이 아니라 작업대의 위치에 맞춰 그려집니다. 가까이 다가가거나 고개를 조금 움직여도 같은 나사를 가리키는지 확인해 보겠습니다.\n주의: 이 장의 제목과 대본은 실제 녹화에서 확인된 범위에 맞춰 고친다. 카메라 영상 위에 Unity 화면을 얹어 "실제 시야"로 설명하지 않는다.')

chapter('04', 'AI와 구현', '영상에서 도구와 위치를 찾아 단계를 판단합니다', IMG['ch4'], '사진: Unsplash · QIU DEXING', '[6:15 무렵 · 장 구분] 2~3초. 사진은 무료 사진(프로젝트 촬영분 아님).')

# ================================================================== 11 AI 검출 영상
s = new()
head(s, '04  AI와 구현', 'AI는 영상에서 도구와 작업 위치를 찾습니다', '마커, 도구, 손을 각각 검출해 비교한 개발 영상입니다.')
mv = s.shapes.add_movie(A + '03_AI_검출/AI_검출비교_원본_20260520.mp4', px(64), px(170), px(788), px(430), poster_frame_image=IMG['poster'], mime_type='video/mp4')
rect(s, 64, 170, 788, 430, line=LN, lw=1)
tb(s, 64, 606, 788, 18, '2026년 5월 검출 비교 영상 (약 15초 · 소리 없음) · 최신 Unity 시연과 다른 영상', size=10.5, color=DIM, anchor='m')
for k, (lg, nm, d_) in enumerate([('opencv', 'ArUco', '마커로 작업대의 좌표를 잡습니다.'), ('yolo', 'YOLO', '영상에서 드라이버를 찾습니다.'), ('mediapipe', 'MediaPipe', '손 관절을 찾습니다. 별도의 오프라인 분석에 씁니다.')]):
    y = 178 + k * 142
    panel(s, 884, y, 332, 124)
    pic(s, LOGO(lg), 904, y + 20, 36, 36)
    tb(s, 954, y + 18, 240, 40, nm, size=19, color=WHITE, w8='x', anchor='m')
    tb(s, 904, y + 66, 296, 48, d_, size=13, color=SUB, ls=1.4)
foot(s, '위 줄: 원본 영상 + 검출 · 아래 줄: 위에서 본 시점으로 편 영상 + 검출')
note(s, '[6:15~6:45 · AI ① 검출 영상]\n대본 초안: 욜로는 영상에서 드라이버를 찾습니다. 아루코 마커로는 작업대의 좌표를 잡습니다.\n편집: 영상은 한 번만 약 15초 재생(반복 재생으로 늘리지 않기). 이 영상은 5월 개발 영상이며 무음이다. 영상 파일이 이 장에 들어 있다.')

# ================================================================== 12 검출 이미지 3장
s = new()
head(s, '04  AI와 구현', '도구의 위치와 나사의 위치를 비교합니다', '마커로 계산한 나사 위치에 드라이버가 다가오고, 머물고, 떠나는지를 봅니다.')
for k, (key, nm, role, d_, live) in enumerate([('aruco', 'ArUco · 마커', '작업대 좌표', '마커 좌표에서 나사 A ~ D의 위치를 계산합니다.', True),
                                               ('yolo', 'YOLO · 도구', '드라이버 위치', '드라이버를 찾아 목표 나사와의 관계를 봅니다.', True),
                                               ('mediapipe', 'MediaPipe · 손', '손 관절', '별도의 오프라인 분석 경로에서 사용합니다.', False)]):
    x = 64 + k * 392
    pic(s, IMG[key], x, 176, 368, 245)
    rect(s, x, 421, 368, 3, fill=ACC if live else DIM)
    tb(s, x, 436, 368, 28, nm, size=18, color=WHITE, w8='x', anchor='m')
    chip(s, x, 472, 108 if live else 122, 26, '실시간 안내' if live else '오프라인 분석', fill=ACCD if live else None, color=ACC if live else DIM, line=None if live else LN, size=11, w8='b')
    tb(s, x + (120 if live else 134), 472, 240, 26, role, size=12.5, color=SUB, anchor='m')
    tb(s, x, 510, 360, 50, d_, size=13.5, color=SUB, ls=1.45)
foot(s, '2026년 5월 개발 영상의 검출 결과')
note(s, '[6:45~7:05 · AI ② 검출 결과]\n대본 초안: 마커로 계산한 나사 위치와 도구 위치를 비교하고, 연속된 관측을 이용해 작업 단계를 판단합니다.\n사실 확인: MediaPipe와 HMM/Viterbi는 별도의 오프라인 분석 경로. 현재 실시간 단계 전이를 HMM이 직접 수행한다고 말하지 않는다.')

# ================================================================== 13 처리 흐름
s = new()
head(s, '04  AI와 구현', '위치는 마커로, 단계는 도구의 움직임으로 판단합니다', '판단한 좌표와 단계를 안경과 관제 화면에 함께 전달합니다.')
def lane(y, label, boxes, color=ACC, logos=(), thumb=None):
    tb(s, 64, y - 24, 200, 20, label, size=12, color=color, w8='b', anchor='m')
    if thumb: pic(s, thumb, 64, y, 96, 56)
    x = 170
    for k, (t, w, hi) in enumerate(boxes):
        r = rect(s, x, y, w, 56, fill=ACCD if hi else PANEL, line=ACC if hi else LN, lw=1, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .18
        tb(s, x, y, w, 56, t, size=13.5, color=WHITE, w8='s' if hi else 'm', align='c', anchor='m')
        x += w
        if k < len(boxes) - 1: arrow(s, x + 1, y + 14); x += 30
    lx = 1216 - len(logos) * 40
    for k, lg in enumerate(logos): pic(s, LOGO(lg), lx + k * 40 + 8, y + 14, 28, 28)
lane(186, '위치', [('카메라', 96, False), ('ArUco 검출 · PnP', 180, False), ('나사 A ~ D 위치 계산', 200, True)], logos=('python', 'opencv'), thumb=IMG['t_aruco'])
lane(278, '단계', [('카메라', 96, False), ('YOLO 도구 검출', 150, False), ('도구와 목표의 관계', 168, False), ('시간 증거 · FSM', 150, False), ('현재 단계 · 다음 행동', 190, True)], logos=('yolo',), thumb=IMG['t_yolo'])
rect(s, 64, 354, 1152, 1, fill=LN)
lane(390, '전달', [('좌표와 단계', 140, False), ('로컬 HTTP', 120, False), ('Unity 양안 안내', 170, True)], logos=('unity', 'csharp'), thumb=IMG['t_ar'])
tb(s, 664, 390, 28, 56, '+', size=18, color=DIM, w8='s', align='c', anchor='m')
r = rect(s, 696, 390, 160, 56, fill=ACCD, line=ACC, lw=1, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .18
tb(s, 696, 390, 160, 56, '브라우저 관제', size=13.5, color=WHITE, w8='s', align='c', anchor='m')
tb(s, 170, 300 + 40, 800, 18, '접근 · 유지 · 이탈', size=10.5, color=DIM, anchor='m').left = px(446)
panel(s, 64, 486, 1152, 126)
for k, (h_, d_) in enumerate([('시간 증거', '한 장면이 아니라 이어진 관측으로 단계를 넘깁니다. 관측이 잠깐 끊겼을 때 진행을 보존하고 다시 확인하도록 보강했습니다.'),
                              ('안내의 의미', '안내 색은 도구의 접근 · 유지 · 이탈을 나타냅니다. 체결 토크나 조임 품질을 측정한 결과가 아닙니다.')]):
    y = 498 + k * 54
    tb(s, 96, y, 130, 48, h_, size=14, color=ACC, w8='x', anchor='m')
    tb(s, 230, y, 960, 48, d_, size=13, color=SUB, anchor='m', ls=1.35)
foot(s, 'MediaPipe · HMM/Viterbi는 별도의 오프라인 분석 경로입니다')
note(s, '[7:05~7:45 · AI ③ 처리 흐름]\n대본 초안: 처리 흐름은 세 갈래입니다. 마커에서 나사 위치를 계산하고, 도구 검출 결과와 비교해 접근, 유지, 이탈을 봅니다. 이어진 관측이 쌓이면 단계가 넘어가고, 그 결과가 유니티 안내와 관제 화면으로 전달됩니다.\n편집: 설명 중인 줄만 밝게(나머지는 어둡게) 보이도록 줄마다 나타내기 애니메이션을 걸면 좋다. 발음: YOLO=욜로, ArUco=아루코, PnP=피 엔 피, FSM=에프 에스 엠, Unity=유니티.\n금지: 이전 문서의 정확도 수치를 현재 실시간 성공률로 쓰지 않는다. 가림을 항상 견딘다고 일반화하지 않는다.')

chapter('05', '관제와 개선', '전체 흐름을 확인하고, 화면은 더 단순하게', IMG['ch5'], '사진: Unsplash @myblu', '[7:45 무렵 · 장 구분] 2~3초. 사진은 무료 사진(프로젝트 촬영분 아님).')

# ================================================================== 14 관제
s = new()
head(s, '05  관제', '관제 화면에서는 전체 진행을 확인합니다', '작업자는 눈앞의 안내를, 확인하는 사람은 전체 흐름을 봅니다.')
pic(s, IMG['ctl'], 64, 170, 836, 448)
rect(s, 64, 170, 836, 448, line=LN, lw=1)
tag(s, 76, 182, '실시간 관제 녹화로 교체')
tb(s, 64, 624, 836, 18, '저장한 상태를 다시 재생한 발표용 화면 · 작업대 영상은 별도 카메라 사진', size=10.5, color=DIM, anchor='m')
for k, (h_, d_) in enumerate([('현재 작업', '나사 B'), ('다음 행동', '드라이버를 나사 B에 대어 주세요'), ('진행', '대상 접근 → 접근 유지 → 이탈 대기'), ('위치', 'A ~ D 중 어느 나사인지 그림으로')]):
    y = 170 + k * 114
    panel(s, 932, y, 284, 98)
    rect(s, 932, y, 3, 98, fill=ACC)
    tb(s, 954, y + 12, 250, 22, h_, size=12, color=ACC, w8='b', anchor='m')
    tb(s, 954, y + 36, 250, 50, d_, size=15, color=WHITE, w8='s', ls=1.35)
foot(s)
note(s, '[7:45~8:45 · 관제와 혼자 쓰는 흐름]\n대본 초안: 관제 화면에는 현재 작업과 다음 행동, 진행 상태가 표시됩니다. 혼자 쓸 때는 이 화면에서 작업을 시작하고 끝내며, 작업 기록을 확인합니다.\n교체: 새 관제 녹화(시작 · 현재 단계 · 종료 · 작업 기록, 30~60초). 운영자 도구로 수동 확인을 했다면 자동 인식처럼 보이게 편집하지 않는다.')

# ================================================================== 15 피드백과 개선
s = new()
head(s, '05  사용자 피드백과 개선', '상태 설명을 줄이고, 지금 할 행동 한 줄로', '사용자가 원한 것은 내부 상태가 아니라 지금 무엇을 해야 하는지였습니다.')
pic(s, IMG['old'], 64, 172, 520, 347); pic(s, IMG['ar_s'], 696, 172, 520, 347)
chip(s, 76, 184, 60, 26, '이전', fill='000000', color=WHITE, line=None, size=11.5, w8='b')
chip(s, 708, 184, 74, 26, '개선안', fill=ACC, color='0B1513', line=None, size=11.5, w8='b')
tb(s, 584, 172, 112, 347, '→', size=34, color=ACC, w8='s', align='c', anchor='m', wrap=False)
tb(s, 64, 526, 520, 22, '영문 상태 문구가 여러 줄 · SCREW A | 1/4, MOVE CLEAR …', size=12.5, color=SUB, anchor='m')
tb(s, 696, 526, 520, 22, '작은 단계 표시 + 큰 행동 한 줄 + 목표 강조', size=12.5, color=WHITE, w8='s', anchor='m')
xs = 64
for t, w in [('상자를 놓아주세요', 176), ('뚜껑을 덮어주세요', 176), ('나사 A를 조여주세요', 190), ('드라이버를 떼어주세요', 204), ('조립 상태를 확인해주세요', 222)]:
    chip(s, xs, 584, w, 40, t, fill=PANEL, color=WHITE, line=LN, size=13.5); xs += w + 12
tag(s, xs + 6, 592, '반영 후 녹화')
foot(s, '왼쪽: 기존 팜플렛의 안내 예시 · 오른쪽: 안내 디자인 예시 (설명용 합성)')
note(s, '[8:45~9:30 · 사용자 피드백과 개선]\n대본 초안: 초기 화면에는 상태 설명이 많았습니다. 사용자가 원하는 것은 내부 상태가 아니라, 지금 무엇을 해야 하는지였습니다. 그래서 행동 안내를 우선하는 화면으로 정리합니다.\n교체: 간소화한 실제 화면을 녹화한 뒤 오른쪽 이미지를 바꾼다. 아래 한글 문구는 개선안이므로 앱에 반영하고 확인한 것만 남긴다. 검증된 복구 장면이 있으면 10~20초 추가.')

# ================================================================== 16 마무리
s = new()
pic(s, IMG['close'], 0, 0, 1280, 720)
tb(s, 84, 176, 900, 170, ['눈앞에는 다음 작업을,', '관제에는 전체 흐름을.'], size=42, color=WHITE, w8='x', ls=1.22)
rect(s, 86, 362, 56, 3, fill=ACC)
tb(s, 84, 382, 900, 32, 'AI Assembly Guide는 조립 순서를 따라 작업을 이어가도록 돕습니다.', size=18, color=SUB, anchor='m')
tb(s, 84, 560, 600, 26, 'AI Assembly Guide', size=20, color=WHITE, w8='x', anchor='m')
tb(s, 84, 590, 900, 22, '작업 단계 인식 기반 AR 조립 안내', size=13.5, color=SUB, anchor='m')
tb(s, 84, 622, 900, 22, '개발 최민준 (C011207)   |   지도교수 윤영 교수님', size=13.5, color=SUB, w8='m', anchor='m')
tb(s, 780, 684, 436, 16, '배경: AR 안내 예시 (설명용 합성)', size=9.5, color=DIM, align='r', anchor='m')
note(s, '[9:30~10:00 · 마무리]\n대본 초안: 눈앞에는 다음 작업을, 관제에는 전체 흐름을. AI Assembly Guide는 조립 순서를 따라 작업을 이어가도록 돕습니다.\n교체: 배경을 대표 안내 장면 또는 완료 화면 녹화로 바꿀 수 있다.')

# ================================================================== 17 제작 메모 (영상 제외)
s = new()
rect(s, 0, 0, 1280, 6, fill=AMBER)
tb(s, 64, 30, 800, 40, '제작 메모 — 영상에는 넣지 않는 장', size=22, color=AMBER, w8='x', anchor='m')
tb(s, 716, 30, 500, 40, '녹화가 끝나면 이 표대로 교체', size=13, color=AMBER, w8='s', align='r', anchor='m')
rows = [('3', 'AR 안내 예시 (사진 + 안내 디자인 합성)', '새 Unity 녹화: 몸체 → 뚜껑 → 나사 강조를 짧게 연결'),
        ('6', '관제 준비 화면 캡처 (실행 전)', '최신 UI로 다시 캡처하거나 녹화'),
        ('9 · 10 · 11', '윤곽 도식, 안내 디자인 예시, 5월 개발 영상 장면', '같은 실행의 Unity 출력 + 관제 녹화 (약 3~4분). 나사 A 한 사이클은 자르지 않기'),
        ('9 · 19', '한글 안내 문구 ("상자를 놓아주세요" 등)', '개선안. 앱에 반영하고 확인한 문구만 남기기'),
        ('7 · 9', '상자 · 뚜껑은 작업자가 확인하고 넘어간다고 표기', '자동 확인이 구현 · 검증되면 범례와 대본 수정'),
        ('12', '이전에 찍은 작업대 사진 3장 (임시)', '가까운 거리 / 원래 거리 / 작은 좌우 이동 녹화 (30~50초). 제목은 녹화 결과에 맞추기'),
        ('14', '5월 검출 비교 영상이 들어 있음 (무음)', '한 번만 재생. 최신 시연과 다른 영상이라는 표기 유지'),
        ('18', '저장 상태 재생 화면', '실시간 관제 녹화: 시작 · 현재 단계 · 종료 · 작업 기록'),
        ('19', '기존 팜플렛 화면 vs 안내 디자인 예시', '간소화한 실제 화면 캡처로 교체')]
tb(s, 64, 88, 110, 24, '장', size=11.5, color=DIM, w8='b', anchor='m'); tb(s, 180, 88, 430, 24, '지금 들어간 것', size=11.5, color=DIM, w8='b', anchor='m'); tb(s, 624, 88, 590, 24, '바꾸거나 확인할 것', size=11.5, color=DIM, w8='b', anchor='m')
for k, (n, a, b) in enumerate(rows):
    y = 116 + k * 46
    rect(s, 64, y, 1152, 1, fill=LN)
    tb(s, 64, y + 2, 110, 44, n, size=13, color=AMBER, w8='x', anchor='m')
    tb(s, 180, y + 2, 430, 44, a, size=12.5, color=WHITE, anchor='m', ls=1.3)
    tb(s, 624, y + 2, 590, 44, b, size=12.5, color=SUB, anchor='m', ls=1.3)
rect(s, 64, 116 + 9 * 46, 1152, 1, fill=LN)
tb(s, 64, 544, 1152, 22, '자료에 없어서 만들어 넣은 것', size=13, color=AMBER, w8='x', anchor='m')
tb(s, 64, 568, 1152, 110, ['· 각 장의 제목과 설명 문장, 4장 사진 아래 설명과 비교 문장, 10장의 사이클 표, 12장의 "볼 것" 두 줄',
                           '· 발표자 노트의 대본 초안과 구간 시간 (구성안의 예시 문장과 시간표를 바탕으로 작성 · 실제 녹화 길이에 맞춰 확정)',
                           '· 2 · 4 · 5 · 8 · 13 · 17장의 사진은 Unsplash 무료 사진 (각 장 오른쪽 아래에 표기). 프로젝트에서 찍은 사진이 아님',
                           '· 주황 표시(녹화 영상 자리, 교체 표시)는 영상을 넣으면서 지우기. 정확도 같은 수치는 넣지 않았음'], size=11.5, color=SUB, ls=1.5)
note(s, '영상에 넣지 않는 장. 녹화·편집 체크리스트.')

# ------------------------------------------------------------------ 템플릿 표지 제거 후 저장
lst = prs.slides._sldIdLst; first = lst[0]
prs.part.drop_rel(first.get(qn('r:id'))); lst.remove(first)
prs.save(OUT); print('saved', OUT, len(prs.slides))
