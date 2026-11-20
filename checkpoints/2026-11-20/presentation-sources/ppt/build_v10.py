# -*- coding: utf-8 -*-
"""사용자가 고친 v9(user_v9/u.pptx, 20장)을 그대로 두고 17 · 18 · 19 · 20장만 손본다 → v10.
17 Expected Impact : 맨 윗줄을 '집에서도, 현장에서도' (조립식 가구 둘 + 현장 하나), 첫 칸을 '처음 조립하는 사람'으로
18 Future Work     : 기대 가치를 다섯 줄로 (시장 · 집 / 시장 · 현장 / 시점 / 비용 / 사업 모델), 04 띄어쓰기
19 마무리          : 배경 사진 교체 (Unsplash @lennykuhne)
16 ~ 18            : PowerPoint에서 단어 중간에 줄이 끊기지 않게 (eaLnBrk · latinLnBrk = 0)
20 Memo            : 장 번호와 확인할 것 갱신"""
import sys, glob
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
from deckkit import chip
from pptx import Presentation
W_ = '/home/claude/grad'; BODY = '333333'
SRC = W_ + '/user_v9/u.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else W_ + '/out/AI Assembly Guide_구조테스트_v10.pptx'
prs = Presentation(SRC); S = list(prs.slides); assert len(S) == 20
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
def title_of(s): return [sh.text_frame.text for sh in s.shapes if sh.has_text_frame and sh.name == 'Title']
def drop(s, sh):
    rids = [b.get(R_NS + 'embed') for b in sh._element.iter(A_NS + 'blip')]
    sh._element.getparent().remove(sh._element)
    for rid in rids:
        if rid and rid not in s.shapes._spTree.xml: s.part.drop_rel(rid)
def find(s, text):
    hit = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip() == text]
    assert len(hit) == 1, (text, len(hit)); return hit[0]
def find_start(s, text):
    hit = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip().startswith(text)]
    assert len(hit) == 1, (text, len(hit)); return hit[0]
def set_text(sh, text):
    rs = sh.text_frame.paragraphs[0].runs; rs[0].text = text
    for r in rs[1:]: r._r.getparent().remove(r._r)
    for p_ in sh.text_frame.paragraphs[1:]: p_._p.getparent().remove(p_._p)
def in_box(sh, x0, y0, x1, y1):
    x, y = sh.left / 9525, sh.top / 9525
    return x0 <= x < x1 and y0 <= y < y1
def sec(s, x, y, text, w=500): tb(s, x, y, w, 24, text, size=13, color=ORANGE, w8='x', anchor='m')
def wordwrap(s):
    for sh in s.shapes:
        if not sh.has_text_frame: continue
        for p_ in sh.text_frame.paragraphs:
            pPr = p_._p.get_or_add_pPr(); pPr.set('eaLnBrk', '0'); pPr.set('latinLnBrk', '0')

# ------------------------------------------------------------------ 17 Expected Impact
s = S[16]; assert title_of(s) == ['Expected Impact']
set_text(find(s, '경력이 없어도, 처음 하는 사람이 바로 조립할 수 있게'), '경험이 없어도, 처음 하는 사람이 바로 조립할 수 있게')
for sh in [sh for sh in s.shapes if in_box(sh, 60, 95, 1240, 262)]: drop(s, sh)       # 맨 윗줄(왜 필요한가) 전부
sec(s, 71, 100, '왜 필요한가 · 집에서도, 현장에서도')
why = [('3명 중 2명', '조립식 가구 조립이 스트레스', '영국 주택 소유자 2,000명 설문'),
       ('절반', '옷장 하나를 제한 시간 안에 못 끝냄', '100명 조립 실험 · 심박은 평균 20% 올라감'),
       ('25.8%', '현장에서 못 뽑는 이유 1위는 경력', '미충원 사유 1위: 요구하는 경력을 갖춘 지원자가 없음')]
for k, (b_, l_, s_) in enumerate(why):
    x = 71 + k * 385
    hline(s, x, 128, 368, color=NAVY, lw=1.25)
    chip(s, x + 368 - 46, 136, '현장' if k == 2 else '집', fill=PALE, color=GREY, size=9.5, w=46, h=20, w8='s')
    tb(s, x, 133, 300, 46, b_, size=27, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x, 180, 368, 22, l_, size=13, color=TXT, w8='s', anchor='m', wrap=False)
    tb(s, x, 203, 368, 18, s_, size=10, color=GREY, anchor='m', wrap=False)
tb(s, 71, 232, 1138, 28, '집에서는 설명서가 어렵고, 현장에서는 경력자가 부족합니다.', size=14.5, color=NAVY, w8='x', anchor='m')
for sh in [sh for sh in s.shapes if in_box(sh, 80, 310, 300, 330)]: drop(s, sh)        # 첫 칸의 이름표
chip(s, 89, 318, '처음 조립하는 사람', fill=TINT, color=NAVY, size=9.5, h=20, w8='s')
set_text(find(s, '첫날부터 정확하게'), '처음부터 정확하게')
set_text(find_start(s, '다음 행동이 작업 위치 위에 보입니다.'), '집에서도 현장에서도 다음 행동이 작업 위치 위에 보입니다. 설명서를 오가거나 순서를 외우지 않아도 끝까지 조립합니다.')
set_text(find_start(s, '버튼을 누르지 않아도'), '버튼을 누르지 않아도 단계가 정확하게 넘어가, 두 손이 자유롭습니다.')
srcbox = find_start(s, '출처:'); x, y, w, h = srcbox.left, srcbox.top, srcbox.width, srcbox.height; drop(s, srcbox)
tb(s, 71, 660, 1138, 34, ['출처: SIMBA 영국 주택 소유자 2,000명 설문(2017) · Hotukdeals 이케아 가구 조립 실험 100명(2023) · 고용노동부 2026년 상반기 직종별사업체노동력조사(2026. 6. 30)',
                          'Boeing · Iowa State Univ.(I/ITSEC 2014) · Boeing 항공기 배선 작업 사례'], size=9, color=LGREY, ls=1.25, name='Source')
s.notes_slide.notes_text_frame.text = (
    '[기대효과] 누구를 위해, 왜 만들었고, 어떤 가치가 있는지를 위에서 아래로 말한다. 맨 윗줄은 "조립은 집에서도 현장에서도 어렵다"로 시작한다.\n'
    '집: 영국 가구 회사 SIMBA가 의뢰한 주택 소유자 2,000명 설문(The London Economic 2017. 4. 27 보도)에서 3명 중 2명이 조립식 가구 조립을 스트레스로 꼽았다. '
    '같은 설문에서 평생 조립식 가구 조립에 쓰는 시간은 평균 8일(195시간 이상). '
    'Hotukdeals의 실험(Apartment Therapy 2023. 3. 12 보도)에서는 100명이 심박계를 차고 이케아 가구를 조립했고, 가장 어려운 PAX 옷장은 절반만 제한 시간 안에 끝냈다. 심박은 평균 20%(13 BPM) 올랐다. '
    '이케아는 2017년 조립 대행 서비스 TaskRabbit을 인수했는데, 이케아 가구 조립은 TaskRabbit에서 가장 인기 있는 일 가운데 하나였다(Fortune 2017. 9. 28). 둘 다 회사가 의뢰하거나 진행한 조사라 "설문" "실험"으로만 말한다.\n'
    '현장: 고용노동부 2026년 상반기 직종별사업체노동력조사(2026. 6. 30). 1분기 미충원 사유 1위는 "사업체가 요구하는 경력을 갖춘 지원자가 없음"(25.8%). 전 산업 기준이다. '
    '질문이 나오면: 2026년 4월 1일 기준 부족인원 46만 7천 명, 제조업이 9만 6천 명으로 가장 많다. 고용허가제(E-9) 외국인 근로자는 2026년 7월 기준 28만 7,424명, 이 가운데 22만 9,844명이 제조업(고용노동부 자료, SBS Biz 2026. 9. 2 보도).\n'
    '누구에게 무엇을: 처음 조립하는 사람(집 · 현장) → 가르치는 숙련자 → 현장 관리자. 세 칸은 측정한 값이 아니라 이 구조에서 기대하는 것이다. 지금 시스템은 마커와 노트북이 있어야 하므로 집에서 바로 쓰는 단계는 아니다(18장 후속 연구 03 · 04).\n'
    '선행 사례: Boeing과 Iowa State University의 날개 조립 실험(I/ITSEC 2014 발표)에서 AR 안내는 PDF 설명서에 비해 조립 시간을 약 30% 줄였고 첫 시도 품질이 90% 가까이 좋아졌다. '
    'Boeing 항공기 배선 작업에서는 스마트 안경 안내로 작업 시간이 25% 줄었다. 모두 다른 회사의 결과이며, 이 프로젝트에서 잰 값이 아니다.\n'
    '화면에서 뺀 단서: 이 프로젝트에서 여러 사람을 대상으로 한 작업 시간 · 오류 비교는 아직 하지 않았다(18장 후속 연구 01).')

# ------------------------------------------------------------------ 18 Future Work
s = S[17]; assert title_of(s) == ['Future Work']
set_text(find(s, '상자 하나에서 확인한 구조를, 현장이 쓰는 제품으로 넓힙니다'), '상자 하나에서 확인한 구조를, 현장과 집으로 넓힙니다')
set_text(find_start(s, '판단을 가볍게 만들어'), '판단을 가볍게 만들어, 노트북 대신 소형 기기나 안경만으로 실행합니다.')
panel = [sh for sh in s.shapes if in_box(sh, 581, 100, 1240, 650)]
bg = [sh for sh in panel if sh.width / 9525 > 600]; assert len(bg) == 1
for sh in panel:
    if sh is not bg[0]: drop(s, sh)
sec(s, 605, 114, '기대 가치')
hline(s, 605, 142, 580, color=NAVY, lw=1.25)
biz = [('시장 · 집', '149.6억 → 212.6억 달러', 20, ['조립식 가구의 세계 시장 전망입니다 (2024 → 2029, 연평균 9.2%).', '국내에서는 이케아코리아 한 곳의 매출이 약 6,393억 원입니다.']),
       ('시장 · 현장', '40만 대 미만 → 650만 대', 20, ['제조 현장으로 나가는 AR 안경의 연간 출하량 전망입니다', '(2024 → 2030, 연평균 59%).']),
       ('시점', 'HoloLens 생산 종료 · Guides 지원 종료', 16, ['Microsoft는 2024년 말 HoloLens 생산을 멈췄고,', '작업 안내 Dynamics 365 Guides의 지원도 2026년 12월에 끝납니다.']),
       ('비용', 'AR 안경 + 서버', 20, ['549달러짜리 소비자용 XR 안경으로 구성했습니다.', '산업용 헤드셋 HoloLens 2의 출시가는 3,500달러였습니다.']),
       ('사업 모델', '작업대 단위 구독 + 작업 등록', 16, ['현장에는 조립 라인 · 직업 훈련 · 정비 작업대 단위로 제공하고,', '집에는 가구 · 전자제품 회사와 제품별 조립 안내를 함께 만듭니다.'])]
RH = 98.6
for k, (l_, v_, vs, d_) in enumerate(biz):
    y = 143 + k * RH
    tb(s, 605, y + 13, 86, 22, l_, size=10.5, color=GREY, w8='s', anchor='m')
    tb(s, 693, y + 8, 492, 32, v_, size=vs, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, 693, y + 44, 492, 44, d_, size=11, color=BODY, ls=1.35)
    if k < 4: hline(s, 605, y + RH, 580, color=LBLUE)
srcbox = find_start(s, '출처:'); drop(s, srcbox)
tb(s, 71, 660, 1138, 34, ['출처: The Business Research Company(2025. 5) · 헤럴드경제(2026. 4. 25, 이케아코리아 2025 회계연도) · ABI Research, AR Smart Glasses Shipments in Manufacturing(2026)',
                          'Directions on Microsoft(2026. 1. 26) · Road to VR(2026. 4. 27, VITURE Beast 출시가) · TechRadar(HoloLens 2 출시가)'], size=9, color=LGREY, ls=1.25, name='Source')
s.notes_slide.notes_text_frame.text = (
    '[후속 연구와 기대 가치] 왼쪽은 앞으로 할 연구, 오른쪽은 그 연구가 향하는 곳. 왼쪽 네 줄의 화살표가 오른쪽으로 이어진다고 말한다.\n'
    '후속 연구: 01 처음 하는 사람들을 대상으로 종이 설명서와 비교(작업 시간 · 오류 수 · 작업 부담). 02 지금은 도구가 닿고 머문 것(접근 → 유지 → 이탈)으로 판단하므로, 조임 완료 자체를 판단하도록 넓힌다. '
    '03 지금은 한 종류의 상자와 마커 작업대다. 새 작업을 등록하는 도구와 마커 없는 추적으로 대상을 넓힌다. 집에서 쓰려면 이 단계가 먼저 필요하다. 04 지금은 Windows 노트북에서 판단한다.\n'
    '기대 가치: 시장 · 집 — The Business Research Company는 조립식(RTA) 가구 세계 시장을 2024년 149.6억 달러에서 2029년 212.6억 달러로, 연평균 9.2% 늘 것으로 본다(EIN Presswire 2025. 5. 16). '
    '이케아코리아의 2025 회계연도(2024. 9 ~ 2025. 8) 매출은 약 6,393억 원(헤럴드경제 2026. 4. 25). '
    '시장 · 현장 — ABI Research는 제조 분야 AR 안경의 연간 출하량이 2024년 40만 대 미만에서 2030년 650만 대로, 연평균 59% 늘 것으로 본다. '
    '시점 — Microsoft는 2024년 말 HoloLens 생산을 멈췄고, 2025년 12월에 Dynamics 365 Guides와 Remote Assist의 지원 종료(2026년 12월)를 알렸으며 후속 제품은 발표하지 않았다. '
    '비용 — 이 프로젝트의 안경 VITURE Beast는 2026년 4월 27일 549달러에 출시됐다. HoloLens 2의 출시가는 3,500달러였다. 헤드셋은 단독으로 동작하고, 이 프로젝트는 판단을 맡는 노트북(서버)이 더 필요하다는 점은 다르다. '
    '사업 모델 — 현장의 작업대 단위 구독, 집을 위한 제품별 조립 안내 제휴는 예상이며 확인한 수요가 아니다.\n'
    '비슷한 방향의 상용 제품: PTC Vuforia Step Check(2023, AI로 조립 상태를 검사해 합격 · 불합격을 표시). 질문이 나오면 "고가 장비가 아닌 소비자용 안경에서, 검사가 아니라 작업 단계의 진행을 따라간다"는 점을 말한다.')

for s in S[15:18]: wordwrap(s)

# ------------------------------------------------------------------ 19 마무리: 배경 사진
s = S[18]
old = [sh for sh in s.shapes if sh.shape_type == 13 and sh.width / 9525 > 1200]; assert len(old) == 1
new = s.shapes.add_picture(W_ + '/cand_close/bg_1.jpg', px(0), px(0), px(1280), px(720))
sp = s.shapes._spTree; sp.remove(new._element); old[0]._element.addprevious(new._element); drop(s, old[0])
s.notes_slide.notes_text_frame.text = '[마무리] 참고 영상 10:16. 배경 사진: Unsplash @lennykuhne (자동차 조립 라인). 왼쪽에 남색 그라데이션을 얹었다.'

# ------------------------------------------------------------------ 20 Memo
s = S[19]; assert title_of(s) == ['Memo']
for sh in list(s.shapes): drop(s, sh)
header(s, 'Memo', '구조 테스트 메모 — 영상에는 넣지 않는 장')
rect(s, 71, 100, 1138, 30, fill=PALE)
for x, w, t_ in [(87, 110, '장'), (200, 300, '내용'), (510, 690, '바뀐 것 · 확인할 것')]:
    tb(s, x, 100, w, 30, t_, size=11.5, color=NAVY, w8='x', anchor='m')
mm = [('6 · 7', '전체 아키텍처, 세 가지 문제', 'HMM은 도식대로, 실시간에서 돈다는 전제 → 아래 둘째 줄'),
      ('11 · 13 · 14', '양안 투영, 가림과 복구, 시연', '11장 위쪽 그림은 재현. 13장 영상은 0:30 ~ 0:38, 14장은 나사 B · C 구간만 2배속 (1분 36초)'),
      ('15', '관제 화면', '메뉴 설명 가운데 작업 기록 · 연결·진단 · 설정은 이름을 보고 쓴 것 → 확인'),
      ('16', '평가와 결과', '"사용하면서 고친 것"은 발표자 노트에. 61.3%가 session 17의 값인지 → 확인'),
      ('17', '기대효과', 'v10: 맨 윗줄을 "집에서도, 현장에서도"로 (조립식 가구 둘 + 현장 하나). 첫 칸을 "처음 조립하는 사람"으로. 노동력 수치는 노트로'),
      ('18', '후속 연구 · 기대 가치', 'v10: 시장을 집 · 현장 두 줄로. 비용 설명에 549달러를 다시 넣음. 사업 모델의 "집" 쪽은 제가 쓴 문장 → 확인'),
      ('19', '마무리', 'v10: 배경 사진 교체 (후보 1). 다른 후보로 바꿀 수 있음'),
      ('16 ~ 18', '줄바꿈', 'v10: PowerPoint에서 단어 중간에 줄이 끊기지 않게 함. 다른 장에도 필요하면 같은 설정을 씀')]
for k, (n, a_, b_) in enumerate(mm):
    y = 130 + k * 36
    tb(s, 87, y, 110, 36, n, size=11.5, color=ORANGE, w8='x', anchor='m')
    tb(s, 200, y, 300, 36, a_, size=11, color=TXT, anchor='m')
    tb(s, 510, y, 690, 36, b_, size=11, color=BODY, anchor='m', ls=1.2)
    hline(s, 71, y + 36, 1138)
tb(s, 71, 432, 1138, 220, ['· 화면에서 뺀 단서는 장마다 발표자 노트에 "화면에서 뺀 단서"로 남겨 둠: 촬영용 설정(초록 안내 2초 뒤 자동 전환), 조임 품질을 재지 않는다는 점, 꺼진 시간 38초, 아직 재지 못한 항목',
                           '· HMM: "실시간에서 돌아간다"는 전제로 6 · 9장에 적었음. 코덱스 구성안에는 "현재 실시간 단계 전이를 HMM이 직접 수행한다고 설명하지 않는다"는 줄이 있으므로 답할 문장을 정해 둘 것',
                           '· 94.1%: 그리드 서치를 같은 세션에서 했다면 그렇게 말해야 함. mAP 94.0%는 5월 학습본(3종 재학습 전)의 값',
                           '· 17 · 18장의 외부 수치는 모두 출처를 확인한 값. 조립식 가구 설문과 실험은 회사가 의뢰하거나 진행한 것이라 "설문" "실험"으로만 말함. 선행 사례의 수치는 다른 회사의 결과',
                           '· 사진: 2 · 3장 Unsplash @maciejka_dslr, 4장 @shaikhulud · @tomspentys, 19장 @lennykuhne, 표지의 안경은 VITURE 제품 이미지, 8장은 1학기 발표 자료의 화면. 글꼴은 Pretendard Bold를 쓰지 않음'], size=10.5, color=BODY, ls=1.4)
prs.save(OUT); print('saved', OUT, len(prs.slides))
