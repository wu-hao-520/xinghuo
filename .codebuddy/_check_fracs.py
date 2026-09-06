# -*- coding: utf-8 -*-
"""检查各 docx 里 m:f 分数结构是否正确（应为 m:num + m:den，而不是 m:e + m:e）。"""
import os, zipfile, glob
from lxml import etree

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
base = r'e:\codebuddy\workflow\student-profiles'
for path in glob.glob(base + r'\**\*.docx', recursive=True):
    try:
        z = zipfile.ZipFile(path)
        root = etree.fromstring(z.read('word/document.xml'))
    except Exception as e:
        print(f'{path}: ERR {e}')
        continue
    fs = list(root.iter('{%s}f' % M))
    bad = 0
    for f in fs:
        children = [etree.QName(c).localname for c in f]
        # 有效子元素应含 num 和 den
        if 'num' not in children or 'den' not in children:
            bad += 1
    status = 'OK' if bad == 0 else f'BAD({bad}/{len(fs)})'
    print(f'{status}  m:f={len(fs):3d}  {os.path.basename(path)}')
