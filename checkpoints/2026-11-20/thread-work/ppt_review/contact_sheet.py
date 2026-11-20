from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import re
import sys

folder = Path(sys.argv[1])
files = sorted(folder.glob('*.PNG'), key=lambda p: int(re.search(r'\d+', p.stem).group()))
for start in range(0, len(files), 6):
    sheet = Image.new('RGB', (1600, 1440), '#d4d4d4')
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(files[start:start+6]):
        x, y = (index % 2)*800, (index//2)*480
        im = ImageOps.contain(Image.open(path).convert('RGB'), (780, 440))
        sheet.paste(im, (x+10, y+30))
        draw.text((x+12,y+10), 'SLIDE '+str(start+index+1), fill='black')
    dest = folder.parent / ('contact-'+str(start//6+1)+'.jpg')
    sheet.save(dest, quality=93)
    print(dest)
