# -*- coding: utf-8 -*-
"""临时验证：用修复后的 render_docx_practice 生成测试 docx 并 dump 关键段落。"""
import sys, os, json, zipfile
from lxml import etree

sys.path.insert(0, r'e:\codebuddy\workflow\.codebuddy\skills\exam-paper-analyzer\scripts')
from render_docx_practice import write_practice_docx

bank = r'e:\codebuddy\workflow\question-bank\_questions.json'
qs = json.load(open(bank, encoding='utf-8'))
# 取高考卷（含 ~ ^ 标记与图片的）题目验证
test_ids = ['Q-0013', 'Q-0016', 'Q-0017', 'Q-0018', 'Q-0020', 'Q-0023', 'Q-0024', 'Q-0025']
sel = [q for q in qs if q.get('id') in test_ids]
out = r'e:\codebuddy\workflow\.codebuddy\_test_fix.docx'
write_practice_docx(sel, out, title='公式修复验证')

# dump
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
z = zipfile.ZipFile(out)
root = etree.fromstring(z.read('word/document.xml'))
body = root.find('{%s}body' % W)

def ptext(p):
    outl = []
    for t in p.iter('{%s}t' % W):
        if t.text: outl.append(t.text)
    for t in p.iter('{%s}t' % M):
        if t.text: outl.append('[M:' + t.text + ']')
    for b in p.iter('{%s}blip' % A):
        outl.append('[IMG]')
    return ''.join(outl)

n = 0
for p in body.iter('{%s}p' % W):
    txt = ptext(p).strip()
    if txt:
        n += 1
        print(f'{n:2d}. {txt[:200]}')
print('\n[IMG count]', sum(1 for _ in root.iter('{%s}blip' % A)))
