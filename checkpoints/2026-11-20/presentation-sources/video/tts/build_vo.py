"""파트 음성 → 0.95배 느리게(음높이 유지) → 문장별 조각 wav + vo_data.js
python3 build_vo.py 1 2 3 4 5 6
각 줄: d(조각 길이), sp(자막 카드 나누는 시각, 조각 시작 기준)
"""
import json, re, sys, os, glob, subprocess, difflib, numpy as np
from seg import silences, dur
HERE = os.path.dirname(os.path.abspath(__file__)); VID = os.path.dirname(HERE)
TEMPO = 0.95; SR = 48000; PRE = 0.03; POST = 0.10

def norm(s): return re.sub(r'[^가-힣A-Za-z0-9]', '', s)
def hang(s): return re.sub(r'[^가-힣]', '', s)

R = json.load(open(f'{HERE}/lines_read.json'))
CAP = {}
for f in sorted(glob.glob(f'{VID}/scenes/s*.html')):
    n = os.path.basename(f)[:-5]
    for k, t in re.findall(r"k:'(\w+)',\s*t:'([^']*)'", open(f).read()): CAP[(n, k)] = t

def part_lines(i):
    return [l for l in open(f'{HERE}/p{i}.txt').read().split('\n') if l.strip()]

def char_times(mp3, lines):
    """대본 글자(norm) 하나하나의 시각 (ASR 단어 시각 + 글자 맞추기)"""
    W = json.load(open(mp3.replace('.mp3', '_words.json')))
    exp = []; owner = []; pos = []
    for k, l in enumerate(lines):
        for j, ch in enumerate(norm(l)): exp.append(ch); owner.append(k); pos.append(j)
    asr = []; at = []
    for a, b, w in W:
        cs = norm(w)
        for i, ch in enumerate(cs): asr.append(ch); at.append(a + (b - a) * (i + 0.5) / max(1, len(cs)))
    sm = difflib.SequenceMatcher(None, ''.join(exp), ''.join(asr), autojunk=False)
    t_of = {}
    for blk in sm.get_matching_blocks():
        for i in range(blk.size): t_of[blk.a + i] = at[blk.b + i]
    per = [dict() for _ in lines]
    for i, k in enumerate(owner):
        if i in t_of: per[k][pos[i]] = t_of[i]
    return per

def best_sil(S, a, b):
    """[a,b] 와 겹치는 쉼 중 가장 긴 것"""
    c = [(x, y) for x, y in S if y > a and x < b]
    return max(c, key=lambda s: s[1] - s[0]) if c else None

def run(i):
    raw = f'{HERE}/raw_p{i}.mp3'; st = f'{HERE}/st_p{i}.wav'
    if not os.path.exists(st) or os.path.getmtime(st) < os.path.getmtime(raw):
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', raw, '-af', f'rubberband=tempo={TEMPO}', '-ar', str(SR), '-ac', '1', '-c:a', 'pcm_f32le', st], check=True)
    lines = part_lines(i)
    D0 = dur(raw); D = dur(st); k_t = D / D0                      # 늘어난 비율 (≈1/0.95)
    S0 = silences(raw, -40, 0.08); S = silences(st, -40, 0.08)
    per = char_times(raw, lines)
    first = [min(p.values()) if p else None for p in per]; last = [max(p.values()) if p else None for p in per]
    # 줄 사이 경계: 원본에서 찾은 가장 긴 쉼 → 늘린 음성의 쉼으로 옮김
    bounds = []
    for k in range(len(lines) - 1):
        s0 = best_sil(S0, last[k] - 0.15, first[k + 1] + 0.15)
        mid = ((s0[0] + s0[1]) / 2 if s0 else (last[k] + first[k + 1]) / 2) * k_t
        s1 = best_sil(S, mid - 0.05, mid + 0.05)
        bounds.append(s1 if s1 else (mid, mid))
    head = S[0][1] if S and S[0][0] < 0.05 else 0.0
    tail = S[-1][0] if S and S[-1][1] > D - 0.05 else D
    import soundfile as sf
    x, sr = sf.read(st, dtype='float32'); assert sr == SR
    out = []
    gidx = sum(len(part_lines(j)) for j in range(1, i))
    for k, l in enumerate(lines):
        a = (bounds[k - 1][1] if k > 0 else head) - PRE
        b = (bounds[k][0] if k < len(lines) - 1 else tail) + POST
        a = max(0, a); b = min(D, b)
        if k > 0: a = max(a, (bounds[k - 1][0] + bounds[k - 1][1]) / 2)
        if k < len(lines) - 1: b = min(b, (bounds[k][0] + bounds[k][1]) / 2)
        sc, key, orig, read = R[gidx + k][:4]
        assert read.strip() == l.strip(), (i, k)
        seg = x[int(a * SR):int(b * SR)].copy()
        n = min(len(seg), int(0.01 * SR)); seg[:n] *= np.linspace(0, 1, n); seg[-n:] *= np.linspace(1, 0, n)
        os.makedirs(f'{HERE}/clips', exist_ok=True)
        sf.write(f'{HERE}/clips/{sc}_{key}.wav', seg, SR, subtype='FLOAT')
        d = len(seg) / SR
        # 자막 카드 나누기: 자막 문장의 ' | ' 위치 → 읽는 문장 위치 → 시각 → 가까운 쉼 한가운데
        sp = []; cap = CAP[(sc, key)]; parts = cap.split(' | ')
        if len(parts) > 1:
            rn = norm(read); rh_idx = [j for j, ch in enumerate(rn) if re.match('[가-힣]', ch)]
            rh = ''.join(rn[j] for j in rh_idx); ch_ = hang(cap.replace(' | ', ''))
            blocks = difflib.SequenceMatcher(None, ch_, rh, autojunk=False).get_matching_blocks()
            def c2r(ci):   # 자막 한글 위치 → 읽는 문장 한글 위치 (맞는 덩어리 기준, 없으면 가장 가까운 덩어리 끝)
                best = None
                for bl in blocks:
                    if bl.size == 0: continue
                    if bl.a <= ci < bl.a + bl.size: return bl.b + ci - bl.a
                    if bl.a + bl.size <= ci: best = bl.b + bl.size - 1 + (ci - (bl.a + bl.size - 1))
                return min(best if best is not None else ci, len(rh) - 1)
            pt = sorted(per[k].items())
            acc = ''
            for p in parts[:-1]:
                acc += p
                jn = rh_idx[c2r(len(hang(acc)) - 1)]                 # 앞 부분 마지막 글자 (norm 기준)
                if len(pt) >= 2: t = float(np.interp(jn + 0.5, [q for q, _ in pt], [v for _, v in pt]))
                else: t = first[k] + (last[k] - first[k]) * jn / len(rn)
                t *= k_t
                # 그 근처의 문장 안 쉼 (조각 안쪽만)
                cand = [(x0, x1) for x0, x1 in S if x1 > t - 0.6 and x0 < t + 0.6 and x0 > a + 0.3 and x1 < b - 0.3]
                s1 = min(cand, key=lambda s: abs((s[0] + s[1]) / 2 - t)) if cand else None
                ts = (s1[0] + s1[1]) / 2 if s1 else t
                sp.append(round(ts - a, 3))
                print(f'    split {sc}_{key}: est {t - a:.2f} → {ts - a:.2f} sil {round(s1[1] - s1[0], 2) if s1 else None}  …{read[max(0, len(read) * 0):][:0]}{rh[max(0, c2r(len(hang(acc)) - 1) - 3):c2r(len(hang(acc)) - 1) + 1]}|')
        out.append(dict(sc=sc, k=key, d=round(d, 3), sp=sp, a=round(a, 3), b=round(b, 3),
                        cov=round(len(per[k]) / max(1, len(norm(l))), 2)))
    return out, D

if __name__ == '__main__':
    parts = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4, 5, 6]
    allv = json.load(open(f'{HERE}/vo.json')) if os.path.exists(f'{HERE}/vo.json') else {}
    for i in parts:
        out, D = run(i)
        allv[str(i)] = out
        print(f'p{i}: {D:.2f}s')
        for o in out: print(f"  {o['sc']:15s} {o['k']} {o['d']:6.2f}  [{o['a']:7.2f}-{o['b']:7.2f}] cov{o['cov']:.2f} sp{o['sp']}")
    json.dump(allv, open(f'{HERE}/vo.json', 'w'), ensure_ascii=False, indent=0)
    VO = {}
    for i in sorted(allv, key=int):
        for o in allv[i]: VO.setdefault(o['sc'], {})[o['k']] = dict(d=o['d'], sp=o['sp'])
    open(f'{VID}/vo_data.js', 'w').write('// 내레이션 실제 길이 (build_vo.py 가 만듦)\nwindow.VO=' + json.dumps(VO, ensure_ascii=False) + ';\n')
    print('lines', sum(len(v) for v in VO.values()))
