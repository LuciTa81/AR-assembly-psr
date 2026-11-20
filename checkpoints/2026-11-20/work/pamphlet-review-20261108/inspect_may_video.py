import json
import hashlib
import struct
import sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import cv2
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding='utf-8')

source = Path('C:/Users/fresh/OneDrive/Desktop/홍익대/4학년/1학기/Ather수업들/졸업프로젝트1/최종발표')
output = Path('C:/Users/fresh/Documents/Codex/pamphlet-review-20261108/may-video-review')
output.mkdir(exist_ok=True)
video_bytes = (source / 'KakaoTalk_20260520_214158270.mp4').read_bytes()
handlers = []
def read_boxes(data):
    offset = 0
    while offset + 8 <= len(data):
        size, kind = struct.unpack_from('>I4s', data, offset)
        header = 8
        if size == 1:
            size = struct.unpack_from('>Q', data, offset + 8)[0]
            header = 16
        elif size == 0:
            size = len(data) - offset
        if size < header or offset + size > len(data):
            raise ValueError('Invalid MP4 box size')
        payload = data[offset + header:offset + size]
        if kind in [b'moov', b'trak', b'mdia']:
            read_boxes(payload)
        elif kind == b'hdlr':
            handlers.append(payload[8:12].decode('ascii'))
        offset += size
read_boxes(video_bytes)
capture = cv2.VideoCapture(str(source / 'KakaoTalk_20260520_214158270.mp4'))
frames = []
timestamps = []
while True:
    ok, frame = capture.read()
    if not ok:
        break
    timestamps.append(capture.get(cv2.CAP_PROP_POS_MSEC) / 1000)
    frames.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
capture.release()
for start in range(0, len(frames), 20):
    sheet = Image.new('RGB', (2000, 1020), '#202020')
    draw = ImageDraw.Draw(sheet)
    for index in range(start, min(start + 20, len(frames))):
        x, y = ((index - start) % 5) * 400, ((index - start) // 5) * 255
        thumb = frames[index].copy()
        thumb.thumbnail((396, 220))
        sheet.paste(thumb, (x, y))
        draw.text((x + 8, y + 224), f'Frame {index:03d} | {timestamps[index]:.3f}s', fill='white')
    sheet.save(output / f'contact-{start // 20 + 1}.jpg', quality=95)
for index in [0, 16, 32, 48, 64, 80, 96, 112, 118]:
    frames[index].save(output / f'frame-{index:03d}.png')
ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
slides = []
with ZipFile(source / 'Assembly_C011207 최민준 .pptx') as archive:
    names = sorted([n for n in archive.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')],
                   key=lambda n: int(n.rsplit('slide', 1)[1].split('.')[0]))
    for name in names:
        root = ET.fromstring(archive.read(name))
        slides.append({'slide': name, 'text': [t.text for t in root.findall('.//a:t', ns) if t.text]})
    media = [{'name': i.filename, 'size': i.file_size} for i in archive.infolist() if i.filename.startswith('ppt/media/')]
    embedded_matches = hashlib.sha256(archive.read('ppt/media/media1.mp4')).digest() == hashlib.sha256(video_bytes).digest()
report = {'frame_count': len(frames), 'timestamps': timestamps, 'slides': slides, 'media': media,
          'mp4_track_handlers': handlers, 'matches_pptx_embedded_video': embedded_matches}
(output / 'inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'frame_count': len(frames), 'first_time': timestamps[0], 'last_time': timestamps[-1],
                  'track_handlers': handlers, 'matches_pptx_embedded_video': embedded_matches}, ensure_ascii=False))
