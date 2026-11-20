import asyncio, sys, subprocess, os
from playwright.async_api import async_playwright
HERE = '/home/claude/grad/vid1/'
async def main(mode, times=None, out=None, fps=30, dur=30.0):
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        pg = await b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        await pg.goto('file://' + HERE + 'scene_built.html'); await pg.evaluate('document.fonts.ready'); await pg.evaluate('window.ready')
        if mode == 'still':
            for t in times:
                await pg.evaluate(f'window.render({t})'); await pg.screenshot(path=HERE + f'still_{t:05.2f}.jpg', type='jpeg', quality=92)
        else:
            tmp = out + '.part.mp4'
            ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', str(fps), '-i', '-',
                                   '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', str(fps), '-movflags', '+faststart', tmp], stdin=subprocess.PIPE)
            n = int(round(dur * fps))
            for i in range(n):
                await pg.evaluate(f'window.render({i / fps})')
                ff.stdin.write(await pg.screenshot(type='jpeg', quality=92))
            ff.stdin.close(); rc = ff.wait()
            if rc == 0: os.replace(tmp, out); print('ok', out, n)
            else: print('ffmpeg failed', rc)
        await b.close()
if __name__ == '__main__':
    if sys.argv[1] == 'still': asyncio.run(main('still', [float(x) for x in sys.argv[2:]]))
    else: asyncio.run(main('film', out=sys.argv[2]))
