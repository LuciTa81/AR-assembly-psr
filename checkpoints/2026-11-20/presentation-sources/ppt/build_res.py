# -*- coding: utf-8 -*-
"""성과 두 장을 다시 만든다 (따로 주는 2장 파일).
1 Evaluation : 세 문제마다 '처음 → 지금'. 그림 + 큰 숫자 + 조건.
2 Results    : 시연 네 장면 + 큰 숫자 넷, 아래는 기대효과.
그림은 assets_res.py 가 만든다."""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip
W_ = '/home/claude/grad'; PR = W_ + '/prep_r/'; BODY = '333333'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_성과_두장.pptx'
def arw(s, x, y, color=LBLUE, size=15, h=28, w=26): tb(s, x, y, w, h, '→', size=size, color=color, w8='s', align='c', anchor='m', wrap=False)
d = Deck(out=OUT)

# ================================================================== 1 Evaluation
s = d.new()
header(s, 'Evaluation', '세 문제가 풀렸는지, 숫자와 기록으로 확인했습니다')
CW = 368; VY = 136; VH = 190
cols = [dict(k='문제 1 · 단계 인식', was='첫 결과는 정확도 61.3%', big='94.1%', lab='단계 인식 정확도',
             sub='119프레임 중 틀린 프레임 46 → 7', cond='1학기 · session 17 · 정답 라벨과 비교'),
        dict(k='문제 2 · 양안 정합', was='카메라에서 맞는 위치가 안경에서는 어긋남', big='4 / 4', lab='나사 네 개가 실물 위에 하나로',
             sub='거리와 시점을 바꿔도 대체로 겹침 유지', cond='2026. 11. 14 · 같은 착용 상태 · 착용자 확인',
             img='ev_fit.jpg', tag='안내 윤곽이 실물과 겹침'),
        dict(k='문제 3 · 가림과 복구', was='손이 마커를 가리면 처음부터 다시 시작', big='10 / 10', lab='가려진 뒤 하던 단계에서 계속',
             sub='가장 길게는 6초 동안 가려져도 이어 감', cond='take4 시연 · 2분 1초 · Unity 화면 기준',
             img='ev_rec.jpg', tag='손이 마커를 가린 순간')]
for k, c in enumerate(cols):
    x = 71 + k * 385
    hline(s, x, 100, CW, color=NAVY, lw=1.25)
    tb(s, x, 108, CW, 22, c['k'], size=12, color=ORANGE, w8='x', anchor='m')
    if 'img' in c:
        pic(s, PR + c['img'], x, VY, CW, VH)
        chip(s, x + 8, VY + 8, c['tag'], fill=WHITE, color=NAVY, size=9.5, h=22, w8='x')
    else:                                                        # 정확도 막대: 0에서 시작, 마지막만 네이비
        rect(s, x, VY, CW, VH, fill=PALE)
        BASE = VY + 138; MAXH = 104; BW = 76
        data = [(61.3, '5월 첫 결과', '틀린 프레임 46'), (87.4, '파라미터 탐색 뒤', '틀린 프레임 15'), (94.1, '6월 최종', '틀린 프레임 7')]
        for j, (v, a_, b_) in enumerate(data):
            bx = x + 26 + j * 120; h = MAXH * v / 100; last = j == 2
            rect(s, bx, BASE - h, BW, h, fill=NAVY if last else LBLUE)
            tb(s, bx - 22, BASE - h - 30, BW + 44, 26, '%.1f%%' % v, size=17 if last else 13, color=NAVY if last else GREY, w8='x', align='c', anchor='b', wrap=False)
            tb(s, bx - 22, BASE + 7, BW + 44, 18, a_, size=10.5, color=TXT, w8='s', align='c', anchor='m', wrap=False)
            tb(s, bx - 22, BASE + 26, BW + 44, 16, b_, size=9.5, color=GREY, align='c', anchor='m', wrap=False)
            if j < 2: arw(s, bx + BW + 9, BASE - 62, color=GREY, size=12)
        hline(s, x + 14, BASE, CW - 28, color=LGREY)
    y = VY + VH + 12
    chip(s, x, y + 1, '처음', fill=PALE, color=GREY, size=9.5, w=42, h=20, w8='s')
    tb(s, x + 52, y, CW - 52, 22, c['was'], size=12, color=GREY, anchor='m', wrap=False)
    chip(s, x, y + 47, '지금', fill=NAVY, color=WHITE, size=9.5, w=42, h=20, w8='s')
    tb(s, x + 52, y + 26, CW - 52, 60, c['big'], size=40, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, y + 90, CW, 26, c['lab'], size=15, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, y + 116, CW, 22, c['sub'], size=12, color=BODY, anchor='m', wrap=False)
    tb(s, x, y + 140, CW, 18, c['cond'], size=9.5, color=LGREY, anchor='m', wrap=False)
tb(s, 71, 520, 400, 24, '사용하면서 고친 것', size=13, color=ORANGE, w8='x', anchor='m')
hline(s, 71, 548, 1138, color=NAVY, lw=1.25)
ut = [('상태 설명이 많아 지금 할 일을 찾기 어려움', '큰 행동 문구 한 줄과 목표 강조로 정리'), ('영문 상태 문구가 낯섦', '한글 행동 문구로 변경')]
for k, (a_, b_) in enumerate(ut):
    y = 549 + k * 45
    tb(s, 87, y, 520, 45, a_, size=13.5, color=BODY, anchor='m')
    arw(s, 615, y + 8.5, color=NAVY, size=13)
    tb(s, 655, y, 540, 45, b_, size=13.5, color=NAVY, w8='x', anchor='m')
    hline(s, 71, y + 45, 1138)
s.notes_slide.notes_text_frame.text = (
    '[검증 결과] 8장의 세 문제에 하나씩 답한다. 문제마다 "처음에는 이랬고, 지금은 이렇다"로 말한다.\n'
    '문제 1: 같은 119프레임에서 HMM 정확도가 61.3%(73/119) → 87.4%(104/119) → 94.1%(112/119). 틀린 프레임은 46 → 15 → 7. '
    '앞의 두 값은 5월 발표 자료의 Before / After(grid search), 마지막 값은 6월 최종 보고서의 session 17 결과다. '
    '참고로 최종 보고서 기준 프레임별 판단은 88.2%, FSM은 91.6%.\n'
    '문제 2: 2026년 11월 14일 같은 착용 상태에서, 거리(가까이 ↔ 기준 거리)와 시점(작은 측면 이동 → 정면 복귀)을 바꿔 가며 나사 A ~ D를 착용자가 눈으로 확인했다. '
    '거리에서는 "대체로 하나로 겹침", 시점에서는 "겹침 유지". 가운데 그림은 작업대 사진에 Unity 왼눈 화면을 맞춰 얹은 재현이며, 안경 렌즈를 통해 찍은 사진이 아니다.\n'
    '문제 3: take4 시연(2분 1초)을 Unity 화면에서 0.1초 단위로 쟀다. 1초 넘게 가려진 구간 10번, 가장 긴 구간 6.0초, 10번 모두 하던 단계에서 이어 갔고 단계가 뒤로 간 적은 없다.\n'
    '화면에서 뺀 단서: 세 결과는 조건이 다르다(오프라인 한 세션 · 시연 한 번 · 착용자 확인). 파라미터 탐색과 평가에 같은 세션을 썼는지 확인이 필요하다. '
    '여러 사람 · 여러 번의 반복 성공률, 실물 기준 위치 오차(mm), 지연 시간은 아직 재지 못했다. 가려진 시간은 모두 38.3초다. 질문이 나오면 그대로 답한다.')

# ================================================================== 2 Results
s = d.new()
header(s, 'Results', '안경의 안내만 따라가며 상자 하나를 끝까지 조립했습니다')
FW = 264; FH = 148.5; STEP = (1138 - FW) / 3
film = [('film_2.jpg', '0:02', '상자 배치', '상자를 놓아주세요'), ('film_25.jpg', '0:25', '뚜껑 닫기', '뚜껑을 덮어주세요'),
        ('film_46.jpg', '0:46', '나사 A ~ D', '나사 A를 조여주세요'), ('film_120_5.jpg', '2:01', '최종 확인', '조립 상태를 확인해주세요')]
for k, (im, t_, a_, b_) in enumerate(film):
    x = 71 + k * STEP
    pic(s, PR + im, x, 100, FW, FH)
    if k < 3: arw(s, x + FW + (STEP - FW - 26) / 2, 100 + FH / 2 - 14, color=NAVY, size=13)
    tb(s, x, 255, FW, 22, [[(t_, {'color': NAVY, 'w': 'x'}), ('   ' + a_, {})]], size=12.5, color=TXT, w8='s', anchor='m', wrap=False)
    tb(s, x, 277, FW, 18, '안경 안내 · ' + b_, size=10, color=GREY, anchor='m', wrap=False)
stats = [('2분 1초', '상자 하나를 처음부터 끝까지'), ('7단계', '빠짐없이 순서대로 안내'), ('4 / 4', '버튼 없이 다음 나사로 넘어감'), ('0번', '가려져서 처음으로 돌아간 횟수')]
for k, (b_, l_) in enumerate(stats):
    x = 71 + k * STEP
    hline(s, x, 306, FW, color=NAVY, lw=1.25)
    tb(s, x, 311, FW, 46, b_, size=30, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, 357, FW, 22, l_, size=12, color=BODY, anchor='m', wrap=False)
PY = 394; PH = 240
rect(s, 71, PY, 1138, PH, fill=PALE)
tb(s, 95, PY + 12, 120, 24, '기대효과', size=13, color=ORANGE, w8='x', anchor='m')
tb(s, 95, PY + 37, 1090, 34, '설명서와 옆 사람 대신, 안경이 다음 할 일을 알려 줍니다', size=19, color=NAVY, w8='x', anchor='m', wrap=False)
hline(s, 95, PY + 82, 1090, color=LBLUE)
fx = [('작업자', '설명서 없이', '시선과 두 손이 작업대를 떠나지 않아 작업 흐름이 끊기지 않습니다.'),
      ('처음 하는 사람', '외우지 않고', '다음 행동이 눈앞에 보여, 순서를 익히는 시간과 실수를 줄일 수 있습니다.'),
      ('관리자', '떨어져서도', '관제 화면에 진행 상황이 보여, 자리를 지키지 않아도 확인할 수 있습니다.'),
      ('현장', '다른 작업에도', '위치는 마커로, 단계는 도구의 움직임으로 판단해 다른 조립 · 정비에도 옮길 수 있습니다.')]
for k, (who, t_, d_) in enumerate(fx):
    x = 95 + k * 277
    if k: rect(s, x - 20, PY + 98, 0.8, 124, fill=LBLUE)
    chip(s, x, PY + 96, who, fill=TINT, color=NAVY, size=9.5, h=20, w8='s')
    tb(s, x, PY + 121, 240, 30, t_, size=17, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, PY + 155, 244, 66, d_, size=11.5, color=BODY, ls=1.4)
src(s, '시연 수치는 take4 한 번의 기록입니다 (2분 1초 · Unity 화면 기준)', y=664)
s.notes_slide.notes_text_frame.text = (
    '[성과와 기대효과] 위는 한 일, 아래는 그 일이 주는 것.\n'
    '위: take4 시연에서 안경의 안내를 따라 상자 배치 → 뚜껑 닫기 → 나사 A ~ D → 최종 확인까지 일곱 단계를 2분 1초에 진행했다. '
    '나사 네 개는 버튼을 누르지 않고 다음 나사로 넘어갔고, 손이 마커를 가려도 처음으로 돌아가지 않았다. 네 장면은 15장 영상의 0:02, 0:25, 0:46, 2:01이다(영상은 카메라 화면에 안경의 안내 글자를 합성한 재현).\n'
    '아래: 기대효과는 측정한 값이 아니라 이 구조에서 기대하는 것이다. 작업자(설명서를 오가지 않음), 처음 하는 사람(순서를 외우지 않음), 관리자(관제 화면으로 확인), 현장(다른 작업으로 확장) 순서로 말한다.\n'
    '화면에서 뺀 단서: 촬영용 설정이라 초록 안내 2초 뒤 자동으로 넘어간다. 조임 품질(토크)은 재지 않는다. 상자 배치 · 뚜껑 닫기 · 최종 확인은 작업자가 확인하고 넘어간다. '
    '여러 사람 · 여러 조건에서의 반복 평가와 다른 작업대 · 부품으로의 확장은 다음 단계다. 다른 대상으로 옮기려면 마커 배치, 부품 위치 등록, 도구 검출 데이터가 새로 필요하다. 질문이 나오면 그대로 답한다.')

lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
d.save()
