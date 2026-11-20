# -*- coding: utf-8 -*-
"""양안 투영 장 초안 (한 장). 그림은 stereo_assets.py 가 만든다."""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip
W_ = '/home/claude/grad'; PR = W_ + '/prep_s/'; BODY = '333333'; BLACK = '0B0F14'
def stereo_slide(d):
    s = d.new()
    header(s, 'Stereo Projection', '같은 나사를 왼눈과 오른눈에 따로 계산해 그립니다')
    pic(s, PR + 'comp.jpg', 71, 104, 520, 292.5)
    chip(s, 81, 114, '재현 이미지', fill=BLACK, color=WHITE, size=9.5, w=86, h=22)
    tb(s, 71, 402, 520, 18, '작업대 사진에 Unity 왼눈 화면을 맞춰 얹은 재현입니다. 안경 렌즈를 통해 찍은 사진은 아닙니다.', size=9.5, color=LGREY, anchor='m')
    tb(s, 624, 104, 300, 24, '실시간 처리', size=13, color=ORANGE, w8='x', anchor='m')
    steps = [('마커 자세 추정', 'ArUco 검출과 PnP로 작업대에 대한 카메라의 위치와 방향을 구합니다.'),
             ('나사의 3D 좌표', '등록한 나사 A ~ D의 위치를 카메라 기준 좌표로 바꿉니다.'),
             ('눈별 투영', '화면 좌표 x = P · X 를 눈마다 따로 계산합니다 (P: 눈별 3×4 투영 행렬).'),
             ('Full SBS 출력', 'Unity가 서로 다른 좌우 화면을 나란히 안경으로 보냅니다.')]
    for k, (a_, b_) in enumerate(steps):
        y = 136 + k * 67
        rect(s, 624, y, 585, 58, fill=PALE)
        if k == 2: rect(s, 624, y, 4, 58, fill=NAVY)
        tb(s, 640, y, 44, 58, '0%d' % (k + 1), size=15, color=NAVY if k == 2 else LBLUE, w8='x', anchor='m')
        tb(s, 690, y + 7, 500, 24, a_, size=15, color=NAVY, w8='x', anchor='m')
        tb(s, 690, y + 31, 510, 20, b_, size=11.5, color=BODY, anchor='m')
    tb(s, 624, 402, 585, 22, '보정값은 미리 구하고, 표시 위치는 움직일 때마다 다시 계산합니다.', size=12.5, color=NAVY, w8='x', anchor='m')
    hline(s, 71, 436, 1138)
    tb(s, 71, 444, 500, 24, '안경에 실제로 들어가는 화면', size=13, color=ORANGE, w8='x', anchor='m')
    for k, (im, lab, w) in enumerate([('eyeL.png', '왼눈', 50), ('eyeR.png', '오른눈', 60), ('overlap.png', '겹쳐 보기', 76)]):
        x = 71 + k * 316
        pic(s, PR + im, x, 474, 300, 168.75)
        chip(s, x + 8, 612, lab, fill=WHITE, color=NAVY, size=10, w=w, h=22, w8='x')
    X = 71 + 2 * 316                                      # 겹쳐 보기 위의 표시 (윤곽 왼쪽 끝: 왼눈 913, 오른눈 574 / 1920)
    xa, xb = X + 574 * 300 / 1920, X + 913 * 300 / 1920
    rect(s, xa, 574, xb - xa, 2, fill=WHITE); rect(s, xa, 569, 2, 12, fill=WHITE); rect(s, xb - 2, 569, 2, 12, fill=WHITE)
    tb(s, xb + 8, 564, 140, 22, '눈마다 다른 위치', size=10, color=WHITE, w8='s', anchor='m', wrap=False)
    tb(s, 1035, 474, 174, 22, '두 화면을 겹치면', size=12.5, color=ORANGE, w8='x', anchor='m')
    for k, (a_, b_) in enumerate([('윤곽 · 나사 표시', '눈마다 다른 자리'), ('안내 글자', '두 눈에 같은 자리')]):
        y = 502 + k * 50
        tb(s, 1035, y, 174, 22, a_, size=13, color=NAVY, w8='x', anchor='m')
        tb(s, 1035, y + 22, 174, 20, b_, size=11.5, color=BODY, anchor='m')
    tb(s, 1035, 604, 174, 40, '그래서 실물의 깊이에 맞춰 하나로 겹쳐 보입니다.', size=11.5, color=NAVY, w8='s', ls=1.35)
    src(s, '아래 세 그림은 Unity 양안 출력의 같은 순간입니다 (선은 보기 쉽게 굵게 처리)', y=664)
    return s
if __name__ == '__main__':
    d = Deck(out=W_ + '/out/stereo_draft.pptx'); stereo_slide(d)
    lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first); d.save()
