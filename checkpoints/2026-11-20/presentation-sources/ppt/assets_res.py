# -*- coding: utf-8 -*-
"""성과 두 장(Evaluation, Results)의 그림.
film_*.jpg  : 합성 영상(06)의 네 장면, 화면 전체 (안내 글자가 잘리지 않게)
ev_fit.jpg  : 실물 상자 위에 겹친 안내 윤곽 (작업대 사진 + Unity 왼눈 화면 재현)
ev_rec.jpg  : 손이 마커를 가린 순간 (합성 영상 0:30 ~ 0:38 구간)
정확도 막대는 그림이 아니라 장 위에 도형으로 직접 그린다 (build_res.py)."""
from PIL import Image
W_ = '/home/claude/grad'; OUT = W_ + '/prep_r/'
def cover(src, w, h, box=None, scale=2):
    m = Image.open(src).convert('RGB')
    if box: m = m.crop(box)
    Wd, Hd = int(round(w * scale)), int(round(h * scale)); r = max(Wd / m.width, Hd / m.height)
    m = m.resize((int(m.width * r + .5), int(m.height * r + .5)), Image.LANCZOS)
    x = (m.width - Wd) // 2; y = (m.height - Hd) // 2; return m.crop((x, y, x + Wd, y + Hd))
for t in ('2', '25', '46', '120.5'):
    cover(OUT + 'f_%s.jpg' % t, 264, 148.5).save(OUT + 'film_%s.jpg' % t.replace('.', '_'), quality=92)
cover(W_ + '/prep_s/comp.jpg', 368, 190, box=(38, 0, 1491, 750)).save(OUT + 'ev_fit.jpg', quality=92)
cover(W_ + '/prep_t6/rec_poster.jpg', 368, 190, box=(0, 22, 960, 518)).save(OUT + 'ev_rec.jpg', quality=92)
print('ok')
