"""전체 영상 자막(SRT)과 장면별 대본을 만든다. 장면 길이는 실제 렌더 프레임 수로 맞춘다."""
import asyncio, json, os, subprocess
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
SC = [l.split("'")[1][:-4] for l in open(HERE + '/out/full.txt') if l.strip()]
def frames(n): return int(subprocess.check_output(['ffprobe','-v','error','-count_packets','-select_streams','v:0','-show_entries','stream=nb_read_packets','-of','csv=p=0',f'{HERE}/out/{n}.mp4']).strip())
def ts(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
async def main():
    out = []; off = 0.0; k = 1; script = []
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={'width': 1920, 'height': 1080})
        for n in SC:
            await pg.goto('file://' + f'{HERE}/scenes/{n}.html'); await pg.evaluate('document.fonts.ready')
            caps = await pg.evaluate('KIT.caps'); script.append((n, off, caps))
            for c in caps:
                out.append(f"{k}\n{ts(off + c['t0'])} --> {ts(off + c['t1'])}\n{c['text']}\n"); k += 1
            off += frames(n) / 30
        await b.close()
    open(f'{HERE}/out/AI Assembly Guide_영상_자막.srt', 'w', encoding='utf-8').write('\n'.join(out))
    json.dump([[n, o, c] for n, o, c in script], open(f'{HERE}/out/script.json', 'w'), ensure_ascii=False)
    print('srt', k - 1, 'lines, total', round(off, 2), 's')
asyncio.run(main())
