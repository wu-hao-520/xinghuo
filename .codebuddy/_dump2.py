# -*- coding: utf-8 -*-
import zipfile
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'

def dump(path, label):
    print('#' * 70)
    print('FILE:', label)
    z = zipfile.ZipFile(path)
    root = etree.fromstring(z.read('word/document.xml'))
    body = root.find('{%s}body' % W)
    def ptext(p):
        out = []
        for t in p.iter('{%s}t' % W):
            if t.text: out.append(t.text)
        for t in p.iter('{%s}t' % M):
            if t.text: out.append('[M:' + t.text + ']')
        for b in p.iter('{%s}blip' % A):
            out.append('[IMG]')
        return ''.join(out)
    n = 0
    for p in body.iter('{%s}p' % W):
        txt = ptext(p).strip()
        if txt:
            n += 1
            print(f'{n:2d}. {txt[:150]}')

dump(r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_公式验证.docx', '公式验证.docx')
