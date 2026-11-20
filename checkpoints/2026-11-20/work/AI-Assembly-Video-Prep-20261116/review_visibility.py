import json
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'recordings/20261116_030943_visibilitycheck'
cap = cv2.VideoCapture(str(root / 'unity-sbs.mp4'))
fps = cap.get(cv2.CAP_PROP_FPS)
rows = []
thumbs = []
start, end = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (42, 90)
for second in range(start, end):
    cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
    ok, frame = cap.read()
    if not ok:
        continue
    left = frame[:, :frame.shape[1] // 2]
    hsv = cv2.cvtColor(left, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, (85, 100, 100), (125, 255, 255))
    green = cv2.inRange(hsv, (35, 100, 100), (85, 255, 255))
    rows.append({'second': second, 'blue_pixels': int(cv2.countNonZero(blue)),
                 'green_pixels': int(cv2.countNonZero(green))})
    image = Image.fromarray(cv2.cvtColor(left, cv2.COLOR_BGR2RGB))
    if second % 2 == 0:
        image.thumbnail((480, 270))
        thumb = Image.new('RGB', (480, 294), '#222222')
        thumb.paste(image, (0, 24))
        ImageDraw.Draw(thumb).text((8, 5), str(second) + 's', fill='white')
        thumbs.append(thumb)
    Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(root / f'check-{second:02}.jpg', quality=92)
cap.release()
sheet = Image.new('RGB', (480 * 4, 294 * ((len(thumbs) + 3) // 4)), '#222222')
for index, thumb in enumerate(thumbs):
    sheet.paste(thumb, ((index % 4) * 480, (index // 4) * 294))
sheet.save(root / 'visibility-contact.jpg', quality=95)
(root / 'visibility-pixels.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(json.dumps(rows))
