# -*- coding: utf-8 -*-
"""直接修复 docx 里错误的分数结构：<m:f> 下的 <m:e>（分子/分母）改名为 <m:num>/<m:den>。"""
import zipfile
from lxml import etree

M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
FILES = [
    r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_公式验证.docx',
    r'e:\codebuddy\workflow\student-profiles\exams\针对性练习_20260905_连可欣_物理_错题巩固.docx',
]


def fix_docx(path):
    zin = zipfile.ZipFile(path, 'r')
    names = zin.namelist()
    data = {n: zin.read(n) for n in names}
    zin.close()

    root = etree.fromstring(data['word/document.xml'])
    fixed = 0
    for f in root.iter('{%s}f' % M):
        children = list(f)
        locals_ = [etree.QName(c).localname for c in children]
        if 'num' in locals_ or 'den' in locals_:
            continue  # 已是正确结构
        e_children = [c for c in children if etree.QName(c).localname == 'e']
        if len(e_children) >= 2:
            e_children[0].tag = '{%s}num' % M
            e_children[1].tag = '{%s}den' % M
            fixed += 1

    data['word/document.xml'] = etree.tostring(
        root, xml_declaration=True, encoding='UTF-8', standalone=True
    )
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(n, data[n])
    print(f'[fixed {fixed} fracs] {path.split(chr(92))[-1]}')


if __name__ == '__main__':
    for p in FILES:
        fix_docx(p)
