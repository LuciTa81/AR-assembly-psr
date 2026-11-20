# -*- coding: utf-8 -*-
"""v5 에 새로 들어가는 그림: 1학기 비교 실험 타임라인(세 줄), take4 가림 기록, 데이터 장 · 문제 장의 사진."""
import json, numpy as np
from PIL import Image, ImageDraw
W_ = '/home/claude/grad'; OUT = W_ + '/prep_t5/'; M = W_ + '/sem1/media/'
NAVY = (56, 87, 125); GTC = (190, 200, 214); ORNG = (217, 130, 43); LINE = (213, 220, 230); PALE = (238, 242, 247)
K = 4                                                     # 4배로 그려 2배로 줄인다

def cover(im, w, h, fx=.5, fy=.5, scale=2, box=None):
    im = (Image.open(im) if isinstance(im, str) else im).convert('RGB')
    if box: im = im.crop(box)
    Wd, Hd = int(w * scale), int(h * scale); r = max(Wd / im.width, Hd / im.height)
    im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x = int((im.width - Wd) * fx); y = int((im.height - Hd) * fy); return im.crop((x, y, x + Wd, y + Hd))

# ------------------------------------------------------------------ 1. 타임라인 (session 17, 119프레임)
S = json.load(open(W_ + '/sem1/session17_states.json')); GT = S['GT']
CW, CH = 700, 108; X0, X1 = 30, 692; YB, YT = 94, 12                      # 그림 안의 좌표 (슬라이드 px)
def fx(f): return X0 + (f - 1) * (X1 - X0) / 118                          # f: 1..119
def fy(s): return YB - s * (YB - YT) / 6
HW = (X1 - X0) / 118 / 2
def steps(d, seq, color, w):
    pts = []
    for i, s in enumerate(seq):
        f = i + 1; pts += [(fx(f) - HW, fy(s)), (fx(f) + HW, fy(s))]
    d.line([(x * K, y * K) for x, y in pts], fill=color, width=int(w * K), joint='curve')
for key in ('FW', 'FSM', 'HMM'):
    im = Image.new('RGBA', (CW * K, CH * K), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for s in range(7):                                                     # 옅은 가로선
        d.line([(X0 - HW) * K, fy(s) * K, (X1 + HW) * K, fy(s) * K], fill=LINE + (150,), width=K // 2)
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
    for i, (g, p) in enumerate(zip(GT, S[key])):                           # 틀린 프레임
        if g != p:
            f = i + 1; do.rectangle([(fx(f) - HW) * K, (YT - 8) * K, (fx(f) + HW) * K, (YB + 6) * K], fill=ORNG + (70,))
            do.rectangle([(fx(f) - HW) * K, (YB + 8) * K, (fx(f) + HW) * K, (YB + 12) * K], fill=ORNG + (255,))
    im = Image.alpha_composite(im, ov); d = ImageDraw.Draw(im)
    steps(d, GT, GTC + (255,), 5); steps(d, S[key], NAVY + (255,), 2)
    im.resize((CW * 2, CH * 2), Image.LANCZOS).save(OUT + 'tl_%s.png' % key)
print('frame x', [round(fx(f), 1) for f in (1, 30, 60, 90, 119)])

# ------------------------------------------------------------------ 2. take4 가림 기록
V = json.load(open(W_ + '/t4/vis.json')); DUR = V['dur']
STEP_T = [0, 13.0, 27.0, 49.4, 71.2, 100.6, 118.7]                         # Unity 화면의 단계 글자가 바뀐 때
RW, RH = 1138, 176; RX0, RX1 = 96, 1126
def tx(t): return RX0 + t * (RX1 - RX0) / DUR
im = Image.new('RGBA', (RW * K, RH * K), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
TY0, TY1 = 10, 24                                                          # 윤곽 표시 줄
SY_B, SY_T = 156, 58                                                       # 단계 계단
ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
for a, b, v in V['segs']:
    if not v and b - a >= 0.3:
        do.rectangle([tx(a) * K, (TY1 + 8) * K, tx(b) * K, (SY_B + 6) * K], fill=ORNG + (40,))
im = Image.alpha_composite(im, ov); d = ImageDraw.Draw(im)
for a, b, v in V['segs']:
    d.rectangle([tx(a) * K, TY0 * K, tx(b) * K, TY1 * K], fill=(NAVY if v else ORNG) + (255,))
for s in range(7):
    y = SY_B - s * (SY_B - SY_T) / 6
    d.line([RX0 * K, y * K, RX1 * K, y * K], fill=LINE + (150,), width=K // 2)
pts = []
for s, t0 in enumerate(STEP_T):
    t1 = STEP_T[s + 1] if s < 6 else DUR; y = SY_B - s * (SY_B - SY_T) / 6
    pts += [(tx(t0), y), (tx(t1), y)]
d.line([(x * K, y * K) for x, y in pts], fill=NAVY + (255,), width=int(2.5 * K), joint='curve')
for t in (0, 30, 60, 90, 120):
    d.line([tx(t) * K, (SY_B + 6) * K, tx(t) * K, (SY_B + 12) * K], fill=(138, 148, 166, 255), width=K)
im.resize((RW * 2, RH * 2), Image.LANCZOS).save(OUT + 'recovery.png')
hid = [(a, b) for a, b, v in V['segs'] if not v]
print('hidden %.1f s of %.1f (%.1f%%), >=1s: %d, longest %.1f' % (sum(b - a for a, b in hid), DUR, sum(b - a for a, b in hid) / DUR * 100, sum(1 for a, b in hid if b - a >= 1), max(b - a for a, b in hid)))
print('tick x', [round(tx(t), 1) for t in (0, 30, 60, 90, 120)], 'step label x', [round(tx(t), 1) for t in STEP_T])

# ------------------------------------------------------------------ 3. 사진
cover(M + 'image17.jpeg', 272, 170, box=(192, 0, 3648, 2160)).save(OUT + 'ds1.jpg', quality=90)
a = cover(M + 'image19.jpeg', 134, 170, fx=.5); b = cover(M + 'image20.jpeg', 134, 170, fx=.5)
two = Image.new('RGB', (272 * 2, 170 * 2), (255, 255, 255)); two.paste(a, (0, 0)); two.paste(b, (138 * 2, 0)); two.save(OUT + 'ds2.jpg', quality=90)
cover(M + 'image12.png', 272, 170, box=(0, 0, 656, 410)).save(OUT + 'ds3.jpg', quality=92)
cover(M + 'image22.jpeg', 272, 170, box=(0, 40, 800, 540)).save(OUT + 'ds4.jpg', quality=90)
cover(W_ + '/prep_s/overlap.png', 368, 190).save(OUT + 'ch2.jpg', quality=92)
cover(W_ + '/t4/full/c33.jpg', 368, 190, box=(160, 60, 1280, 638)).save(OUT + 'ch3.jpg', quality=90)
print('ok')
