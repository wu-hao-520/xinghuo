# -*- coding: utf-8 -*-
"""dump 重新生成的 30 分钟练习 docx，检查公式/图片渲染。"""
import zipfile
from lxml import etree

OUT = r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_30分钟.docx'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
z = zipfile.ZipFile(OUT)
root = etree.fromstring(z.read('word/document.xml'))
body = root.find('{%s}body' % W)

def ptext(p):
    outl = []
    for t in p.iter('{%s}t' % W):
        if t.text:
            outl.append(t.text)
    for t in p.iter('{%s}t' % M):
        if t.text:
            outl.append('[M:' + t.text + ']')
    for b in p.iter('{%s}blip' % A):
        outl.append('[IMG]')
    return ''.join(outl)

n = 0
for p in body.iter('{%s}p' % W):
    txt = ptext(p).strip()
    if txt:
        n += 1
        print(f'{n:2d}. {txt[:170]}')
print('\n[IMG count]', sum(1 for _ in root.iter('{%s}blip' % A)))
