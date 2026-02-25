import zipfile
import xml.etree.ElementTree as ET

def read_docx(path):
    with zipfile.ZipFile(path) as docx:
        tree = ET.XML(docx.read('word/document.xml').decode('utf-8'))
        return ''.join(node.text for node in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text)

with open('extracted_text.txt', 'w', encoding='utf-8') as f:
    f.write('--- INFO PACK ---\n')
    f.write(read_docx(r'C:\Users\jiahe\OneDrive\Desktop\Programming Stuff\KitaHack\KitaHack Info\KitaHack 2026 Participants Info Pack.docx'))
    f.write('\n\n--- JUDGING CRITERIA ---\n')
    f.write(read_docx(r'C:\Users\jiahe\OneDrive\Desktop\Programming Stuff\KitaHack\KitaHack Info\Kitahack 2026 Prelim Judging Criteria.docx'))
