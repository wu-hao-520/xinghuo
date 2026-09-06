# -*- coding: utf-8 -*-
"""题库 → Word 练习生成器（完整公式渲染版）。"""
import os, re
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

BROKEN_LATEX_REPAIRS = {
    '\x0crac': r'\frac',   # \frac 被 Python/JSON 转义成 form-feed + rac
    '\x07ngle': r'\angle', # \angle 被转义成 bell + ngle
    '\x08ar': r'\bar',     # \bar 被转义成 backspace + ar
    '\text': r'\text',     # \text 被转义成 tab + ext
    '\n:eq': r'\neq',      # \neq 被转义成 newline + :eq
    '\neq': r'\ne',        # \ne 被转义成 newline + e
}


def normalize_question_text(text):
    """修复题库/中间题包中被转义破坏的 LaTeX，并剔除不可见控制字符。"""
    if text is None:
        return ''
    text = str(text)
    for bad, good in BROKEN_LATEX_REPAIRS.items():
        text = text.replace(bad, good)
    return ''.join(ch for ch in text if ch in '\t\n\r' or ord(ch) >= 32)

sys_dir = os.path.dirname(os.path.abspath(__file__))
sys_path_local = sys_dir
import sys as _sys
if _sys.path[0] != sys_path_local:
    _sys.path.insert(0, sys_path_local)
from latex2omml import latex_to_omath

def _mr2(text):
    r = OxmlElement('m:r')
    rpr = OxmlElement('m:rPr')
    sty = OxmlElement('m:sty'); sty.set(qn('m:val'), 'p'); rpr.append(sty)
    r.append(rpr)
    t = OxmlElement('m:t'); t.text = text; t.set(qn('xml:space'), 'preserve')
    r.append(t)
    return r

def _sSup2(base, sup):
    s = OxmlElement('m:sSup')
    e = OxmlElement('m:e'); e.append(_mr2(base)); s.append(e)
    sp = OxmlElement('m:sup'); sp.append(_mr2(sup)); s.append(sp)
    return s

def _sSub2(base, sub):
    s = OxmlElement('m:sSub')
    e = OxmlElement('m:e'); e.append(_mr2(base)); s.append(e)
    sb = OxmlElement('m:sub'); sb.append(_mr2(sub)); s.append(sb)
    return s

def _sSup_nodes(base_nodes, sup):
    s = OxmlElement('m:sSup')
    e = OxmlElement('m:e')
    for n in base_nodes:
        e.append(n)
    s.append(e)
    sp = OxmlElement('m:sup'); sp.append(_mr2(sup)); s.append(sp)
    return s

def _sSub_nodes(base_nodes, sub):
    s = OxmlElement('m:sSub')
    e = OxmlElement('m:e')
    for n in base_nodes:
        e.append(n)
    s.append(e)
    sb = OxmlElement('m:sub'); sb.append(_mr2(sub)); s.append(sb)
    return s

def _add_simple_formula(p, text, size=10.5):
    """把 ~x~/^x^ 标记文本写入段落：普通文字走 w:r，上下标走 OMML。"""
    nodes = []  # 元素列表：('t', 文本) 或 ('m', oMath 节点)
    buf = ''
    def flush_text():
        nonlocal buf
        if buf:
            nodes.append(('t', buf))
            buf = ''
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        kind = None
        j = -1
        if ch == '~':
            j = text.find('~', i + 1)
            if j > i + 1:
                kind = 'sub'
        elif ch == '^':
            j = text.find('^', i + 1)
            if j > i + 1:
                kind = 'sup'
        if kind:
            val = text[i + 1:j]
            base_char = buf[-1] if buf else ''
            if buf[:-1]:
                nodes.append(('t', buf[:-1]))
            buf = ''
            if base_char:
                base_nodes = [_mr2(base_char)]
            elif nodes and nodes[-1][0] == 'm':
                base_nodes = [nodes.pop()[1]]
            else:
                base_nodes = [_mr2('')]
            if kind == 'sub':
                nodes.append(('m', _sSub_nodes(base_nodes, val)))
            else:
                nodes.append(('m', _sSup_nodes(base_nodes, val)))
            i = j + 1
            continue
        buf += ch
        i += 1
    flush_text()
    for kind, val in nodes:
        if kind == 't':
            r = p.add_run(val)
            r.font.name = '微软雅黑'
            r.font.size = Pt(size)
            r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        else:
            p._p.append(val)

def add_formula_mixed(p, text, size=10.5):
    """把含 $LaTeX$ + ~x~/^x^ 标记的混合文本写入段落 p。"""
    text = normalize_question_text(text)
    parts = re.split(r'(\$[^$]+\$)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith('$') and part.endswith('$') and len(part) > 2:
            latex_to_omath(p, part[1:-1])
        else:
            _add_simple_formula(p, part, size=size)

NAVY = (0x1F, 0x4E, 0x79)
GRAY = (0x59, 0x59, 0x59)

def set_run(r, size=10.5, bold=False, color=None):
    r.font.name = '微软雅黑'
    r.font.size = Pt(size)
    r.font.bold = bold
    r._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if color:
        r.font.color.rgb = RGBColor(*color)

def add_text(p, text, size=10.5, bold=False, color=None):
    r = p.add_run(text)
    set_run(r, size=size, bold=bold, color=color)
    return r

def _resolve_question_image(img, q=None, question_bank_root=None):
    """Resolve a question image stored relative to its grade/subject library."""
    if os.path.isabs(img):
        return img
    root = question_bank_root or os.environ.get('QUESTION_BANK_ROOT') or os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'question-bank')
    )
    parts = img.replace('\\', '/').split('/')
    candidates = []
    if q and q.get('grade') and q.get('subject'):
        candidates.append(os.path.join(root, q['grade'], q['subject'], *parts))
    candidates.append(os.path.join(root, *parts))
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def write_practice_docx(questions, out_path, title='物理练习', subtitle='', question_bank_root=None):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0); sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(2.0)
    sec.left_margin = Cm(2.0); sec.right_margin = Cm(2.0)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_text(p, title, size=18, bold=True, color=NAVY)
    if subtitle:
        p = doc.add_paragraph()
        add_text(p, subtitle, size=10, color=GRAY)
    doc.add_paragraph()
    for i, q in enumerate(questions, 1):
        p = doc.add_paragraph()
        add_text(p, f'第 {i} 题（{q["question_type"]} · {q["difficulty"]}）', size=13, bold=True, color=NAVY)
        if q.get('images'):
            for img in q['images']:
                abs_img = _resolve_question_image(img, q=q, question_bank_root=question_bank_root)
                if os.path.exists(abs_img):
                    ip = doc.add_paragraph(); ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    ip.add_run().add_picture(abs_img, width=Cm(7))
        p = doc.add_paragraph()
        add_formula_mixed(p, q['question_text'], size=10.5)
        for o in q.get('options', []):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.5)
            add_formula_mixed(p, o, size=10.5)
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(20)
        add_text(p, '作答区：' + '＿' * 30, size=10.5, color=(0x99, 0x99, 0x99))
        doc.add_paragraph()
    doc.add_page_break()
    p = doc.add_paragraph()
    add_text(p, '答案与解析', size=16, bold=True, color=NAVY)
    for i, q in enumerate(questions, 1):
        p = doc.add_paragraph()
        add_text(p, f'第 {i} 题答案：', size=11, bold=True)
        add_formula_mixed(p, q['answer'], size=11)
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.3)
        r = p.add_run('解析：'); set_run(r, size=10, bold=True)
        add_formula_mixed(p, q['analysis'], size=10)
        doc.add_paragraph()
    doc.save(out_path)
    print('[saved]', out_path)
    return out_path
