# -*- coding: utf-8 -*-
"""dump docx 段落级内容，展示每段的文本 run 和 oMath 公式结构。"""
import sys, zipfile
from lxml import etree

path = r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_30分钟.docx'
z = zipfile.ZipFile(path)
xml = z.read('word/document.xml')
root = etree.fromstring(xml)

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'

def para_text(p):
    """返回段落纯文本（含公式的 m:t 文本），用于快速看内容。"""
    out = []
    for t in p.iter('{%s}t' % W):
        if t.text:
            out.append(t.text)
    for t in p.iter('{%s}t' % M):
        if t.text:
            out.append('[M:' + t.text + ']')
    # 图片
    for b in p.iter('{%s}blip' % 'http://schemas.openxmlformats.org/drawingml/2006/main'):
        out.append('[IMG]')
    return ''.join(out)

body = root.find('{%s}body' % W)
count = 0
for p in body.iter('{%s}p' % W):
    txt = para_text(p).strip()
    if txt:
        count += 1
        print(f'{count:2d}. {txt}')
