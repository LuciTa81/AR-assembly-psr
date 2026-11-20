# -*- coding: utf-8 -*-
"""v11: 17 Expected Impact · 18 Future Work 를 '사진 반 + 글 반' 구성으로 줄인다 (학교 제안서 Why school 장과 같은 틀).
사진 준비(prep_photo)와 장 그리기(impact_slide, future_slide)를 나눠 두고, build_v11.py 와 후보 시안이 같이 쓴다."""
import sys, glob
import numpy as np
from PIL import Image
SK = glob.glob('/root/.claude/skills/synced/*/sentient-deck')[0]
sys.path.insert(0, SK + '/scripts')
from deckkit import *
W_ = '/home/claude/grad'; PV = W_ + '/prep_v11/'; BODY = '333333'
import os; os.makedirs(PV, exist_ok=True)

def cover(src, w, h, fx=.5, fy=.5, scale=2):
    im = Image.open(src).convert('RGB')
    Wd, Hd = int(round(w * scale)), int(round(h * scale)); r = max(Wd / im.width, Hd / im.height)
    im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x = int((im.width - Wd) * fx); y = int((im.height - Hd) * fy); return im.crop((x, y, x + Wd, y + Hd))
def shade(im, top=0, bottom=0, flat=0, c=(22, 38, 64)):
    a = np.asarray(im).astype(np.float32); h = a.shape[0]; ys = np.linspace(0, 1, h)[:, None, None]
    k = flat + top * np.clip(1 - ys / .55, 0, 1) ** 1.2 + bottom * np.clip((ys - .45) / .55, 0, 1) ** 1.2
    k = np.clip(k, 0, .94); return Image.fromarray((a * (1 - k) + np.array(c, np.float32)[None, None, :] * k).astype(np.uint8))

PW17 = 560; PW18 = 580
PH17 = {  # 17장 왼쪽 사진 후보: (원본, fx, fy, top, flat)
    1: (W_ + '/cand17/hi/albacalbeto-senior_screws.jpg', .5, .62, .85, .22),
    2: (W_ + '/cand17/hi/jaywennington-flatpack_hardware.jpg', .5, .55, .8, .25),
    3: (W_ + '/photo/helloimnik-assemble_a.jpg', .42, .5, .85, .25),
    4: (W_ + '/cand_close/hi/alirezahatami-factory_man.jpg', .62, .5, .85, .25)}
def prep17(n):
    f, fx, fy, top, flat = PH17[n]; p = PV + 'impact_%d.jpg' % n
    shade(cover(f, PW17, 720, fx, fy), top=top, flat=flat).save(p, quality=90); return p
def prep18():
    p = PV + 'future_meta.jpg'
    shade(cover('/mnt/user-data/uploads/Downloads/unsplash/mrbd_Meta-Ray-Ban-Display_Social-Share.jpg', PW18, 720, .3, .5), bottom=1.05, flat=.08).save(p, quality=90); return p

def numrow(s, x, y, n, title, desc, w, tsize=16, dsize=12.5, dy=32, dh=48):
    tb(s, x, y, 40, 26, '%02d' % n, size=15, color=LBLUE, w8='x', anchor='m')
    tb(s, x + 42, y, w - 42, 26, title, size=tsize, color=NAVY, w8='x', anchor='m', wrap=False)
    tb(s, x + 42, y + dy, w - 42, dh, desc, size=dsize, color=BODY, ls=1.45)
def callout(s, x, y, w, h, lines, size=15.5):
    rect(s, x, y, w, h, fill=PALE); rect(s, x, y, 4, h, fill=NAVY)
    tb(s, x + 24, y, w - 40, h, lines, size=size, color=NAVY, w8='x', anchor='m', ls=1.4)

def impact_slide(s, photo):
    pic(s, photo, 0, 0, PW17, 720)
    tb(s, 48, 54, 480, 110, ['처음 하는 사람도', '바로 조립할 수 있게'], size=28, color=WHITE, w8='x', ls=1.3)
    rect(s, 50, 178, 36, 2, fill=LBLUE)
    tb(s, 48, 190, 480, 24, '집에서도, 산업 현장에서도 조립은 어렵습니다.', size=13.5, color='D9E2F0', anchor='m')
    X = 616; W = 1209 - X
    tb(s, X, 44, W, 42, 'Expected Impact', size=20, color=NAVY, w8='x', anchor='m', name='Title')
    pts = [('집에서도 어렵습니다', '조립식 가구를 조립해 본 사람 3명 중 2명이 스트레스라고 답했습니다.'),
           ('산업 현장에는 경험자가 부족합니다', "사람을 못 뽑는 이유 1위는 '요구하는 경력을 갖춘 지원자가 없음'(25.8%)입니다."),
           ('AR 안내는 이미 효과가 확인됐습니다', 'Boeing · Iowa State 실험에서 PDF 설명서보다 조립 시간은 약 30% 줄고, 첫 시도 품질은 90% 가까이 좋아졌습니다.')]
    for k, (t_, d_) in enumerate(pts):
        numrow(s, X, 122 + k * 118, k + 1, t_, d_, W)
    callout(s, X, 494, W, 100, ['버튼을 누르지 않아도 단계가 정확하게 넘어가,', '처음 하는 사람도 두 손으로 끝까지 조립합니다.'])
    tb(s, X, 650, W, 40, ['출처: SIMBA 영국 주택 소유자 2,000명 설문(2017) · 고용노동부 직종별사업체노동력조사(2026. 6. 30)',
                          'Boeing · Iowa State Univ.(I/ITSEC 2014)'], size=9, color=LGREY, ls=1.25, name='Source')

def future_slide(s, photo):
    X = 71; W = 640 - X
    tb(s, 49, 44, 600, 42, 'Future Work', size=20, color=NAVY, w8='x', anchor='m', name='Title')
    tb(s, X, 100, W, 24, '후속 연구', size=13, color=ORANGE, w8='x', anchor='m')
    hline(s, X, 128, W, color=NAVY, lw=1.25)
    fw = [('현장 사용자 평가', '처음 하는 사람들과 종이 설명서를 비교해 시간 · 오류를 잽니다.'),
          ('조임 완료 판단', '나사가 끝까지 조여졌는지 영상과 공구 신호로 확인합니다.'),
          ('마커 없이, 안경만으로', '마커 없는 추적과 경량화로 노트북 없이 실행합니다.')]
    for k, (t_, d_) in enumerate(fw):
        numrow(s, X, 142 + k * 62, k + 1, t_, d_, W, tsize=15, dsize=12, dy=28, dh=22)
    tb(s, X, 342, W, 24, '기대 가치', size=13, color=ORANGE, w8='x', anchor='m')
    hline(s, X, 370, W, color=NAVY, lw=1.25)
    st = [('149.6억 → 212.6억 달러', '집 · 조립식 가구 세계 시장 (2024 → 2029, 연평균 9.2%)'),
          ('40만 대 미만 → 650만 대', '현장 · 제조 현장으로 나가는 AR 안경 연간 출하 (2024 → 2030)')]
    for k, (b_, l_) in enumerate(st):
        y = 380 + k * 80
        tb(s, X, y, W, 42, b_, size=24, color=NAVY, w8='x', anchor='m', wrap=False)
        tb(s, X, y + 42, W, 22, l_, size=12, color=BODY, anchor='m', wrap=False)
    callout(s, X, 552, W, 84, ['현장에는 작업대 단위 구독으로,', '집에는 제품별 조립 안내로 넓힙니다.'], size=15)
    pic(s, photo, 1280 - PW18, 0, PW18, 720)
    PX = 1280 - PW18 + 40
    tb(s, PX, 440, PW18 - 72, 100, ['AI 안경이', '일상으로 들어옵니다'], size=26, color=WHITE, w8='x', ls=1.28)
    rect(s, PX + 2, 552, 36, 2, fill=LBLUE)
    tb(s, PX, 566, PW18 - 72, 44, ['디스플레이 없는 AI 안경 출하는 2030년 2,730만 대,', '4년 만에 두 배가 될 전망입니다.'], size=12.5, color='D9E2F0', ls=1.4)
    tb(s, PX, 626, PW18 - 72, 20, 'Meta 국내 출시 (2026. 5) · 삼성 · 구글 출시 예정 (2026. 12)', size=10.5, color='AFC0D6', anchor='m', wrap=False)
    tb(s, X, 650, W, 40, ['출처: The Business Research Company(2025. 5) · ABI Research(2026) · IDC(2026. 6. 15)',
                          'Meta 뉴스룸(2026. 5. 19) · 연합뉴스(2026. 11. 9)'], size=9, color=LGREY, ls=1.25, name='Source')

def wordwrap(s):
    for sh in s.shapes:
        if not sh.has_text_frame: continue
        for p_ in sh.text_frame.paragraphs:
            pPr = p_._p.get_or_add_pPr(); pPr.set('eaLnBrk', '0'); pPr.set('latinLnBrk', '0')
