# -*- coding: utf-8 -*-
"""dump 第3题 C/D 选项的完整 OMML XML。"""
import zipfile
from lxml import etree

path = r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_30分钟.docx'
z = zipfile.ZipFile(path)
xml = z.read('word/document.xml')
root = etree.fromstring(xml)

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'

def para_text(p):
    out = []
    for t in p.iter('{%s}t' % W):
        if t.text:
            out.append(t.text)
    return ''.join(out)

body = root.find('{%s}body' % W)
paras = list(body.iter('{%s}p' % W))
for i, p in enumerate(paras):
    txt = para_text(p).strip()
    if txt.startswith('C.第k次加速') or txt.startswith('D.第k次加速'):
        print('=' * 60)
        print('段落文本:', txt)
        # 打印该段落的 oMath XML
        for om in p.findall('{%s}oMath' % M):
            print(etree.tostring(om, encoding='unicode', pretty_print=True))
        break
