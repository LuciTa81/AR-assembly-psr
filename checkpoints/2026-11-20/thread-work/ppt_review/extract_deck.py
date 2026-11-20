import json
import posixpath
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}

source, out = map(Path, sys.argv[1:3])
out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(source) as z:
    presentation = ET.fromstring(z.read('ppt/presentation.xml'))
    relations = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))
    targets = {r.get('Id'): r.get('Target') for r in relations}
    result = {'source': str(source), 'size': presentation.find('p:sldSz', NS).attrib, 'slides': []}
    for number, item in enumerate(presentation.findall('p:sldIdLst/p:sldId', NS), 1):
        path = posixpath.normpath(posixpath.join('ppt', targets[item.get('{'+NS['r']+'}id')]))
        root = ET.fromstring(z.read(path))
        slide = {'number': number, 'part': path, 'shapes': [], 'notes': [], 'media': []}
        for sp in root.findall('.//p:sp', NS):
            cnv = sp.find('p:nvSpPr/p:cNvPr', NS)
            paragraphs = []
            for p in sp.findall('.//a:p', NS):
                text = ''.join(t.text or '' for t in p.findall('.//a:t', NS))
                runs = []
                for r in p.findall('a:r', NS):
                    runs.append({'text': r.findtext('a:t', '', NS), 'style': ET.tostring(r.find('a:rPr', NS), encoding='unicode') if r.find('a:rPr', NS) is not None else ''})
                if text:
                    paragraphs.append({'text': text, 'runs': runs})
            if paragraphs:
                slide['shapes'].append({'name': cnv.get('name') if cnv is not None else '', 'paragraphs': paragraphs})
        relpath = posixpath.join(posixpath.dirname(path), '_rels', posixpath.basename(path)+'.rels')
        if relpath in z.namelist():
            for r in ET.fromstring(z.read(relpath)):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(path), r.get('Target')))
                kind = r.get('Type', '').split('/')[-1]
                if kind == 'notesSlide':
                    nr = ET.fromstring(z.read(target))
                    slide['notes'] = [t.text for t in nr.findall('.//a:t', NS) if t.text]
                if kind in ('image', 'video', 'audio', 'media'):
                    slide['media'].append({'type': kind, 'target': target})
        result['slides'].append(slide)
    (out/'deck.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = []
    for slide in result['slides']:
        lines.append('\n## SLIDE '+str(slide['number']))
        for shape in slide['shapes']:
            for para in shape['paragraphs']:
                lines.append(para['text'])
                red = [r['text'] for r in para['runs'] if any(c in r['style'].upper() for c in ('FF0000', 'E53935', 'FF3B30', 'C00000', 'EF4444', 'E74C3C', 'DC2626'))]
                if red:
                    lines.append('RED: '+' | '.join(red))
        lines.append('NOTES: '+'\n'.join(slide['notes']))
        lines.append('MEDIA: '+json.dumps(slide['media'], ensure_ascii=False))
    (out/'text.txt').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({'slides': len(result['slides']), 'out': str(out)}, ensure_ascii=False))
