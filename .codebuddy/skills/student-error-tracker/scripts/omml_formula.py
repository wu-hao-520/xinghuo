# -*- coding: utf-8 -*-
"""
正确的 OMML 公式构造模块（Word 公式排版核心）。

用途：在 python-docx 中生成正确的 Office Math (OMML) 公式，
支持真上下标、真分数。

关键点（此前踩过的坑）：
- 上标必须用 <m:sSup> 结构（含 <m:e> + <m:sup>），不能把 <m:sup/> 塞进 <m:rPr>。
- 下标必须用 <m:sSub> 结构（含 <m:e> + <m:sub>），不能用 <m:sscr>（错误标签）。
- 分数用 <m:f>（含分子 <m:num> + 分母 <m:den>）。
- <m:sty m:val="p"> 表示普通文本样式（避免变量被默认斜体）。

用法：
    from omml_formula import add_formula
    p = doc.add_paragraph()
    add_formula(p, "\\frac{B^2^L^2^v~0~}{mR}")  # 真分数 + 上下标

标记语法：
    ~x~  -> 下标 x（紧跟前面的 base 字符）
    ^x^  -> 上标 x（紧跟前面的 base 字符）
    \\frac{num}{den} -> 真分数（分子分母内部可再含 ~ ^ 标记）
"""

import re
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def _mr(text, italic=False):
    """构造 <m:r>（普通数学 run）。"""
    r = OxmlElement('m:r')
    rpr = OxmlElement('m:rPr')
    sty = OxmlElement('m:sty')
    sty.set(qn('m:val'), 'p')
    rpr.append(sty)
    if italic:
        rpr.append(OxmlElement('m:i'))
    r.append(rpr)
    t = OxmlElement('m:t')
    t.text = text
    t.set(qn('xml:space'), 'preserve')
    r.append(t)
    return r


def _sSup(base, sup):
    """上标：base^sup。"""
    s = OxmlElement('m:sSup')
    e = OxmlElement('m:e')
    e.append(_mr(base, italic=True))
    s.append(e)
    sp = OxmlElement('m:sup')
    sp.append(_mr(sup))
    s.append(sp)
    return s


def _sSub(base, sub):
    """下标：base_sub。"""
    s = OxmlElement('m:sSub')
    e = OxmlElement('m:e')
    e.append(_mr(base, italic=True))
    s.append(e)
    sb = OxmlElement('m:sub')
    sb.append(_mr(sub))
    s.append(sb)
    return s


def _frac(num_nodes, den_nodes):
    """真分数：<m:f> 含分子 <m:num> + 分母 <m:den>。"""
    f = OxmlElement('m:f')
    num = OxmlElement('m:num')
    for n in num_nodes:
        num.append(n)
    den = OxmlElement('m:den')
    for n in den_nodes:
        den.append(n)
    f.append(num)
    f.append(den)
    return f


def _rad(e_nodes):
    """真根号：<m:rad>，隐藏次数，表示平方根。"""
    rad = OxmlElement('m:rad')
    rad_pr = OxmlElement('m:radPr')
    deg_hide = OxmlElement('m:degHide')
    deg_hide.set(qn('m:val'), '1')
    rad_pr.append(deg_hide)
    rad.append(rad_pr)
    e = OxmlElement('m:e')
    for n in e_nodes:
        e.append(n)
    rad.append(e)
    return rad


# 匹配 \frac{...}{...} 与 \sqrt{...}（~ 和 ^ 由 parse_inline 处理）
TOKEN_RE = re.compile(r'(\\frac\{[^{}]*\}\{[^{}]*\}|\\sqrt\{[^{}]*\})')


def parse_inline(text):
    """把一段含 ~下标~/^上标^ 的文本解析成 OMML 节点列表。"""
    nodes = []
    i = 0
    buf = ''

    def flush():
        nonlocal buf
        if buf:
            nodes.append(_mr(buf, italic=True))
            buf = ''

    while i < len(text):
        ch = text[i]
        if ch == '~':
            j = text.find('~', i + 1)
            if j > i + 1:
                sub = text[i + 1:j]
                base = buf[-1] if buf else ''
                if buf[:-1]:
                    nodes.append(_mr(buf[:-1], italic=True))
                buf = ''
                if base:
                    nodes.append(_sSub(base, sub))
                else:
                    nodes.append(_mr(sub))
                i = j + 1
                continue
        elif ch == '^':
            j = text.find('^', i + 1)
            if j > i + 1:
                sup = text[i + 1:j]
                base = buf[-1] if buf else ''
                if buf[:-1]:
                    nodes.append(_mr(buf[:-1], italic=True))
                buf = ''
                if base:
                    nodes.append(_sSup(base, sup))
                else:
                    nodes.append(_mr(sup))
                i = j + 1
                continue
        buf += ch
        i += 1
    flush()
    return nodes


def parse_formula(text):
    """解析公式字符串为 OMML 节点列表，支持 \\frac 和 ~下标~ ^上标^。"""
    nodes = []
    pos = 0
    for m in TOKEN_RE.finditer(text):
        if m.start() > pos:
            nodes.extend(parse_inline(text[pos:m.start()]))
        token = m.group(0)
        if token.startswith('\\frac'):
            mm = re.match(r'\\frac\{([^{}]*)\}\{([^{}]*)\}', token)
            num, den = mm.group(1), mm.group(2)
            nodes.append(_frac(parse_inline(num), parse_inline(den)))
        elif token.startswith('\\sqrt'):
            mm = re.match(r'\\sqrt\{([^{}]*)\}', token)
            nodes.append(_rad(parse_inline(mm.group(1))))
        pos = m.end()
    if pos < len(text):
        nodes.extend(parse_inline(text[pos:]))
    return nodes


def add_formula(p, formula):
    """在段落 p 中插入公式（OMML）。"""
    omath = OxmlElement('m:oMath')
    for n in parse_formula(formula):
        omath.append(n)
    p._p.append(omath)
