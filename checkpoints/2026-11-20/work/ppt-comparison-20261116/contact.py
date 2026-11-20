from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

root = Path(__file__).parent
for folder in root.iterdir():
    if not folder.is_dir():
        continue
    slides = sorted(folder.glob('slide-*.png'))
    for start in range(0, len(slides), 8):
        batch = slides[start:start + 8]
        sheet = Image.new('RGB', (1280, 390 * ((len(batch) + 1) // 2)), '#dddddd')
        draw = ImageDraw.Draw(sheet)
        for i, path in enumerate(batch):
            x, y = i % 2 * 640, i // 2 * 390
            with Image.open(path) as source:
                thumb = ImageOps.contain(source, (640, 360))
                sheet.paste(thumb, (x, y + 25))
            draw.text((x + 12, y + 5), str(start + i + 1), fill='black')
        sheet.save(folder / f'contact-{start // 8 + 1}.jpg')
