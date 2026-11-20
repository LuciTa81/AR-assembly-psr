"""Render the same recorded pose in both players; no camera or stage control."""
import copy
import json
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
from server.realtime.workspace_live_preview import load_profiles
from server.realtime.workspace_projection import estimate_pose

ROOT = Path('C:/Users/fresh/Documents/Codex')
OUT = ROOT / 'beast-line-clip-20261116'
source = ROOT / 'AI-Assembly-Video-Prep-20261116/recordings/20261116_030943_visibilitycheck/states.jsonl'
rows = [json.loads(x) for x in source.read_text(encoding='utf-8-sig').splitlines()]
row = next(x for x in rows if 54 <= x['video_seconds'] < 56 and x['state']['extra']['presentation_pose'] == 'tracking')
state = row['state']
d = state['extra']['presentation_diagnostics']
presentation = json.loads((ROOT / 'beast-pose-continuation-20261116/presentation-rms32.json').read_text(encoding='utf-8-sig'))
camera, workspace, binding = load_profiles(presentation['camera_profile'], presentation['workspace_profile'])
pose = estimate_pose({int(k): v for k, v in d['detected_corners_px'].items()}, workspace, camera, d['image_size'], max_rms_px=3.2, max_point_error_px=5.)
rotation = cv2.Rodrigues(pose.rvec)[0]
config = json.loads(Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/display_correspondence/7049e2a9cb59491fa52c882bc7162a72/client-config.json').read_text(encoding='utf-8-sig'))
session_dir = Path(config['directory']).parent / ('render-check-' + uuid.uuid4().hex)
session_dir.mkdir()
config.update(session_id='offline-render-check', directory=str(session_dir), token=uuid.uuid4().hex)
state['session_id'] = config['session_id']
world = np.array(workspace.targets['A'])
xyz = rotation @ world + pose.tvec.reshape(3)
observation = {k: config[k] for k in ('session_id', 'camera_profile_id', 'camera_profile_sha256', 'workspace_profile_id', 'workspace_profile_sha256', 'image_size', 'target_id')}
observation.update(schema_version='beast_display_observation_v1', status='tracking', reason='', reason_code='tracking',
    marker_ids=d['marker_ids'], marker_count=d['marker_count'], age_ms=0, rms_px=float(d['rms_px']), max_error_px=5.,
    rvec=pose.rvec.reshape(3).tolist(), tvec_mm=pose.tvec.reshape(3).tolist(), world_xyz_mm=world.tolist(),
    camera_xyz_mm=xyz.tolist(), target_pixel=[640, 360], camera_targets=[{'target_id': k, 'camera_xyz_mm': (rotation @ np.array(v) + pose.tvec.reshape(3)).tolist()} for k, v in workspace.targets.items()])
start = time.monotonic()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = copy.deepcopy(observation if self.path == '/observation' else state)
        payload['frame_id'] = 10000 + int((time.monotonic() - start) * 10)
        payload['timestamp_ms'] = int(time.monotonic() * 1000)
        payload['frame_age_ms'] = 0
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
url = f'http://127.0.0.1:{server.server_port}'
config['observation_url'] = url + '/observation'
config_path = session_dir / 'client-config.json'
config_path.write_text(json.dumps(config), encoding='utf-8')
threading.Thread(target=server.serve_forever, daemon=True).start()
ffmpeg = ROOT / '2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin/ffmpeg.exe'
results = {}
try:
    for label, folder in [('before', ROOT / 'beast-action-guide-20261115/player-v2'), ('after', OUT / 'player')]:
        args = [str(folder / 'BeastAssemblyGuide.exe'), '--display-name', 'VITURE', '--sbs-guidance', '--action-korean',
            '--candidate-presentation', '--stage-targets', '--stage-context', '--state-url', url + '/state.json',
            '--display-observation-config', str(config_path), '--candidate-projection', str(ROOT / 'beast-reference-return-20261114/candidate-ABCD-joint-unverified.json'),
            '--box-outline-config', str(ROOT / 'beast-reference-return-20261114/rounded-box-124mm.json'), '-logFile', str(OUT / (label + '.log'))]
        player = subprocess.Popen(args)
        try:
            for _ in range(60):
                time.sleep(.5)
                log = OUT / (label + '.log')
                if log.exists() and 'gate=VISIBLE' in log.read_text(encoding='utf-8', errors='replace'):
                    break
            else:
                raise RuntimeError('No visible replay: ' + label)
            time.sleep(2)
            subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                "gfxcapture=window_title='Beast Assembly Guide':window_exe='BeastAssemblyGuide':capture_cursor=0:max_framerate=30",
                '-vf', 'hwdownload,format=bgra', '-frames:v', '1', '-update', '1', '-y', str(OUT / (label + '.png'))], check=True, timeout=20)
            pixels = cv2.imread(str(OUT / (label + '.png')))
            # The missing lower-left horizontal segment from the original recording.
            strip = pixels[550:630, 900:1100]
            mask = (strip[:, :, 1] > 60) & (strip[:, :, 1].astype(int) > strip[:, :, 2].astype(int) + 15)
            results[label] = {'edge_columns': int(np.any(mask, axis=0).sum()), 'image_size': list(pixels.shape[:2])}
        finally:
            player.terminate()
            player.wait(timeout=10)
            time.sleep(1)
finally:
    server.shutdown()
print(json.dumps(results, indent=2))
(OUT / 'render-verification.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
assert results['before']['edge_columns'] < 100, 'The stored clipping regression was not reproduced'
assert results['after']['edge_columns'] >= 190, 'The candidate still clips the lower-left edge'
