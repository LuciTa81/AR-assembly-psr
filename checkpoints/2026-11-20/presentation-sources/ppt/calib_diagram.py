# -*- coding: utf-8 -*-
"""보정 장의 개념도 (글자는 슬라이드에서 얹는다). 440x300 기준 좌표, 4배로 그려 2배로 줄인다."""
from PIL import Image, ImageDraw
K = 4; W, H = 440, 300
PALE = (238, 242, 247); NAVY = (56, 87, 125); TEAL = (38, 160, 142); ORNG = (217, 130, 43); GREY = (138, 148, 166); WHITE = (255, 255, 255)
im = Image.new('RGB', (W * K, H * K), PALE); d = ImageDraw.Draw(im)
def P(x, y): return (x * K, y * K)
def line(a, b, c, w): d.line([P(*a), P(*b)], fill=c, width=int(w * K))
def dot(c, r, fill, outline=None, ow=0):
    d.ellipse([(c[0] - r) * K, (c[1] - r) * K, (c[0] + r) * K, (c[1] + r) * K], fill=fill, outline=outline, width=int(ow * K))
PT = (220, 50); EL = (140, 232); ER = (300, 232); YD = 158
t = (EL[1] - YD) / (EL[1] - PT[1]); XL = EL[0] + (PT[0] - EL[0]) * t; XR = ER[0] + (PT[0] - ER[0]) * t
line(EL, PT, TEAL, 1.6); line(ER, PT, ORNG, 1.6)                      # 눈에서 나사로 가는 선
for (x0, x1, cx) in ((82, 198, EL[0]), (242, 358, ER[0])):            # 눈별 화면
    line((x0, YD), (x1, YD), NAVY, 3)
    line((x0, YD - 6), (x0, YD + 6), NAVY, 2); line((x1, YD - 6), (x1, YD + 6), NAVY, 2)
    line((cx, YD + 3), (cx, YD + 12), GREY, 1.2)                      # 화면 가운데 눈금
dot((XL, YD), 6.5, TEAL, WHITE, 1.6); dot((XR, YD), 6.5, ORNG, WHITE, 1.6)
dot(PT, 13, None, NAVY, 1.6); dot(PT, 6.5, NAVY)                      # 나사
for e in (EL, ER):
    dot(e, 11, WHITE, NAVY, 2); dot(e, 4, NAVY)
line((EL[0], 258), (ER[0], 258), GREY, 1.2)                           # PD
for x in (EL[0], ER[0]): line((x, 253), (x, 263), GREY, 1.2)
im.resize((W * 2, H * 2), Image.LANCZOS).save('/home/claude/grad/prep_s/calib.png')
print('ok', XL, XR)
