# -*- coding: utf-8 -*-
"""v8 그림: 보정 장의 스테레오 기하 그림을 덱 색과 글꼴로 다시 그린 것, 검증 장의 줄머리 그림."""
import math
from PIL import Image, ImageDraw, ImageFont
W_ = '/home/claude/grad'; OUT = W_ + '/prep_v8/'
NAVY = (56, 87, 125); LBLUE = (158, 182, 210); ORNG = (217, 130, 43); GREY = (107, 114, 128); DARK = (34, 34, 34); WHITE = (255, 255, 255)
K = 4; W, H = 440, 300
im = Image.new('RGB', (W * K, H * K), WHITE); d = ImageDraw.Draw(im)
F = lambda w, s: ImageFont.truetype('/root/.fonts/Pretendard-%s.otf' % w, int(s * K))
def P(x, y): return (x * K, y * K)
def line(a, b, c=NAVY, w=1.5): d.line([P(*a), P(*b)], fill=c, width=max(1, int(w * K)))
def dashed(a, b, c=NAVY, w=1.8, on=7, off=5):
    L = math.dist(a, b); n = int(L // (on + off)) + 1; ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    for i in range(n):
        s = i * (on + off); e = min(s + on, L)
        if s >= L: break
        line((a[0] + ux * s, a[1] + uy * s), (a[0] + ux * e, a[1] + uy * e), c, w)
def dot(c, r, fill, outline=None, ow=0):
    d.ellipse([(c[0] - r) * K, (c[1] - r) * K, (c[0] + r) * K, (c[1] + r) * K], fill=fill, outline=outline, width=int(ow * K))
def head(tip, ang, c=GREY, L=7, Wd=3.2):                              # 화살촉 (ang: 진행 방향, 도)
    a = math.radians(ang); ux, uy = math.cos(a), math.sin(a); px_, py_ = -uy, ux
    b = (tip[0] - ux * L, tip[1] - uy * L)
    d.polygon([P(*tip), P(b[0] + px_ * Wd, b[1] + py_ * Wd), P(b[0] - px_ * Wd, b[1] - py_ * Wd)], fill=c)
def text(xy, s, f, c=DARK, anchor='la'): d.text(P(*xy), s, font=f, fill=c, anchor=anchor)
PT = (261, 24); OL = (150, 214); OR = (372, 214); YP = 152
t = (OL[1] - YP) / (OL[1] - PT[1]); PL = (OL[0] + (PT[0] - OL[0]) * t, YP); PR = (OR[0] + (PT[0] - OR[0]) * t, YP)
# 광축 (위로 향하는 가는 화살표)
for o in (OL, OR):
    line((o[0], o[1]), (o[0], 62), GREY, 1.1); head((o[0], 56), -90)
# 기준선 (점선) 과 깊이
dashed(OL, OR, GREY, 1.1, 3, 3)
line((PT[0], 40), (PT[0], OL[1] - 6), GREY, 1.1); head((PT[0], OL[1]), 90); head((PT[0], 34), -90)
# 점 P 로 가는 선
dashed(OL, PT, NAVY, 2.2); dashed(OR, PT, NAVY, 2.2)
# 이미지 평면
line((OL[0] - 58, YP), (OL[0] + 58, YP), NAVY, 3.5); line((OR[0] - 58, YP), (OR[0] + 58, YP), NAVY, 3.5)
dot(PL, 6.5, NAVY, WHITE, 1.6); dot(PR, 6.5, NAVY, WHITE, 1.6)
dot(OL, 7.5, LBLUE, NAVY, 1.8); dot(OR, 7.5, LBLUE, NAVY, 1.8)
dot(PT, 7.5, ORNG, WHITE, 1.6)
# 초점 거리
FX = OL[0] - 38
line((FX, YP + 8), (FX, OL[1] - 7), GREY, 1.1); head((FX, YP + 3), -90, L=6, Wd=2.8); head((FX, OL[1] - 2), 90, L=6, Wd=2.8)
# 기준선 길이
line((OL[0] + 6, 247), (OR[0] - 6, 247), GREY, 1.1); head((OL[0], 247), 180); head((OR[0], 247), 0)
fs = F('Medium', 12); fm = F('SemiBold', 12.5); fb = F('ExtraBold', 14.5); fsub = F('SemiBold', 9)
text((PT[0] + 13, PT[1]), 'P (X, Y, Z)', fm, ORNG, 'lm')
text((OL[0] - 8, YP - 12), '이미지 평면', fs, GREY, 'rm'); text((OR[0] + 8, YP - 12), '이미지 평면', fs, GREY, 'lm')
text((PT[0] + 8, 104), 'Depth', fm, DARK, 'lm')
text((FX - 6, (YP + OL[1]) / 2), 'F = Focal length', fs, GREY, 'rm')
def sub(xy, toks, anchor_right=False):
    # toks: [(글자, 아래첨자 여부)] 를 이어서 쓴다
    ws = [d.textlength(tx_, font=(fsub if sb else fm)) / K for tx_, sb in toks]
    x = xy[0] - sum(ws) if anchor_right else xy[0]
    for (tx_, sb), w_ in zip(toks, ws):
        text((x, xy[1] + (3 if sb else 0)), tx_, fsub if sb else fm, DARK, 'lm'); x += w_
def pt(c): return [('P', 0), (c, 1), (' (x', 0), (c, 1), (', y', 0), (c, 1), (')', 0)]
sub((PL[0] + 12, YP + 16), pt('l')); sub((PR[0] - 12, YP + 16), pt('r'), True)
text((OL[0] - 14, OL[1] + 16), 'Optical center (left)', fs, GREY, 'rm'); sub((OL[0] + 12, OL[1] + 15), [('O', 0), ('l', 1)])
text((OR[0] - 14, OR[1] + 16), 'Optical center (right)', fs, GREY, 'rm'); sub((OR[0] + 12, OR[1] + 15), [('O', 0), ('r', 1)])
text(((OL[0] + OR[0]) / 2, 259), 'B = Baseline', fm, DARK, 'mm')
text((OL[0], 284), '왼쪽 카메라', fb, NAVY, 'mm'); text((OR[0], 284), '오른쪽 카메라', fb, NAVY, 'mm')
im.resize((W * 2, H * 2), Image.LANCZOS).save(OUT + 'stereo_geo_redraw.png')

def cover(src, w, h, fx=.5, fy=.5, scale=2, box=None):
    m = Image.open(src).convert('RGB')
    if box: m = m.crop(box)
    Wd, Hd = int(w * scale), int(h * scale); r = max(Wd / m.width, Hd / m.height)
    m = m.resize((int(m.width * r + .5), int(m.height * r + .5)), Image.LANCZOS)
    x = int((m.width - Wd) * fx); y = int((m.height - Hd) * fy); return m.crop((x, y, x + Wd, y + Hd))
cover(W_ + '/prep_t6/det_poster.jpg', 150, 84).save(OUT + 'ev1.jpg', quality=90)
cover(W_ + '/prep_t6/demo_poster.jpg', 150, 84, box=(190, 60, 1090, 564)).save(OUT + 'ev2.jpg', quality=90)
cover(W_ + '/prep_s/overlap.png', 150, 84, fy=.3).save(OUT + 'ev3.jpg', quality=92)
print('ok')
