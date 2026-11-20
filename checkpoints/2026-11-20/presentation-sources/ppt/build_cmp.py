# -*- coding: utf-8 -*-
"""비교(Comparison) 장 다시 디자인: 방식마다 사진을 머리에 두고, 우리 열만 강조. 1장 = 태블릿 사진, 2장 = 작업실 모니터 사진."""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from PIL import Image
W_ = '/home/claude/grad'; P = W_ + '/photo/'; PRC = W_ + '/prep_c/'; BODY = '333333'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_비교_디자인.pptx'
def cover(src, w, h, fx=.5, fy=.5, scale=2, box=None):
    im = Image.open(src).convert('RGB')
    if box: im = im.crop(box)
    Wd, Hd = int(w * scale), int(h * scale); r = max(Wd / im.width, Hd / im.height)
    im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x = int((im.width - Wd) * fx); y = int((im.height - Hd) * fy); return im.crop((x, y, x + Wd, y + Hd))
CW, CW3, PH = 290, 348, 152                     # 앞 두 열 / 우리 열 / 사진 높이
cover(P + 'shaikhulud-assemble_manual.jpg', CW, PH, fy=.62).save(PRC + 'cmp_paper.jpg', quality=90)
cover(P + 'tomspentys-tablet_point.jpg', CW, PH, fy=.55).save(PRC + 'cmp_tab1.jpg', quality=90)
cover(P + 'snapmaker_official-workshop_monitor.jpg', CW, PH, fy=.72).save(PRC + 'cmp_tab2.jpg', quality=90)
cover(W_ + '/prep_t6/demo_poster.jpg', CW3, PH, box=(130, 40, 1150, 486)).save(PRC + 'cmp_ours.jpg', quality=90)
d = Deck(out=OUT)
def comparison(tab):
    s = d.new()
    header(s, 'Comparison', '안내가 보이는 곳과 단계를 넘기는 방법이 다릅니다')
    X = [265, 563, 861]; WS = [CW, CW, CW3]; Y0 = 104; TY = Y0 + PH; RY = TY + 50; RH = 64
    # 우리 열의 바탕
    rect(s, X[2], TY, CW3, 50 + 4 * RH, fill=PALE); rect(s, X[2], Y0 - 4, CW3, 4, fill=NAVY)
    for k, im in enumerate(['cmp_paper.jpg', tab, 'cmp_ours.jpg']): pic(s, PRC + im, X[k], Y0, WS[k], PH)
    tb(s, 71, Y0 + 8, 196, 22, '비교', size=13, color=ORANGE, w8='x', anchor='m')
    tb(s, 71, Y0 + 38, 190, 80, ['같은 조립,', '세 가지 안내 방식'], size=18, color=NAVY, w8='x', ls=1.28)
    tb(s, 79, TY, 176, 50, '구분', size=12, color=GREY, w8='x', anchor='m')
    tb(s, X[0] + 16, TY, CW - 28, 50, '종이 설명서', size=15.5, color=TXT, w8='x', anchor='m')
    tb(s, X[1] + 16, TY, 96, 50, '화면 설명서', size=15.5, color=TXT, w8='x', anchor='m', wrap=False)
    tb(s, X[1] + 118, TY, 160, 50, '태블릿 · 영상', size=11.5, color=GREY, anchor='m', wrap=False)
    tb(s, X[2] + 16, TY, CW3 - 28, 50, 'AI Assembly Guide', size=17, color=NAVY, w8='x', anchor='m')
    hline(s, 71, RY, 1138, color=NAVY, lw=1.25)
    trs = [('안내가 보이는 곳', '책상 위 설명서', '옆에 둔 화면', '작업 위치 위 (AR 안경)'),
           ('다음 단계로 넘어가기', '직접 페이지를 넘김', '직접 누르거나 재생', '나사 A ~ D는 AI 관측으로 자동 전환'),
           ('작업 중 시선', '설명서와 작업대를 오감', '화면과 작업대를 오감', '작업대에 머묾, 시각적 피드백 명확'),
           ('진행 상황 확인', '작업자가 이해하고 기억해야 함', '작업자가 매번 파악', '관제 화면에 현재 단계와 다음 행동 표시')]
    for r, row in enumerate(trs):
        y = RY + r * RH
        tb(s, 79, y, 182, RH, row[0], size=15, color=NAVY, w8='x', anchor='m', wrap=False)
        tb(s, X[0] + 16, y, CW - 28, RH, row[1], size=13.5, color=BODY, anchor='m')
        tb(s, X[1] + 16, y, CW - 28, RH, row[2], size=13.5, color=BODY, anchor='m')
        tb(s, X[2] + 16, y, CW3 - 24, RH, row[3], size=14, color=NAVY, w8='x', anchor='m')
        hline(s, 71, y + RH, 1138)
    Y2 = RY + 4 * RH + 22
    hline(s, 71, Y2, 1138); hline(s, 71, Y2 + 62, 1138)
    tb(s, 71, Y2, 170, 62, '핵심 차별점', size=13, color=ORANGE, w8='x', anchor='m')
    tb(s, 240, Y2, 960, 62, '위치는 마커로, 단계는 도구의 움직임으로 판단해 작업 위치에 바로 안내합니다.', size=18, color=NAVY, w8='x', anchor='m')
    credit = '@tomspentys' if tab == 'cmp_tab1.jpg' else '@snapmaker_official'
    s.notes_slide.notes_text_frame.text = '[기존 방식과 비교] 사진: 종이 설명서 Unsplash @shaikhulud, 화면 설명서 Unsplash %s, 오른쪽은 시연 영상의 한 장면(재현 영상). 표의 문구는 초안이며 근거 자료는 없다.' % credit
    return s
comparison('cmp_tab1.jpg'); comparison('cmp_tab2.jpg')
lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
d.save()
