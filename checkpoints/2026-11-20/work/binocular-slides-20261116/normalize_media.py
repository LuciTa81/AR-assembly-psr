from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as ET

root = Path(__file__).parent
source = root / 'build/merged-candidate.pptx'
target = root / 'build/validated-candidate.pptx'
rel = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
tag = '{http://schemas.openxmlformats.org/drawingml/2006/main}hlinkClick'
changed = 0
with ZipFile(source) as zin, ZipFile(target, 'w', ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.startswith('ppt/slides/slide') and item.filename.endswith('.xml'):
            xml = ET.fromstring(data)
            edited = False
            for element in xml.iter(tag):
                # Media playback is defined by action and the picture's media relationship.
                # An empty external hyperlink id is redundant, not a missing video.
                if element.get('action') == 'ppaction://media' and element.get(rel + 'id') == '':
                    del element.attrib[rel + 'id']
                    edited = True
                    changed += 1
            if edited:
                data = ET.tostring(xml, xml_declaration=True, encoding='UTF-8', standalone=True)
        zout.writestr(item, data)
assert changed == 1, changed
print('Normalized one empty media hyperlink id; media and playback action retained.')
