import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

SOURCE = Path('C:/Users/fresh/Downloads/B5 팜플렛 책자_최종.pdf')
OUT = Path(__file__).parent / 'yearbook-review'
OUT.mkdir(exist_ok=True)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
document = pdfium.PdfDocument(str(SOURCE))
records = []
for index in range(len(document)):
    page = document[index]
    width, height = page.get_size()
    text_page = page.get_textpage()
    text = text_page.get_text_range()
    text_page.close()
    image = page.render(scale=720/width).to_pil().convert('RGB')
    image.save(OUT / f'page-{index+1:03}.jpg', quality=88)
    records.append({'page': index+1, 'size_pt': [width,height], 'text': text})
    page.close()
    if (index+1) % 20 == 0:
        print(f'Rendered {index+1}/{len(document)}', flush=True)
document.close()
(OUT / 'page-index.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
for start in range(0, len(records), 9):
    sheet = Image.new('RGB', (1110, 1680), '#e5e5e5')
    draw = ImageDraw.Draw(sheet)
    for slot, record in enumerate(records[start:start+9]):
        x, y = slot%3*370, slot//3*560
        image = Image.open(OUT / f"page-{record['page']:03}.jpg")
        image.thumbnail((354,522))
        draw.text((x+10,y+5), f"PDF p.{record['page']}", font=font, fill='#111111')
        sheet.paste(image, (x+(370-image.width)//2, y+32))
    sheet.save(OUT / f'contact-{start+1:03}-{min(start+9,len(records)):03}.jpg',quality=92)
print(json.dumps({'pages':len(records),'pages_with_text':sum(bool(r['text'].strip()) for r in records),'contact_sheets':(len(records)+8)//9,'out':str(OUT)},ensure_ascii=False),flush=True)
