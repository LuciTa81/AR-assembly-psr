from pathlib import Path
from PIL import Image, ImageDraw
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import json

root = Path(__file__).resolve().parent
source = Path('C:/Users/fresh/OneDrive/Desktop/회사/Claude/AI Assembly Guide_구조테스트_v14.pptx')
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
slides=[]
with ZipFile(source) as z:
    for i in range(1,20):
        xml=ET.fromstring(z.read(f'ppt/slides/slide{i}.xml'))
        shapes=[]
        for sp in xml.findall('.//p:sp',ns):
            text='\n'.join(''.join(p.itertext()) for p in [])
            text='\n'.join(''.join(t.text or '' for t in p.findall('.//a:t',ns)) for p in sp.findall('.//a:p',ns))
            if text.strip(): shapes.append(text)
        slides.append({'slide':i,'text':shapes})
for start in range(1,20,6):
    sheet=Image.new('RGB',(1440,870),'#cccccc')
    d=ImageDraw.Draw(sheet)
    for n,i in enumerate(range(start,min(20,start+6))):
        im=Image.open(root/'slides'/f'slide-{i:02}.png').convert('RGB').resize((720,405))
        x=(n%2)*720;y=(n//2)*290
        im=im.resize((496,279)) if False else im.resize((480,270))
        # Three columns at a readable contact-sheet scale.
        x=(n%3)*480;y=(n//3)*435
        sheet.paste(Image.open(root/'slides'/f'slide-{i:02}.png').convert('RGB').resize((480,270)),(x,y+24))
        d.text((x+8,y+6),str(i),fill='black')
    sheet.crop((0,0,1440,730)).save(root/f'contact-{start:02}.jpg',quality=94)
(root/'slide-text.json').write_text(json.dumps(slides,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(slides,ensure_ascii=False))
