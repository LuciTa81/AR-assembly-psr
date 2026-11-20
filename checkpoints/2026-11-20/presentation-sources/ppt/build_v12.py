# -*- coding: utf-8 -*-
"""v11 → v12: 표지(1장)를 전시 포스터 구성으로 바꾼다 (cover_v12.py). 메모의 사진 줄만 갱신."""
import sys
sys.path.insert(0, '/home/claude/grad')
from cover_v12 import *
from pptx import Presentation
SRC = W_ + '/out/AI Assembly Guide_구조테스트_v11.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v12.pptx'
prs = Presentation(SRC); S = list(prs.slides); assert len(S) == 20
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
def drop(s, sh):
    rids = [b.get(R_NS + 'embed') for b in sh._element.iter(A_NS + 'blip')]
    sh._element.getparent().remove(sh._element)
    for rid in rids:
        if rid and rid not in s.shapes._spTree.xml: s.part.drop_rel(rid)
s = S[0]; assert any(sh.has_text_frame and 'AI Assembly Guide' in sh.text_frame.text for sh in s.shapes)
for sh in list(s.shapes): drop(s, sh)
cover_slide(s, prep_bg(mirror=True))
for sh in s.shapes:
    if sh.has_text_frame:
        for p_ in sh.text_frame.paragraphs:
            pPr = p_._p.get_or_add_pPr(); pPr.set('eaLnBrk', '0'); pPr.set('latinLnBrk', '0')
s.notes_slide.notes_text_frame.text = ('[표지] 참고 영상 0:01 인사에 해당. 전시 포스터(AI Assembly Guide.pdf)의 구성을 16:9로 옮겼다. '
                                       '배경과 안경 이미지는 포스터에서 그대로 가져왔고(안경은 VITURE 제품 이미지, 배경은 좌우를 뒤집음), 04 단계 카드와 초록 선은 도형으로 다시 그려 고칠 수 있다.')
m = S[19]
hit = [sh for sh in m.shapes if sh.has_text_frame and sh.text_frame.text.startswith('· 화면에서 뺀 단서')]; assert len(hit) == 1
for p_ in hit[0].text_frame.paragraphs:
    if p_.text.startswith('· 사진:'):
        t = p_.text.replace('표지의 안경은 VITURE 제품 이미지', '표지는 전시 포스터의 배경과 안경(VITURE 제품 이미지)'); assert t != p_.text
        p_.runs[0].text = t
        for x in p_.runs[1:]: x._r.getparent().remove(x._r)
prs.save(OUT); print('saved', OUT, len(prs.slides))
