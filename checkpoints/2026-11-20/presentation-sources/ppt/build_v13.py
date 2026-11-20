# -*- coding: utf-8 -*-
"""v12 → v13: 마무리 장(19장)을 표지와 같은 배경 · 안경 · 04 카드로. 글(멘트)은 원래 것을 같은 자리 · 같은 크기로 둔다."""
import sys
sys.path.insert(0, '/home/claude/grad')
from cover_v12 import *
from pptx import Presentation
SRC = W_ + '/out/AI Assembly Guide_구조테스트_v12.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v13.pptx'
prs = Presentation(SRC); S = list(prs.slides); assert len(S) == 20
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
def drop(s, sh):
    rids = [b.get(R_NS + 'embed') for b in sh._element.iter(A_NS + 'blip')]
    sh._element.getparent().remove(sh._element)
    for rid in rids:
        if rid and rid not in s.shapes._spTree.xml: s.part.drop_rel(rid)
s = S[18]
texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
assert texts == ['눈앞에는 다음 작업을,\n관제에는 전체 흐름을.', 'AI Assembly Guide는 조립 순서를 따라\n작업을 이어가도록 돕습니다.', 'AI Assembly Guide', '작업 단계 인식 기반 AR 조립 안내', '개발 최민준 C011207   |   지도교수 윤영 교수님'], texts
for sh in list(s.shapes): drop(s, sh)
cover_visual(s, PC + 'cover_bg.jpg')
tb(s, 85, 176, 900, 170, ['눈앞에는 다음 작업을,', '관제에는 전체 흐름을.'], size=40, color=WHITE, w8='x', ls=1.22)
rect(s, 87, 366, 40, 2, fill=GREEN)
tb(s, 85, 384, 520, 60, ['AI Assembly Guide는 조립 순서를 따라', '작업을 이어가도록 돕습니다.'], size=17, color='D9E2F0', ls=1.4)
tb(s, 85, 572, 600, 28, 'AI Assembly Guide', size=19, color=WHITE, w8='x', anchor='m')
tb(s, 85, 602, 900, 22, '작업 단계 인식 기반 AR 조립 안내', size=13, color='D9E2F0', anchor='m')
tb(s, 85, 634, 900, 22, '개발 최민준 C011207   |   지도교수 윤영 교수님', size=12.5, color='D9E2F0', w8='m', anchor='m')
for sh in s.shapes:
    if sh.has_text_frame:
        for p_ in sh.text_frame.paragraphs:
            pPr = p_._p.get_or_add_pPr(); pPr.set('eaLnBrk', '0'); pPr.set('latinLnBrk', '0')
s.notes_slide.notes_text_frame.text = '[마무리] 참고 영상 10:16. 표지와 같은 배경 · 안경 · 04 카드로 처음과 끝을 맞췄다(포스터에서 가져온 이미지, 안경은 VITURE 제품 이미지). 글은 원래 마무리 문구 그대로.'
m = S[19]
def retext(start, new):
    hit = [sh for sh in m.shapes if sh.has_text_frame and sh.text_frame.text.strip().startswith(start)]; assert len(hit) == 1, start
    r = hit[0].text_frame.paragraphs[0].runs; r[0].text = new
    for x in r[1:]: x._r.getparent().remove(x._r)
retext('v10: 배경 사진 교체', 'v13: 표지와 같은 배경 · 안경 · 04 카드로 바꿈. 글은 그대로')
hit = [sh for sh in m.shapes if sh.has_text_frame and sh.text_frame.text.startswith('· 화면에서 뺀 단서')]; assert len(hit) == 1
for p_ in hit[0].text_frame.paragraphs:
    if p_.text.startswith('· 사진:'):
        t = p_.text.replace(', 19장 @lennykuhne', '').replace('표지는 전시 포스터의', '표지 · 마무리는 전시 포스터의'); assert t != p_.text
        p_.runs[0].text = t
        for x in p_.runs[1:]: x._r.getparent().remove(x._r)
prs.save(OUT); print('saved', OUT, len(prs.slides))
