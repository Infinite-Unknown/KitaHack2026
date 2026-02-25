import zipfile
import xml.etree.ElementTree as ET
import sys

def extract(p, o):
    try:
        docx = zipfile.ZipFile(p)
        tree = ET.XML(docx.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paras = [''.join([t.text for t in p.findall('.//w:t', ns) if t.text]) for p in tree.findall('.//w:p', ns)]
        with open(o, 'w', encoding='utf-8') as f:
            f.write('\n'.join([p for p in paras if p]))
    except Exception as e:
        print(f"Error extracting {p}: {e}")

extract(sys.argv[1], sys.argv[2])
extract(sys.argv[3], sys.argv[4])
