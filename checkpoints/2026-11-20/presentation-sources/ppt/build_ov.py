# -*- coding: utf-8 -*-
"""개요(Overview) 장 수정본 두 가지. A: 관제 화면 그림을 빼고 '화면 읽는 법'을 넓게 (관제 화면은 따로 한 장이 생겼으므로).
B: 관제 화면 그림을 새 실행 화면으로 바꿈 (잘리지 않게)."""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
W_ = '/home/claude/grad'; BODY = '333333'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_개요_수정.pptx'
d = Deck(out=OUT)
def arw(s, x, y, color=LBLUE, size=15, h=28, w=26):
    tb(s, x, y, w, h, '→', size=size, color=color, w8='s', align='c', anchor='m', wrap=False)
def overview(variant):
    s = d.new()
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
    for k, (a_, b_) in enumerate([('안경', '현재 나사 강조, 상자 · 뚜껑 윤곽, 지금 할 행동 한 줄'), ('관제 화면', '현재 작업, 다음 행동, 진행 상태')]):
        y = 466 + k * 86
        tb(s, 71, y, 120, 74, a_, size=16.5, color=NAVY, w8='x', anchor='m')
        tb(s, 191, y, 500, 74, b_, size=14.5, color=BODY, anchor='m')
        if k < 1: hline(s, 71, y + 80, 620)
    pic(s, W_ + '/prep_t3/ov.jpg', 725, 106, 484, 272)
    tb(s, 725, 384, 484, 18, '카메라 화면에 안내를 겹친 모습 (시연 영상)', size=9.5, color=LGREY, anchor='m')
    leg = [('청록 선', '상자와 뚜껑의 윤곽'), ('노란 표시', '지금 작업할 나사'), ('A · B · C · D', '나사 네 개의 위치')]
    if variant == 'A':
        rect(s, 725, 428, 484, 206, fill=PALE)
        tb(s, 749, 442, 300, 26, '화면 읽는 법', size=13, color=ORANGE, w8='x', anchor='m')
        for k, (a_, b_) in enumerate(leg):
            y = 480 + k * 48
            tb(s, 749, y, 150, 40, a_, size=15, color=NAVY, w8='x', anchor='m')
            tb(s, 899, y, 290, 40, b_, size=14, color=BODY, anchor='m')
            if k < 2: rect(s, 749, y + 44, 436, 1, fill='D5DCE6')
    else:
        pic(s, W_ + '/prep_c/ctl_live.png', 725, 428, 296, 187)
        tb(s, 725, 619, 296, 16, '관제 화면', size=9.5, color=LGREY, anchor='m')
        rect(s, 1037, 428, 172, 206, fill=PALE)
        tb(s, 1053, 438, 150, 24, '화면 읽는 법', size=12, color=ORANGE, w8='x', anchor='m')
        for k, (a_, b_) in enumerate(leg):
            y = 470 + k * 54
            tb(s, 1053, y, 150, 22, a_, size=13, color=NAVY, w8='x', anchor='m')
            tb(s, 1053, y + 22, 150, 20, b_, size=11.5, color=BODY, anchor='m')
    s.notes_slide.notes_text_frame.text = '[서비스 개요] 참고 영상 2:20~2:46. 대상 → 처리 흐름 → 제공하는 결과.' + (' (A안: 관제 화면 그림은 따로 만든 관제 화면 장으로 옮김)' if variant == 'A' else ' (B안: 관제 화면 그림을 새 실행 화면으로 바꿈)')
    return s
overview('A'); overview('B')
lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
d.save()
