# -*- coding: utf-8 -*-
"""5장(Problem)만 한 장으로. 사진 3장을 밝은 톤의 Unsplash 사진으로 교체."""
import sys, os, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import numcircle
from PIL import Image
W_ = '/home/claude/grad'; P = W_ + '/photo/'; PR = W_ + '/prep_p5/'; os.makedirs(PR, exist_ok=True)
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_5장_Problem_사진교체.pptx'
BODY = '333333'
def cover(src, w, h, fx=.5, fy=.5, scale=2):
    im = Image.open(src).convert('RGB'); Wd, Hd = int(w * scale), int(h * scale)
    r = max(Wd / im.width, Hd / im.height); im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x = int((im.width - Wd) * fx); y = int((im.height - Hd) * fy); return im.crop((x, y, x + Wd, y + Hd))
SRC = [('shaikhulud-assemble_manual.jpg', .5, .62), ('imattsmart-robotkit.jpg', .5, .5), ('oppofindx5pro-floor_manual.jpg', .5, .62)]
if len(sys.argv) > 2: SRC = eval(sys.argv[2])
IMG = []
for k, (f, fx, fy) in enumerate(SRC):
    p = PR + 'a%d.jpg' % k; cover(P + f, 368, 230, fx, fy).save(p, quality=90); IMG.append(p)
d = Deck(out=OUT)
s = d.new()
header(s, 'Problem', '조립이 익숙하지 않은 작업자를 위해 만들었습니다')
lead(s, '조립 초보자와 실습자는 설명서를 반복해서 확인하고, 순서를 헷갈리기 쉽습니다.', y=96, h=30)
caps = [('설명서를 봅니다', '그림과 부품을 번갈아 확인합니다.'), ('부품을 맞춥니다', '손이 멈추면 순서를 다시 찾습니다.'), ('다시 설명서로 돌아갑니다', '어디까지 했는지 헷갈리기 쉽습니다.')]
for k, (a_, b_) in enumerate(caps):
    x = 71 + k * 385
    pic(s, IMG[k], x, 140, 368, 230)
    rect(s, x, 370, 368, 4, fill=NAVY)
    numcircle(s, x, 388, k + 1, d=26, size=11.5)
    tb(s, x + 36, 386, 330, 30, a_, size=16, color=NAVY, w8='x', anchor='m')
    tb(s, x + 36, 418, 330, 24, b_, size=12, color=BODY, anchor='m')
hline(s, 71, 476, 1138); hline(s, 71, 606, 1138)          # 남색으로 채우지 않고 가는 선만
rect(s, 640, 498, 1, 86, fill=LINE)
for k, (a_, b_) in enumerate([('설명서를 보며 작업하면', '시선이 설명서와 작업대를 오갑니다.'), ('AR 안내로 작업하면', '작업 위치에서 다음 행동을 확인합니다.')]):
    x = 71 + k * 599
    tb(s, x, 494, 500, 24, a_, size=12.5, color=ORANGE if k else GREY, w8='x', anchor='m')
    tb(s, x, 524, 530, 56, b_, size=21, color=NAVY if k else '5B6570', w8='x', anchor='m')
tb(s, 71, 692, 900, 18, sys.argv[3] if len(sys.argv) > 3 else 'Photo: @shaikhulud, iMattSmart, @oppofindx5pro / Unsplash', size=8, color=LGREY)
lst = d.prs.slides._sldIdLst; first = lst[0]; d.prs.part.drop_rel(first.rId); lst.remove(first)
d.save()
