from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent
files = sorted((root / 'preview').glob('*-52.jpg'))
for batch in range(0, len(files), 6):
    canvas = Image.new('RGB', (1440, 588), '#cccccc')
    d = ImageDraw.Draw(canvas)
    for i, path in enumerate(files[batch:batch+6]):
        x, y = (i % 3) * 480, (i // 3) * 294
        d.text((x+8, y+4), path.stem, fill='black')
        canvas.paste(Image.open(path).resize((480,270)), (x,y+24))
    canvas.save(root / f'preview-contact-{batch+1:02d}.jpg', quality=95)
