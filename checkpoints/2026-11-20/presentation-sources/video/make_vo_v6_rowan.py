"""내레이션 트랙을 장면 시간표대로 놓고, 배경음악을 말소리 아래로 낮춰 섞는다.
먼저: 장면 렌더 → music/make_bgm.py (bgm.wav, layout.json)
python3 make_vo.py  →  out/vo.wav (내레이션만), out/mix.wav (내레이션 + 음악), out/vo_times.json
"""
import asyncio, json, os, subprocess, numpy as np, soundfile as sf
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); SR = 48000; FPS = 30
VO_LUFS = -16.0          # 내레이션 크기
BED_GAIN_DB = 0.0        # 말 없는 구간의 음악 (bgm.wav 는 약 -25 LUFS)
DUCK_DB = -8.0           # 말하는 동안 음악을 더 낮춤 (→ 약 -33 LUFS, 말소리보다 17 dB 아래)
MERGE = 1.2              # 이보다 짧은 말 사이 틈은 음악을 올리지 않음
ATK, PRE_DUCK, REL = 0.35, 0.30, 0.9

def lufs(x):
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', 'ebur128', '-f', 'null', '-'],
                       input=x.astype(np.float32).tobytes(), capture_output=True).stderr.decode()
    return float(p.split('Integrated loudness:')[1].split('I:')[1].split('LUFS')[0])

def proc(x, af):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-af', af, '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-'],
                       input=x.astype(np.float32).tobytes(), capture_output=True, check=True).stdout
    y = np.frombuffer(p, np.float32).copy(); return np.pad(y, (0, max(0, len(x) - len(y))))[:len(x)]

async def vo_times(L):
    out = []
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 1920, 'height': 1080})
        for n, off in L['offsets'].items():
            await pg.goto('file://' + f'{HERE}/scenes/{n}.html')
            vo = await pg.evaluate('KIT.vo'); d = await pg.evaluate('KIT.dur')
            assert abs(round(d * FPS) - L['frames'][n]) <= 1, (n, d, L['frames'][n])
            for v in vo: out.append(dict(sc=n, k=v['k'], t=off / FPS + v['t'], d=v['d']))
        await b.close()
    return out

def main():
    L = json.load(open(f'{HERE}/music/layout.json'))
    TOT = L['total_frames'] / FPS; N = int(round(TOT * SR))
    V = asyncio.run(vo_times(L))
    vo = np.zeros(N, np.float32)
    for v in V:
        x, sr = sf.read(f'{HERE}/tts/clips/{v["sc"]}_{v["k"]}.wav', dtype='float32'); assert sr == SR
        a = int(round(v['t'] * SR)); vo[a:a + len(x)] += x[:max(0, N - a)]
    vo = proc(vo, 'highpass=f=70,acompressor=threshold=0.1:ratio=2.5:attack=8:release=150:knee=4')   # 말소리 크기 고르게
    g = 10 ** ((VO_LUFS - lufs(vo)) / 20); vo *= g
    vo = proc(vo, 'alimiter=limit=0.84:attack=3:release=60:level=0')                              # 봉우리만 -1.5 dBFS 로
    # 음악 낮추기 곡선
    spans = sorted([(v['t'], v['t'] + v['d']) for v in V]); M = []
    for a, b in spans:
        if M and a - M[-1][1] < MERGE: M[-1][1] = max(M[-1][1], b)
        else: M.append([a, b])
    t = np.arange(N) / SR; duck = np.zeros(N, np.float32)
    for a, b in M:
        a0 = a - PRE_DUCK - ATK
        i0, i1, i2, i3 = [int(max(0, min(N, round(x * SR)))) for x in (a0, a - PRE_DUCK, b, b + REL)]
        duck[i0:i1] = np.maximum(duck[i0:i1], np.linspace(0, 1, i1 - i0) if i1 > i0 else 0)
        duck[i1:i2] = 1
        if i3 > i2: duck[i2:i3] = np.maximum(duck[i2:i3], 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, i3 - i2)))
    gain = 10 ** ((BED_GAIN_DB + DUCK_DB * duck) / 20)
    bgm, sr = sf.read(f'{HERE}/music/bgm.wav', dtype='float32'); assert sr == SR
    if len(bgm) < N: bgm = np.pad(bgm, ((0, N - len(bgm)), (0, 0)))
    bgm = bgm[:N] * gain[:, None]
    mix = bgm + vo[:, None]
    pk = np.abs(mix).max(); print('vo gain', round(20 * np.log10(g), 2), 'dB  vo LUFS', round(lufs(vo), 1), 'vo peak', round(20 * np.log10(np.abs(vo).max()), 2), ' mix peak', round(20 * np.log10(pk), 2), 'dBFS')
    if pk > 0.89: mix *= 0.89 / pk            # 넘치면 전체를 살짝 낮춤 (-1 dBFS)
    vpk = np.abs(vo).max()
    vo2 = np.repeat(vo[:, None], 2, 1) * (min(1, 0.89 / vpk))
    sf.write(f'{HERE}/out/vo.wav', vo2, SR, subtype='PCM_16'); sf.write(f'{HERE}/out/mix.wav', mix, SR, subtype='PCM_16')
    json.dump(dict(lines=V, duck=M), open(f'{HERE}/out/vo_times.json', 'w'), ensure_ascii=False, indent=0)
    print('lines', len(V), 'total', round(TOT, 3), 's', 'mix LUFS', round(lufs(mix.mean(1)), 1))

if __name__ == '__main__': main()
