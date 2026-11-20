"""Record only the local camera preview and named Unity window, never the desktop."""
import argparse
import datetime
import json
import math
from pathlib import Path
import subprocess
import threading
import time
import urllib.request

FFMPEG = Path('C:/Users/fresh/Documents/Codex/2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin/ffmpeg.exe')
ROOT = Path(__file__).parent / 'recordings'
BASE = 'http://127.0.0.1:8764'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=10)
    parser.add_argument('--label', default='check')
    parser.add_argument('--base-url', default=BASE)
    args = parser.parse_args()
    from urllib.parse import urlparse
    base = args.base_url.rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path or parsed.query or parsed.fragment or parsed.username:
        parser.error('Recording source must be a local loopback HTTP server.')
    if not 1 <= args.seconds <= 600 or not args.label.replace('-', '').isalnum():
        parser.error('Duration must be 1..600 seconds; label must be alphanumeric.')
    folder = ROOT / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + args.label)
    folder.mkdir(parents=True, exist_ok=False)
    latest, lock, stopped = {}, threading.Lock(), threading.Event()
    errors = []

    def fetch(key, endpoint, period):
        while not stopped.is_set():
            try:
                with urllib.request.urlopen(base + endpoint, timeout=2) as response:
                    value = response.read()
                if key == 'state':
                    value = json.loads(value)
                elif not value.startswith(b'\xff\xd8'):
                    raise ValueError('Expected JPEG preview')
                with lock:
                    latest[key] = (time.monotonic(), value)
            except Exception as exc:
                with lock:
                    if len(errors) < 100:
                        errors.append({'time': time.time(), 'source': key, 'error': str(exc)})
            stopped.wait(period)

    workers = [threading.Thread(target=fetch, args=('jpeg', '/frame.jpg', .08), daemon=True),
               threading.Thread(target=fetch, args=('state', '/state.json', .1), daemon=True)]
    for worker in workers:
        worker.start()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with lock:
            ready = 'jpeg' in latest and 'state' in latest
        if ready:
            break
        time.sleep(.05)
    else:
        stopped.set()
        raise RuntimeError('No live camera preview and state; no recording started.')

    common = [str(FFMPEG), '-hide_banner', '-loglevel', 'warning', '-n']
    encode = ['-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
    procs = []
    frames = 0
    start = time.monotonic()
    wall_start = time.time()
    unity_offset = None
    try:
        with (folder / 'unity-encoder.log').open('wb') as ulog, (folder / 'camera-encoder.log').open('wb') as clog, (folder / 'states.jsonl').open('w', encoding='utf-8') as log:
            unity_offset = time.monotonic() - start
            # GDI can return a frozen surface for Unity's GPU-rendered window.
            unity = subprocess.Popen(common + ['-f', 'lavfi', '-i', "gfxcapture=window_title=^Beast Assembly Guide$:window_exe='^BeastAssemblyGuide[.]exe$':capture_cursor=0:max_framerate=30", '-t', str(args.seconds), '-vf', 'hwdownload,format=bgra,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-r', '30'] + encode + [str(folder / 'unity-sbs.mp4')], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=ulog, creationflags=subprocess.CREATE_NO_WINDOW)
            procs.append(unity)
            camera = subprocess.Popen(common + ['-f', 'image2pipe', '-framerate', '10', '-vcodec', 'mjpeg', '-i', 'pipe:0'] + encode + [str(folder / 'camera-preview.mp4')], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=clog, creationflags=subprocess.CREATE_NO_WINDOW)
            procs.append(camera)
            print(json.dumps({'event': 'recording', 'folder': str(folder), 'seconds': args.seconds, 'wall_start': wall_start}), flush=True)
            while frames < args.seconds * 10 and not (folder / 'stop').exists():
                if unity.poll() is not None and unity.returncode != 0:
                    raise RuntimeError('Unity window capture failed; inspect unity-encoder.log.')
                wait = start + frames / 10 - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                with lock:
                    jpeg_time, jpeg = latest['jpeg']
                    state_time, state = latest['state']
                now = time.monotonic()
                camera.stdin.write(jpeg)
                log.write(json.dumps({'video_frame': frames, 'video_seconds': frames / 10, 'elapsed_seconds': now - start, 'camera_fetch_age_ms': round((now - jpeg_time) * 1000), 'state_fetch_age_ms': round((now - state_time) * 1000), 'state': state}, ensure_ascii=False) + '\n')
                frames += 1
                if frames % 100 == 0:
                    log.flush()
                    print(json.dumps({'event': 'progress', 'seconds': frames / 10, 'stage': state.get('current_state'), 'phase': state.get('guidance', {}).get('phase'), 'markers': state.get('marker_count')}), flush=True)
            camera.stdin.close()
            camera.wait(timeout=30)
            if frames < args.seconds * 10 and unity.poll() is None:
                unity.stdin.write(b'q\n')
                unity.stdin.flush()
            unity.wait(timeout=args.seconds + 30)
    finally:
        stopped.set()
        for process in procs:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        result = {'folder': str(folder), 'frames': frames, 'duration_seconds': frames / 10,
                  'wall_start': wall_start, 'unity_launch_offset_seconds': unity_offset,
                  'return_codes': [p.returncode for p in procs], 'errors': errors,
                  'source': 'camera preview and Unity window; not optical through-lens footage',
                  'unity_capture': 'Windows Graphics Capture; exact Unity title and executable only',
                  'synchronization': 'host timestamps; camera preview and state are fetched separately'}
        (folder / 'recording.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False), flush=True)
    if len(procs) != 2 or any(p.returncode for p in procs):
        raise RuntimeError('An encoder failed; inspect encoder logs.')


if __name__ == '__main__':
    main()
