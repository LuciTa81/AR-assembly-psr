# -*- coding: utf-8 -*-
"""표지를 포스터(AI Assembly Guide.pdf, A0 세로)의 구성으로 16:9에 맞춰 다시 짠다.
배경 · 안경은 PDF에서 꺼낸 원본(prep_cov/im-000.jpg, glasses_rgba.png), 04 단계 카드와 초록 선은 PowerPoint 도형으로 그린다."""
import sys, glob, copy
import numpy as np
from PIL import Image, ImageOps
from lxml import etree
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from pptx.oxml.ns import qn
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.util import Pt
W_ = '/home/claude/grad'; PC = W_ + '/prep_cov/'
GREEN = '5EE6A0'; CYAN = '38D6F0'; CARD = '0C1912'; MUTE = 'A9B8B0'

def prep_bg(fy=.42, mirror=False):
    im = Image.open(PC + 'im-000.jpg').convert('RGB')
    if mirror: im = ImageOps.mirror(im)
    W, H = im.size; h = int(W * 9 / 16); y = int((H - h) * fy); im = im.crop((0, y, W, y + h)).resize((2560, 1440), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    xs = np.linspace(0, 1, 2560)[None, :, None]; ys = np.linspace(0, 1, 1440)[:, None, None]
    k = .30 + .55 * np.clip(1 - xs / .62, 0, 1) ** 1.2 + .25 * np.clip((ys - .7) / .3, 0, 1)     # 왼쪽(글자 쪽)과 아래를 더 어둡게
    k = np.clip(k, 0, .9); c = np.array([6, 12, 10], np.float32)[None, None, :]
    p = PC + 'cover_bg.jpg'; Image.fromarray((a * (1 - k) + c * k).astype(np.uint8)).save(p, quality=90); return p

def _alpha(fill_el, a):                       # srgbClr 에 투명도
    clr = fill_el.find(qn('a:srgbClr')); e = etree.SubElement(clr, qn('a:alpha')); e.set('val', str(int(a * 1000)))
def glow(shape, color, rad_pt, a=45):
    spPr = shape._element.spPr
    eff = spPr.find(qn('a:effectLst'))
    if eff is None: eff = etree.SubElement(spPr, qn('a:effectLst'))
    g = etree.SubElement(eff, qn('a:glow')); g.set('rad', str(int(rad_pt * 12700)))
    c = etree.SubElement(g, qn('a:srgbClr')); c.set('val', color); al = etree.SubElement(c, qn('a:alpha')); al.set('val', str(a * 1000))
def box(s, x, y, w, h, fill=None, falpha=100, line=None, lw=1.0, rad=None, shape=MSO_SHAPE.RECTANGLE):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rad is not None else shape, px(x), px(y), px(w), px(h))
    if rad is not None: sh.adjustments[0] = rad
    if fill: sh.fill.solid(); sh.fill.fore_color.rgb = rgb(fill)
    else: sh.fill.background()
    if fill and falpha < 100: _alpha(sh._element.spPr.find(qn('a:solidFill')), falpha)
    if line: sh.line.color.rgb = rgb(line); sh.line.width = Pt(lw)
    else: sh.line.fill.background()
    sh.shadow.inherit = False
    return sh
def grad_run(run, c1, c2):
    rPr = run._r.get_or_add_rPr()
    for t in ('a:solidFill', 'a:gradFill'):
        e = rPr.find(qn(t))
        if e is not None: rPr.remove(e)
    gf = etree.Element(qn('a:gradFill')); gl = etree.SubElement(gf, qn('a:gsLst'))
    for pos, c in ((0, c1), (100000, c2)):
        gs = etree.SubElement(gl, qn('a:gs')); gs.set('pos', str(pos)); e = etree.SubElement(gs, qn('a:srgbClr')); e.set('val', c)
    lin = etree.SubElement(gf, qn('a:lin')); lin.set('ang', '0'); lin.set('scaled', '0')
    rPr.insert(0, gf)

def step_card(s, x, y, w=244, h=292):
    c = box(s, x, y, w, h, fill=CARD, falpha=90, line=GREEN, lw=1.5, rad=.05); glow(c, '22C55E', 14, 40)
    tb(s, x + 18, y + 12, 90, 46, '04', size=30, color=GREEN, w8='l', anchor='m')
    tb(s, x + w - 118, y + 18, 100, 20, '지금 · 4 / 7', size=9.5, color=MUTE, align='r', anchor='m')
    # 작은 상자 그림: 윤곽 + 네 모서리 나사 (A 완료, B 지금)
    bx, by, bw, bh = x + 62, y + 76, 120, 70
    box(s, bx, by, bw, bh, line='C9D6CF', lw=1.25, rad=.12)
    pts = {'A': (bx + 12, by + 12), 'B': (bx + bw - 12, by + 12), 'C': (bx + 12, by + bh - 12), 'D': (bx + bw - 12, by + bh - 12)}
    for k, (cx, cy) in pts.items():
        if k == 'A':
            box(s, cx - 6, cy - 6, 12, 12, fill=GREEN, shape=MSO_SHAPE.OVAL)
            tb(s, cx - 6, cy - 6, 12, 12, '✓', size=7, color=CARD, w8='x', align='c', anchor='m', wrap=False)
        elif k == 'B':
            r1 = box(s, cx - 12, cy - 12, 24, 24, line=GREEN, lw=1.5, shape=MSO_SHAPE.OVAL); glow(r1, '22C55E', 6, 50)
            box(s, cx - 6, cy - 6, 12, 12, line=GREEN, lw=1.25, shape=MSO_SHAPE.OVAL)
            tb(s, cx - 10, cy - 36, 20, 20, '↓', size=12, color=GREEN, w8='x', align='c', anchor='m', wrap=False)
        else:
            box(s, cx - 6, cy - 6, 12, 12, line='C9D6CF', lw=1.0, shape=MSO_SHAPE.OVAL)
        lx = cx - 26 if k in 'AC' else cx + 14
        tb(s, lx, cy - 8, 12, 16, k, size=8, color=MUTE, align='c', anchor='m', wrap=False)
    tb(s, x + 18, y + 166, w - 36, 18, '나사 B · 2/4', size=9.5, color=GREEN, w8='s', anchor='m')
    tb(s, x + 18, y + 186, w - 36, 28, '나사 B를 조여주세요.', size=16, color=WHITE, w8='x', anchor='m', wrap=False)
    tb(s, x + 18, y + 216, w - 36, 18, '드라이버 끝을 원 안에 맞추면 됩니다.', size=9.5, color='C2CCC6', anchor='m', wrap=False)
    sw = (w - 36 - 12) / 3
    for i, (lab, frac) in enumerate([('접근', 1.0), ('유지 0.8초', .55), ('이탈', 0)]):
        sx = x + 18 + i * (sw + 6)
        box(s, sx, y + 246, sw, 3, fill='33443B')
        if frac: box(s, sx, y + 246, sw * frac, 3, fill=GREEN)
        tb(s, sx, y + 254, sw, 16, lab, size=8, color=GREEN if frac == 1.0 else MUTE, anchor='m', wrap=False)

def lead_line(s, pts, color=GREEN, t=2):          # 가로 · 세로 선만 쓰므로 얇은 사각형으로 그린다 (어느 프로그램에서나 같은 색)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if y1 == y2: box(s, min(x1, x2), y1 - t / 2, abs(x2 - x1) + t / 2, t, fill=color)
        else: box(s, x1 - t / 2, min(y1, y2), t, abs(y2 - y1), fill=color)

def cover_visual(s, bg, G=dict(x=600, y=268, w=620)):
    """배경 + 안경 + 렌즈의 목표 원 + 초록 선 + 04 카드 (표지와 마무리 장이 같이 쓴다)"""
    pic(s, bg, 0, 0, 1280, 720)
    gw = G['w']; gh = gw * 1751 / 2400
    pic(s, PC + 'glasses_rgba.png', G['x'], G['y'], gw, gh)
    # 렌즈 위의 목표 원과 초록 선 → 카드
    rx, ry = G['x'] + .115 * gw, G['y'] + .45 * gh
    CX, CY, CW, CH = 958, 52, 244, 292
    lead_line(s, [(CX, CY + 214), (rx, CY + 214), (rx, ry - 13)])
    r = box(s, rx - 13, ry - 13, 26, 26, line=GREEN, lw=1.75, shape=MSO_SHAPE.OVAL); glow(r, '22C55E', 8, 55)
    box(s, rx - 3, ry - 3, 6, 6, fill=GREEN, shape=MSO_SHAPE.OVAL)
    step_card(s, CX, CY, CW, CH)

def cover_slide(s, bg):
    cover_visual(s, bg)
    # 왼쪽 글
    tb(s, 72, 52, 700, 20, '2026 홍익대학교 컴퓨터공학과 졸업프로젝트 · 인공지능', size=10.5, color='8D9A94', anchor='m')
    tb(s, 72, 178, 520, 30, 'AI Assembly Guide', size=17, color=WHITE, w8='x', anchor='m')
    t = tb(s, 66, 216, 640, 140, [[('다음 작업', {}), ('이', {})], '눈앞에 펼쳐집니다.'], size=50, color=WHITE, w8='l', ls=1.0)
    grad_run(t.text_frame.paragraphs[0].runs[0], '86EFAC', '38D6F0')
    tb(s, 72, 392, 560, 28, '작업 단계 인식 기반 AR 조립 안내 시스템', size=17, color='E2E8E4', w8='s', anchor='m')
    tb(s, 72, 422, 560, 20, 'Procedure-step recognition for AR assembly guidance', size=11, color='8D9A94', anchor='m')
    tb(s, 72, 640, 800, 24, '2026. 11   |   최민준 C011207   |   지도교수 윤영 교수님', size=12.5, color='D9E2DD', w8='m', anchor='m')

if __name__ == '__main__':
    d = Deck(out=W_ + '/scratch/cover_test.pptx')
    for mir in (False, True):
        s = d.new(); cover_slide(s, prep_bg(mirror=mir)); import shutil; shutil.copy(PC + 'cover_bg.jpg', PC + 'cover_bg_%d.jpg' % mir)
    lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
    d.save()

def final_card(s, x, y, w=244, h=292):
    """07 최종 확인 카드: 네 나사 모두 완료"""
    c = box(s, x, y, w, h, fill=CARD, falpha=90, line=GREEN, lw=1.5, rad=.05); glow(c, '22C55E', 14, 40)
    tb(s, x + 18, y + 12, 90, 46, '07', size=30, color=GREEN, w8='l', anchor='m')
    tb(s, x + w - 118, y + 18, 100, 20, '지금 · 7 / 7', size=9.5, color=MUTE, align='r', anchor='m')
    bx, by, bw, bh = x + 62, y + 76, 120, 70
    b = box(s, bx, by, bw, bh, line=GREEN, lw=1.5, rad=.12); glow(b, '22C55E', 6, 45)
    for k, (cx, cy) in {'A': (bx + 12, by + 12), 'B': (bx + bw - 12, by + 12), 'C': (bx + 12, by + bh - 12), 'D': (bx + bw - 12, by + bh - 12)}.items():
        box(s, cx - 6, cy - 6, 12, 12, fill=GREEN, shape=MSO_SHAPE.OVAL)
        tb(s, cx - 6, cy - 6, 12, 12, '✓', size=7, color=CARD, w8='x', align='c', anchor='m', wrap=False)
        lx = cx - 26 if k in 'AC' else cx + 14
        tb(s, lx, cy - 8, 12, 16, k, size=8, color=MUTE, align='c', anchor='m', wrap=False)
    tb(s, x + 18, y + 166, w - 36, 18, '최종 확인', size=9.5, color=GREEN, w8='s', anchor='m')
    tb(s, x + 18, y + 186, w - 36, 28, '조립 상태를 확인해주세요.', size=16, color=WHITE, w8='x', anchor='m', wrap=False)
    tb(s, x + 18, y + 216, w - 36, 18, '나사 A ~ D를 모두 조였습니다.', size=9.5, color='C2CCC6', anchor='m', wrap=False)
    sw = (w - 36 - 12) / 3
    for i, lab in enumerate(['상자 · 뚜껑', '나사 4 / 4', '최종 확인']):
        sx = x + 18 + i * (sw + 6)
        box(s, sx, y + 246, sw, 3, fill=GREEN)
        tb(s, sx, y + 254, sw, 16, lab, size=8, color=GREEN, anchor='m', wrap=False)

def closing_text(s):
    tb(s, 85, 176, 900, 170, ['눈앞에는 다음 작업을,', '관제에는 전체 흐름을.'], size=40, color=WHITE, w8='x', ls=1.22)
    rect(s, 87, 366, 40, 2, fill=GREEN)
    tb(s, 85, 384, 520, 60, ['AI Assembly Guide는 조립 순서를 따라', '작업을 이어가도록 돕습니다.'], size=17, color='D9E2F0', ls=1.4)
    tb(s, 85, 572, 600, 28, 'AI Assembly Guide', size=19, color=WHITE, w8='x', anchor='m')
    tb(s, 85, 602, 900, 22, '작업 단계 인식 기반 AR 조립 안내', size=13, color='D9E2F0', anchor='m')
    tb(s, 85, 634, 900, 22, '개발 최민준 C011207   |   지도교수 윤영 교수님', size=12.5, color='D9E2F0', w8='m', anchor='m')
