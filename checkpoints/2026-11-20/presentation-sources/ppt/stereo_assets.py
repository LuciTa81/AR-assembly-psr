# -*- coding: utf-8 -*-
"""양안 투영 장에 쓸 그림: 재현 합성, 왼눈·오른눈 화면, 겹쳐 보기. (Unity SBS 45초 지점)"""
import numpy as np
from PIL import Image, ImageFilter, ImageChops
A = '/mnt/user-data/uploads/AI_Assembly_Video_Pack_20261115/'; W_ = '/home/claude/grad'; PR = W_ + '/prep_s/'
s = Image.open(W_ + '/t4/sbs_45.png').convert('RGB'); L = s.crop((0, 0, 1920, 1080)); R = s.crop((1920, 0, 3840, 1080))

def glow(im, k=9, blur=10, gain=.6):
    t = im.filter(ImageFilter.MaxFilter(k)); g = t.filter(ImageFilter.GaussianBlur(blur))
    return Image.fromarray(np.clip(np.asarray(t).astype(np.float32) + np.asarray(g).astype(np.float32) * gain, 0, 255).astype(np.uint8))

def tint(im, rgb):
    a = np.asarray(im.convert('L')).astype(np.float32)[..., None] / 255
    return Image.fromarray(np.clip(a * np.array(rgb, np.float32), 0, 255).astype(np.uint8))

def screen(a, b):
    x = np.asarray(a).astype(np.float32) / 255; y = np.asarray(b).astype(np.float32) / 255
    return Image.fromarray(((1 - (1 - x) * (1 - y)) * 255).astype(np.uint8))

# 1) 왼눈 · 오른눈 화면 (선을 굵게)
BG = Image.new('RGB', (1920, 1080), (11, 15, 20))
def eye(im):
    o = im.copy(); t = im.copy(); po = o.load(); pt = t.load()
    for x in range(1920):
        for y in range(1080):
            is_text = y >= 780 or (52 <= y <= 98 and 760 <= x <= 1160)
            if is_text: po[x, y] = (0, 0, 0)
            else: pt[x, y] = (0, 0, 0)
    return ImageChops.lighter(glow(o, 11, 12), glow(t, 3, 6, .4))
gl = eye(L); gr = eye(R)
screen(BG, gl).resize((900, 506), Image.LANCZOS).save(PR + 'eyeL.png'); screen(BG, gr).resize((900, 506), Image.LANCZOS).save(PR + 'eyeR.png')
# 2) 겹쳐 보기: 왼눈 청록, 오른눈 주황
ov = screen(screen(BG, tint(gl, (70, 225, 200))), tint(gr, (255, 150, 50)))
ov.resize((900, 506), Image.LANCZOS).save(PR + 'overlap.png')
def bbox(im, y0, y1):
    a = np.asarray(im.convert('L'))[y0:y1]; ys, xs = np.where(a > 60); return int(xs.min()), int(xs.max())
print('outline x-range L', bbox(L, 100, 600), 'R', bbox(R, 100, 600))
# 3) 재현: 깨끗한 작업대 사진에 왼눈 윤곽을 나사 네 점 기준으로 맞춰 얹는다
photo = Image.open(A + '02_작업대_사진/작업대_편집용_크롭.png').convert('RGB')
src = [(942, 45), (1464, 45), (959, 490), (1547, 485)]          # Unity 왼눈 화면의 A B C D
dst = [(597, 268), (1045, 248), (588, 609), (1114, 575)]         # 사진 속 나사 A B C D
def homography(p, q):                                              # q -> p (출력 좌표에서 입력 좌표로)
    M = []; b = []
    for (x, y), (u, v) in zip(q, p):
        M += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]; b += [u, v]
    return np.linalg.solve(np.array(M, float), np.array(b, float))
lay = L.copy(); px_ = lay.load()
_a = np.asarray(L.convert('L')).astype(int)                          # 단계 글자가 윤곽 안쪽 윗선과 겹치므로, 글자를 지우고 선을 다시 잇는다
_y0 = 48 + int(_a[48:66, 836].argmax()); _y1 = 48 + int(_a[48:66, 1084].argmax()); _col = L.getpixel((836, _y0))
for x in range(838, 1083):
    for y in range(50, 98): px_[x, y] = (0, 0, 0)
    yy = round(_y0 + (_y1 - _y0) * (x - 838) / 244); px_[x, yy] = _col; px_[x, yy + 1] = _col
for x in range(0, 1920):
    for y in range(780, 1080): px_[x, y] = (0, 0, 0)
lay = glow(lay, 9, 9, .55)
warped = lay.transform(photo.size, Image.PERSPECTIVE, tuple(homography(src, dst)), Image.BICUBIC)
base = Image.fromarray((np.asarray(photo).astype(np.float32) * .82).astype(np.uint8))
comp = screen(base, warped)
def text_patch(box, scale):
    t = L.crop(box); return t.resize((int(t.width * scale), int(t.height * scale)), Image.LANCZOS)
lab = text_patch((840, 52, 1080, 98), .95); phr = text_patch((660, 800, 1260, 900), .95)
cv = np.asarray(comp).astype(np.float32)
def put(patch, cx, top):
    global cv
    p = np.asarray(patch).astype(np.float32); h, w = p.shape[:2]; x0 = int(cx - w / 2)
    reg = cv[top:top + h, x0:x0 + w] / 255; cv[top:top + h, x0:x0 + w] = (1 - (1 - reg) * (1 - p / 255)) * 255
put(lab, 470, 150); put(phr, 765, 838)
comp = Image.fromarray(cv.astype(np.uint8)).crop((0, 80, 1530, 941))   # 16:9
comp.save(PR + 'comp.jpg', quality=92); print('comp', comp.size)
