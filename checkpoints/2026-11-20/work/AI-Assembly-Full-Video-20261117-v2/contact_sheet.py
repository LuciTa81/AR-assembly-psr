"""Contact sheets for visual inspection of every revised scene."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent / 'preview'
files = sorted(root.glob('??-52.jpg'))
for start in range(0, len(files), 6):
    sheet = Image.new('RGB', (1920, 768), '#dddddd')
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(files[start:start+6]):
        x, y = i % 3 * 640, i // 3 * 384
        draw.text((x+8, y+4), path.stem, fill='black')
        with Image.open(path) as im:
            sheet.paste(im.resize((640, 360)), (x, y+24))
    sheet.save(root / f'contact-{start+1:02d}.jpg', quality=95)
