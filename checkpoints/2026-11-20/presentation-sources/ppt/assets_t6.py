# -*- coding: utf-8 -*-
"""v6: 가림 기록 그래프를 좁게(옆에 영상이 들어감), 영상 구간 표시 추가."""
import json
from PIL import Image, ImageDraw
W_ = '/home/claude/grad'; OUT = W_ + '/prep_t6/'
NAVY = (56, 87, 125); ORNG = (217, 130, 43); LINE = (213, 220, 230); K = 4
V = json.load(open(W_ + '/t4/vis.json')); DUR = V['dur']
STEP_T = [0, 13.0, 27.0, 49.4, 71.2, 100.6, 118.7]
RW, RH = 762, 176; RX0, RX1 = 74, 750
def tx(t): return RX0 + t * (RX1 - RX0) / DUR
TY0, TY1 = 22, 36; SY_B, SY_T = 156, 70
im = Image.new('RGBA', (RW * K, RH * K), (0, 0, 0, 0))
ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); do = ImageDraw.Draw(ov)
for a, b, v in V['segs']:
    if not v and b - a >= 0.3: do.rectangle([tx(a) * K, (TY1 + 8) * K, tx(b) * K, (SY_B + 6) * K], fill=ORNG + (40,))
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
C0, C1 = 29.5, 38.5                                                        # 옆에 넣은 영상의 구간
d.line([tx(C0) * K, 12 * K, tx(C1) * K, 12 * K], fill=NAVY + (255,), width=int(1.5 * K))
for t in (C0, C1): d.line([tx(t) * K, 8 * K, tx(t) * K, 17 * K], fill=NAVY + (255,), width=int(1.5 * K))
im.resize((RW * 2, RH * 2), Image.LANCZOS).save(OUT + 'recovery_n.png')
print('tick', [round(tx(t), 1) for t in (0, 30, 60, 90, 120)], 'step', [round(tx(t), 1) for t in STEP_T], 'clip', round(tx(C0), 1), round(tx(C1), 1))
