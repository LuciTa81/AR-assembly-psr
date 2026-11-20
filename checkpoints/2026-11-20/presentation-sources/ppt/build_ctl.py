# -*- coding: utf-8 -*-
"""관제 화면 한 장: 왼쪽 실행 화면, 오른쪽 메뉴 설명. 화면 그림은 사용자가 보낸 슬라이드 캡처에서 잘라 낸 것(prep_c/ctl_live.png)."""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip
W_ = '/home/claude/grad'; BODY = '333333'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_관제화면_메뉴설명.pptx'
d = Deck(out=OUT)
s = d.new()
header(s, 'Overview', '관제 화면 하나로 연결부터 작업 진행까지 확인합니다')
SX, SY, SW = 71, 106, 800; K = SW / 1024; SH = 647 * K
pic(s, W_ + '/prep_c/ctl_live.png', SX, SY, SW, SH)
r = rect(s, SX + 134 * K, SY + 3 * K, (462 - 134) * K, 37 * K, line=ORANGE, lw=1.5, shape=MSO_SHAPE.ROUNDED_RECTANGLE); r.adjustments[0] = .18   # 화면 위쪽 메뉴 줄
tb(s, SX, SY + SH + 6, SW, 18, '실시간 관제 화면 · 상자 배치 단계', size=9.5, color=LGREY, anchor='m')
PX, PW = 895, 314
rect(s, PX, SY, PW, SH, fill=PALE)
tb(s, PX + 22, SY + 12, 200, 24, '화면 위쪽 메뉴', size=13, color=ORANGE, w8='x', anchor='m')
menus = [('실시간 관제', '작업대 영상과 현재 작업, 다음 행동을 한 화면에서 봅니다. 작업 시작과 종료도 여기서 합니다.'),
         ('작업 기록', '지난 작업이 단계별로 어떻게 진행됐는지 다시 확인합니다.'),
         ('연결 · 진단', '안경 카메라와 화면 연결을 확인하고, 추적이 끊긴 이유를 살펴봅니다.'),
         ('설정', '화면 표시 방식 같은 실행 설정을 바꿉니다.')]
YS = [SY + 48, SY + 184, SY + 293, SY + 402]                     # 첫 항목은 세 줄이라 조금 더 띄운다
for k, (a_, b_) in enumerate(menus):
    y = YS[k]
    tb(s, PX + 22, y, 180, 28, a_, size=16.5, color=NAVY, w8='x', anchor='m')
    if k == 0: chip(s, PX + 22 + 128, y + 4, '지금 화면', fill=NAVY, color=WHITE, size=9.5, w=66, h=20, w8='x')
    tb(s, PX + 22, y + 32, PW - 40, 74, b_, size=12.5, color=BODY, ls=1.4)
    if k < 3: rect(s, PX + 22, YS[k + 1] - 12, PW - 44, 1, fill='D5DCE6')
lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
s.notes_slide.notes_text_frame.text = ('[관제 화면] 왼쪽은 실행 중인 실시간 관제 화면(상자 배치 단계). 주황 테두리가 화면 위쪽 메뉴다. '
    '실시간 관제 설명은 이 화면에 보이는 내용 그대로다. 작업 기록 · 연결·진단 · 설정의 설명은 메뉴 이름과 준비 화면, 구성안을 바탕으로 쓴 것이라 실제 화면과 맞는지 확인이 필요하다.')
d.save()
