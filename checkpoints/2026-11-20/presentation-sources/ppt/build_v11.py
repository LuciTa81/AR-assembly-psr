# -*- coding: utf-8 -*-
"""사용자가 고친 v10(user_v10/u.pptx)을 그대로 두고 → v11.
14 Product : 영상 설명 문장 다듬기
17 · 18    : 분량을 줄이고 '사진 반 + 글 반' 구성으로 (v11_parts.py). 17장 사진은 후보 1, 18장은 Meta 제품 사진
20 Memo    : 17 · 18 줄과 사진 출처 갱신"""
import sys
sys.path.insert(0, '/home/claude/grad')
from v11_parts import *
from pptx import Presentation
SRC = W_ + '/user_v10/u.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v11.pptx'
PICK17 = int(sys.argv[2]) if len(sys.argv) > 2 else 1
prs = Presentation(SRC); S = list(prs.slides); assert len(S) == 20
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
def title_of(s): return [sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.name == 'Title']
def drop(s, sh):
    rids = [b.get(R_NS + 'embed') for b in sh._element.iter(A_NS + 'blip')]
    sh._element.getparent().remove(sh._element)
    for rid in rids:
        if rid and rid not in s.shapes._spTree.xml: s.part.drop_rel(rid)
def clear(s):
    for sh in list(s.shapes): drop(s, sh)

# ------------------------------------------------------------------ 14 영상 설명
s = S[13]; assert title_of(s) == ['Product']
hit = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip() == '카메라 화면에 안경의 조립 안내 영상']; assert len(hit) == 1
r = hit[0].text_frame.paragraphs[0].runs; r[0].text = '카메라 화면에 안경의 조립 안내를 겹친 영상'
for x in r[1:]: x._r.getparent().remove(x._r)

# ------------------------------------------------------------------ 17 Expected Impact
s = S[16]; assert title_of(s) == ['Expected Impact']; clear(s)
impact_slide(s, prep17(PICK17)); wordwrap(s)
s.notes_slide.notes_text_frame.text = (
    '[기대효과] 왼쪽 사진의 한 줄("처음 하는 사람도 바로 조립할 수 있게")로 시작해, 오른쪽 세 줄을 위에서 아래로 말하고 아래 상자로 맺는다.\n'
    '01 집: 영국 가구 회사 SIMBA가 의뢰한 주택 소유자 2,000명 설문(The London Economic 2017. 4. 27 보도)에서 3명 중 2명이 조립식 가구 조립을 스트레스로 꼽았다. '
    '같은 설문에서 평생 조립식 가구 조립에 쓰는 시간은 평균 8일(195시간 이상). Hotukdeals 실험(2023)에서는 100명 가운데 절반만 PAX 옷장을 제한 시간 안에 끝냈다.\n'
    "02 현장: 고용노동부 2026년 상반기 직종별사업체노동력조사(2026. 6. 30). 1분기 미충원 사유 1위는 '사업체가 요구하는 경력을 갖춘 지원자가 없음'(25.8%), 전 산업 기준. "
    '질문이 나오면: 2026년 4월 1일 기준 부족인원 46만 7천 명, 제조업이 9만 6천 명으로 가장 많다.\n'
    '03 선행 사례: Boeing과 Iowa State University의 날개 조립 실험(I/ITSEC 2014)에서 AR 안내는 PDF 설명서에 비해 조립 시간을 약 30% 줄였고 첫 시도 품질이 90% 가까이 좋아졌다. '
    'Boeing 배선 작업에서는 스마트 안경 안내로 작업 시간이 25% 줄었다. 다른 회사의 결과이며 이 프로젝트에서 잰 값이 아니다.\n'
    '화면에서 뺀 것: "체계적인 조립 도움" 세 칸(처음 조립하는 사람 · 가르치는 숙련자 · 현장 관리자). 말로 덧붙일 때는 숙련자가 옆에 붙어 있는 시간이 줄고, 관리자는 관제 화면과 기록으로 확인한다고 말한다. '
    '"60대 80%" 수치는 출처를 찾지 못해 넣지 않았다.\n'
    '사진: Unsplash @albacalbeto (나사를 다루는 손).')

# ------------------------------------------------------------------ 18 Future Work
s = S[17]; assert title_of(s) == ['Future Work']; clear(s)
future_slide(s, prep18()); wordwrap(s)
s.notes_slide.notes_text_frame.text = (
    '[후속 연구와 기대 가치] 왼쪽 위는 앞으로 할 연구, 왼쪽 아래는 그 연구가 향하는 시장, 오른쪽 사진은 지금이 그 때인 이유.\n'
    '후속 연구: 01 처음 하는 사람들을 대상으로 종이 설명서와 비교(작업 시간 · 오류 수 · 작업 부담). 02 지금은 도구가 닿고 머문 것(접근 → 유지 → 이탈)으로 판단하므로 조임 완료 자체를 판단하도록 넓힌다. '
    '03 지금은 한 종류의 상자와 마커 작업대, Windows 노트북이다. 마커 없는 추적과 경량화로 안경만으로 실행하는 쪽으로 간다. 집에서 쓰려면 이 단계가 먼저 필요하다.\n'
    '기대 가치: 집 — The Business Research Company는 조립식(RTA) 가구 세계 시장을 2024년 149.6억 달러에서 2029년 212.6억 달러로, 연평균 9.2% 늘 것으로 본다(EIN Presswire 2025. 5. 16). 국내 이케아코리아의 2025 회계연도 매출은 약 6,393억 원(헤럴드경제 2026. 4. 25). '
    '현장 — ABI Research는 제조 분야 AR 안경의 연간 출하량이 2024년 40만 대 미만에서 2030년 650만 대로 늘 것으로 본다(연평균 59%). '
    '사업 모델(현장 작업대 단위 구독, 집을 위한 제품별 조립 안내)은 예상이며 확인한 수요가 아니다.\n'
    '오른쪽 사진: IDC(2026. 6. 15)는 디스플레이 없는 스마트 안경 출하가 2026년 1,360만 대에서 2030년 2,730만 대로 늘 것으로 본다(연평균 18.9%). '
    'Meta는 레이밴 메타 Gen2 등을 2026년 5월 25일 국내에 출시했다(Meta 뉴스룸 2026. 5. 19). 삼성전자와 구글의 AI 안경("인텔리전트 아이웨어")은 11월 12일 사전 예약, 12월 정식 출시 예정(연합뉴스 2026. 11. 9).\n'
    '화면에서 뺀 것: HoloLens 생산 종료 · Dynamics 365 Guides 지원 종료(2026. 12), VITURE Beast 같은 소비자용 XR 안경으로 구성했다는 점과 HoloLens 2 출시가 3,500달러. 질문이 나오면 말한다. '
    'XREAL Aura의 국내 출시는 확인하지 못해 넣지 않았다.\n'
    '사진: Meta Ray-Ban Display 제품 이미지(Meta). 이 프로젝트에서 쓴 안경이 아니라 AI 안경의 예로 보여 준다.')

# ------------------------------------------------------------------ 20 Memo : 17 · 18 줄과 사진 줄만 바꿈
s = S[19]; assert title_of(s) == ['Memo']
def retext(old_start, new):
    hit = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip().startswith(old_start)]; assert len(hit) == 1, old_start
    r = hit[0].text_frame.paragraphs[0].runs; r[0].text = new
    for x in r[1:]: x._r.getparent().remove(x._r)
retext('v10: 맨 윗줄을', 'v11: 사진 반 + 글 반으로 줄임. 세 칸은 노트로. "60대 80%"는 출처를 못 찾아 뺌')
retext('v10: 시장을 집', 'v11: 후속 연구 셋 + 시장 둘 + 사업 모델 한 줄. 오른쪽은 Meta 제품 사진. 시점 · 비용 줄은 노트로')
for sh in s.shapes:
    if sh.has_text_frame and sh.text_frame.text.strip() == '후속 연구 · 기대 가치': pass
hit = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.startswith('· 화면에서 뺀 단서')]; assert len(hit) == 1
for p_ in hit[0].text_frame.paragraphs:
    if p_.text.startswith('· 사진:'):
        p_.runs[0].text = '· 사진: 2 · 3장 Unsplash @maciejka_dslr, 4장 @shaikhulud · @tomspentys, 17장 @albacalbeto, 18장 Meta Ray-Ban Display 제품 이미지, 19장 @lennykuhne, 표지의 안경은 VITURE 제품 이미지, 8장은 1학기 발표 자료의 화면'
        for x in p_.runs[1:]: x._r.getparent().remove(x._r)
prs.save(OUT); print('saved', OUT, len(prs.slides))
