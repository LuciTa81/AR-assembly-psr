from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import json

ROOT=Path(__file__).resolve().parent
PPT=Path('C:/Users/fresh/OneDrive/Desktop/회사/Claude/AI Assembly Guide_구조테스트_v14.pptx')
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}

def get_shapes():
    result={}
    with ZipFile(PPT) as z:
        p=ET.fromstring(z.read('ppt/presentation.xml')).find('p:sldSz',NS)
        sx,sy=1920/int(p.attrib['cx']),1080/int(p.attrib['cy'])
        for i in range(1,20):
            xml=ET.fromstring(z.read(f'ppt/slides/slide{i}.xml'))
            shapes=[]
            for sp in xml.findall('.//p:sp',NS):
                text='\n'.join(''.join(t.text or '' for t in p.findall('.//a:t',NS)) for p in sp.findall('.//a:p',NS))
                tr=sp.find('p:spPr/a:xfrm',NS)
                if not text.strip() or tr is None:continue
                off,ext=tr.find('a:off',NS),tr.find('a:ext',NS)
                if off is None or ext is None:continue
                box=[round(int(off.attrib['x'])*sx),round(int(off.attrib['y'])*sy),round(int(ext.attrib['cx'])*sx),round(int(ext.attrib['cy'])*sy)]
                r=sp.find('.//a:rPr',NS)
                shapes.append(dict(text=text,box=box,size=r.attrib.get('sz') if r is not None else None))
            result[i]=shapes
    return result

if __name__=='__main__':
    s=get_shapes()
    (ROOT/'shapes.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
    for i in (9,10,16,17,18):
        print(i)
        for sp in s[i]:print(sp['box'],sp['text'].replace('\n',' / '))
