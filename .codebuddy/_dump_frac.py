# -*- coding: utf-8 -*-
import zipfile
from lxml import etree

OUT = r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_30分钟.docx'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
z = zipfile.ZipFile(OUT)
root = etree.fromstring(z.read('word/document.xml'))
fs = list(root.iter('{%s}f' % M))
print('total m:f =', len(fs))
for f in fs[:3]:
    print('=' * 60)
    print(etree.tostring(f, pretty_print=True).decode())
