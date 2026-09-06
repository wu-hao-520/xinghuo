# -*- coding: utf-8 -*-
"""dump 另两个受影响的 docx 的标题与题目结构，判断题目来源。"""
import zipfile
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'

for path in [
    r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_公式验证.docx',
    r'e:\codebuddy\workflow\student-profiles\exams\针对性练习_20260905_连可欣_物理_错题巩固.docx',
]:
    print('#' * 70)
    print('FILE:', path.split('\\')[-1])
    z = zipfile.ZipFile(path)
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
            if n <= 40:
                print(f'{n:2d}. {txt[:120]}')
    print('... total paras:', n)
    print('[IMG count]', sum(1 for _ in root.iter('{%s}blip' % A)))
