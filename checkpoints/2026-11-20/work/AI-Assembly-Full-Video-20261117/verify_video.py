"""Verify the encoded deliverable, narration timeline, and unchanged source."""
from pathlib import Path
import hashlib
import json
import subprocess
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
FF = Path('C:/Users/fresh/Documents/Codex/2026-08-29/new-chat-7/work/ffmpeg/ffmpeg-9.0.1-full_build/bin')
VIDEO = ROOT / 'AI-Assembly-Guide-Full-Motion-KO.mp4'
timing = json.loads((ROOT / 'timing.json').read_text(encoding='utf-8'))
source = json.loads((ROOT / 'source-manifest.json').read_text(encoding='utf-8'))
audio_checks = []
for scene in timing:
    with wave.open(scene['audio']) as wav:
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')
        duration = wav.getnframes() / wav.getframerate()
        peak = int(np.abs(samples.astype(np.int32)).max())
        assert wav.getframerate() == 48000
        assert abs(duration-scene['duration']) < .01
        assert 100 < peak < 32767
    previous_end = 0
    for part in scene['parts']:
        assert part['start'] >= previous_end - .05, (scene['slide'], 'overlapping speech')
        previous_end = part['start'] + part['duration']
    assert previous_end <= scene['duration'] + .05
    audio_checks.append(dict(slide=scene['slide'], duration=duration, peak=peak))
unchanged = hashlib.sha256(Path(source['source']).read_bytes()).hexdigest() == source['source_sha256']
assert unchanged
report = dict(source_unchanged=unchanged, audio=audio_checks)
if VIDEO.exists():
    probe = json.loads(subprocess.check_output([str(FF/'ffprobe.exe'), '-v', 'error', '-show_streams', '-show_format', '-show_chapters', '-of', 'json', str(VIDEO)]))
    v = next(s for s in probe['streams'] if s['codec_type']=='video')
    a = next(s for s in probe['streams'] if s['codec_type']=='audio')
    assert (v['width'],v['height'],v['r_frame_rate']) == (1920,1080,'30/1')
    assert a['codec_name']=='aac' and a['sample_rate']=='48000'
    assert len(probe['chapters']) == 19
    assert abs(float(probe['format']['duration'])-sum(s['duration'] for s in timing)) < .7
    decode = subprocess.run([str(FF/'ffmpeg.exe'), '-v','error','-i',str(VIDEO),'-f','null','NUL'], capture_output=True, text=True)
    assert decode.returncode==0 and not decode.stderr.strip(), decode.stderr
    report.update(duration=float(probe['format']['duration']), size=int(probe['format']['size']), decode_errors=decode.stderr, chapters=len(probe['chapters']), width=v['width'], height=v['height'])
    cap = cv2.VideoCapture(str(VIDEO))
    offset = 0
    frames = []
    for scene in timing:
        t=offset+scene['duration']*.72
        cap.set(cv2.CAP_PROP_POS_MSEC,t*1000)
        ok,frame=cap.read()
        assert ok
        assert frame.std()>15, (scene['slide'],'blank frame')
        img=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
        img.save(ROOT/'preview'/f"verified-{scene['slide']:02d}.jpg",quality=94)
        frames.append((scene['slide'],img))
        offset+=scene['duration']
    cap.release()
    for start in range(0,len(frames),6):
        sheet=Image.new('RGB',(1440,588),'#dddddd')
        d=ImageDraw.Draw(sheet)
        for i,(num,img) in enumerate(frames[start:start+6]):
            x,y=(i%3)*480,(i//3)*294
            d.text((x+8,y+4),f'Slide {num:02d}',fill='black')
            sheet.paste(img.resize((480,270)),(x,y+24))
        sheet.save(ROOT/'preview'/f'verified-contact-{start+1:02d}.jpg',quality=95)
(ROOT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='audio'},ensure_ascii=False),flush=True)
print(f'Validated {len(audio_checks)} audio tracks',flush=True)
