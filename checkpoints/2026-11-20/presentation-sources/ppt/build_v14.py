# -*- coding: utf-8 -*-
"""사용자가 고친 v13(user_v13/u.pptx) → v14.
19 마무리 : 안경 · 카드 · 초록 선을 빼고 배경과 원래 글만 (A안). sys.argv[2] == 'B' 이면 07 최종 확인 카드만 둔다
2  목차   : 11 · 12장 순서를 바꾸신 데 맞춰 04 설명을 '보정과 확인, 눈별 투영'으로
노트      : 장 번호 (14장 → 12장, 16장 → 11장), 16장 98.7% · 99.2% 확인 메모
17        : 고용노동부 조사 문항을 바꿔 쓴 따옴표를 풀어 씀
20 Memo   : 줄 몇 개 갱신"""
import sys
sys.path.insert(0, '/home/claude/grad')
from cover_v12 import *
from pptx import Presentation
SRC = W_ + '/user_v13/u.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v14.pptx'
OPT = sys.argv[2] if len(sys.argv) > 2 else 'A'
prs = Presentation(SRC); S = list(prs.slides); assert len(S) == 20
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
def drop(s, sh):
    rids = [b.get(R_NS + 'embed') for b in sh._element.iter(A_NS + 'blip')]
    sh._element.getparent().remove(sh._element)
    for rid in rids:
        if rid and rid not in s.shapes._spTree.xml: s.part.drop_rel(rid)
def set_first(sh, text):
    rs = sh.text_frame.paragraphs[0].runs; rs[0].text = text
    for r in rs[1:]: r._r.getparent().remove(r._r)
def find(s, start):
    hit = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip().startswith(start)]; assert len(hit) == 1, (start, len(hit)); return hit[0]
def renote(s, a, b):
    tf = s.notes_slide.notes_text_frame; t = tf.text; assert a in t, a; tf.text = t.replace(a, b)
def wordwrap(s):
    for sh in s.shapes:
        if sh.has_text_frame:
            for p_ in sh.text_frame.paragraphs:
                pPr = p_._p.get_or_add_pPr(); pPr.set('eaLnBrk', '0'); pPr.set('latinLnBrk', '0')

# ------------------------------------------------------------------ 19 마무리
s = S[18]
texts = [sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
assert texts[-5:] == ['눈앞에는 다음 작업을,\n관제에는 전체 흐름을.', 'AI Assembly Guide는 조립 순서를 따라\n작업을 이어가도록 돕습니다.', 'AI Assembly Guide', '작업 단계 인식 기반 AR 조립 안내', '개발 최민준 C011207   |   지도교수 윤영 교수님'], texts[-5:]
for sh in list(s.shapes): drop(s, sh)
pic(s, PC + 'cover_bg.jpg', 0, 0, 1280, 720)
if OPT == 'B': final_card(s, 880, 214)
closing_text(s); wordwrap(s)
s.notes_slide.notes_text_frame.text = ('[마무리] 참고 영상 10:16. 표지와 같은 배경에 원래 마무리 글만 두었다(안경 · 카드는 표지에만).'
                                       + (' 오른쪽에는 마지막 단계(07 최종 확인) 카드를 두었다.' if OPT == 'B' else '')
                                       + ' 배경은 전시 포스터에서 가져온 이미지.')

# ------------------------------------------------------------------ 2 목차
c = find(S[1], '눈별 투영, 보정과 확인'); set_first(c, '보정과 확인, 눈별 투영')

# ------------------------------------------------------------------ 노트의 장 번호와 확인 메모
renote(S[13], '실제 안경 화면은 11장에 있다.', '실제 안경 화면은 12장에 있다.')
renote(S[15], '(12장에서 날짜와 표현을 고치신 데 맞춰', '(11장에서 날짜와 표현을 고치신 데 맞춰')
tf = S[15].notes_slide.notes_text_frame
tf.text = ('확인 필요: 화면의 98.7%(문제 2, 일치율)와 99.2%(문제 3)가 무엇을 어떤 조건에서 잰 값인지 여기에 적어 둘 것. '
           '아래 문제 2 · 3 설명은 이전 화면(나사 4 / 4 착용자 확인, 가림 10 / 10) 기준이다.\n' + tf.text)

# ------------------------------------------------------------------ 17 따옴표
q = find(S[16], "사람을 못 뽑는 이유 1위는 '요구하는 경험을 갖춘 지원자가 없음'(25.8%)입니다.")
set_first(q, '사람을 못 뽑는 이유 1위는 경험을 갖춘 지원자가 없다는 것(25.8%)입니다.')
renote(S[16], "02 현장: 고용노동부", "02 현장(조사 문항 원문은 '경력'): 고용노동부")

# ------------------------------------------------------------------ 20 Memo
m = S[19]
set_first(find(m, '11 · 13 · 14'), '12 · 13 · 14')
set_first(find(m, '11장 위쪽 그림은 재현.'), '12장 위쪽 그림은 재현. 13장 영상은 0:30 ~ 0:38, 14장은 나사 B · C 구간만 2배속 (1분 36초)')
set_first(find(m, '"사용하면서 고친 것"은 발표자 노트에.'), '61.3%가 session 17의 값인지, 98.7% · 99.2%가 무엇을 잰 값인지 → 노트에 적을 것')
set_first(find(m, 'v13: 표지와 같은 배경'), 'v14: 안경 · 카드를 빼고 표지와 같은 배경에 원래 글만' if OPT == 'A' else 'v14: 안경을 빼고 07 최종 확인 카드만')
prs.save(OUT); print('saved', OUT, len(prs.slides), OPT)
