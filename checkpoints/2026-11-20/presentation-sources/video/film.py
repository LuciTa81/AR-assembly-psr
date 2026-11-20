"""장면 HTML 을 1920x1080 30fps MP4 로 찍는다.
python3 film.py scenes/s02_motiv.html                 → out/s02_motiv.mp4
python3 film.py scenes/s02_motiv.html --still 3 9.5   → stills/s02_motiv_03.00.jpg ...
python3 film.py scenes/s02_motiv.html --dur           → 장면 길이와 자막 시간표 출력"""
import asyncio, sys, subprocess, os, json
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30

async def main(scene, mode, times, css=None):
    name = os.path.splitext(os.path.basename(scene))[0]
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('file://' + os.path.abspath(scene))
        if css: await pg.add_style_tag(path=css)
        await pg.evaluate('KIT.ready()')
        dur = await pg.evaluate('KIT.dur')
        if errs: print('PAGE ERRORS:', errs)
        if mode == 'dur':
            caps = await pg.evaluate('KIT.caps')
            print(f'{name}: {dur:.2f}s')
            for c in caps: print(f"  {c['t0']:6.2f}-{c['t1']:6.2f}  {c['text']}")
        elif mode == 'still':
            os.makedirs(HERE + '/stills', exist_ok=True)
            for t in times:
                await pg.evaluate(f'window.render({t})')
                await pg.screenshot(path=f'{HERE}/stills/{name}_{t:05.2f}' + (('_' + os.path.basename(css)[:-4]) if css and '--css' in sys.argv else '') + '.jpg', type='jpeg', quality=92)
            print('stills', name, times, f'(dur {dur:.2f})')
        else:
            out = f'{HERE}/out/{name}.mp4'; tmp = out[:-4] + '.part.mp4'
            ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', str(FPS), '-i', '-',
                                   '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', str(FPS), tmp], stdin=subprocess.PIPE)
            n = int(round(dur * FPS))
            for i in range(n):
                await pg.evaluate(f'window.render({i / FPS})')
                ff.stdin.write(await pg.screenshot(type='jpeg', quality=92))
            ff.stdin.close(); rc = ff.wait()
            if rc == 0: os.replace(tmp, out); print('ok', out, n, 'frames', f'{dur:.2f}s')
            else: print('ffmpeg failed', rc)
        await b.close()

if __name__ == '__main__':
    a = sys.argv[1:]; css = None
    # 기본 배경 테마: theme.txt 한 줄 (themes/<이름>.css). --css 로 바꿔 볼 수 있다
    tf = os.path.join(HERE, 'theme.txt')
    if os.path.exists(tf):
        nm = open(tf).read().strip()
        if nm and os.path.exists(os.path.join(HERE, 'themes', nm + '.css')): css = os.path.join(HERE, 'themes', nm + '.css')
    if '--css' in a: i = a.index('--css'); css = a[i + 1]; del a[i:i + 2]
    if '--still' in a: asyncio.run(main(a[0], 'still', [float(x) for x in a[a.index('--still') + 1:]], css))
    elif '--dur' in a: asyncio.run(main(a[0], 'dur', [], css))
    else: asyncio.run(main(a[0], 'film', [], css))
