# -*- coding: utf-8 -*-
"""
LaTeX → OMML 转换器（把题库里的 LaTeX 公式转成 Word 原生 Office Math）。

题库里公式存为 LaTeX（由 omml2latex.py 从 OMML 转出），但 Word 不识别 LaTeX，
直接写入 docx 会显示原始代码。本模块把受限 LaTeX 子集转回 OMML：

支持的子集（题库中实际用到的）：
- 文本：字母数字、中英文标点、＋－＝() 等
- \\frac{num}{den}    真分数（可嵌套）
- \\sqrt{content}     平方根
- base_{sub}          下标（可写 base^{sup}、base_{sub}^{sup} 组合）
- base^{sup}          上标
- 组合如 \\frac{\\sqrt{m^{2}v_{0}^{2}＋2kqUm}}{qR}

用法：
    from latex2omml import latex_to_omml_nodes, latex_to_omath
    p = doc.add_paragraph()
    latex_to_omath(p, "\\frac{\\sqrt{m^{2}v_{0}^{2}＋2kqUm}}{qR}")
"""
import re
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

M_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'


def _mr(text):
    r = OxmlElement('m:r')
    rpr = OxmlElement('m:rPr')
    sty = OxmlElement('m:sty')
    sty.set(qn('m:val'), 'p')
    rpr.append(sty)
    r.append(rpr)
    t = OxmlElement('m:t')
    t.text = text
    t.set(qn('xml:space'), 'preserve')
    r.append(t)
    return r


def _wrap_e(nodes):
    """把节点列表包进 <m:e>。"""
    e = OxmlElement('m:e')
    for n in nodes:
        e.append(n)
    return e


def _frac(num_nodes, den_nodes):
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


def _sqrt(content_nodes):
    rad = OxmlElement('m:rad')
    radPr = OxmlElement('m:radPr')
    degHide = OxmlElement('m:degHide')
    degHide.set(qn('m:val'), '1')
    radPr.append(degHide)
    rad.append(radPr)
    deg = OxmlElement('m:deg')
    rad.append(deg)
    rad.append(_wrap_e(content_nodes))
    return rad


def _sSub(base_nodes, sub_nodes):
    s = OxmlElement('m:sSub')
    s.append(_wrap_e(base_nodes))
    sub = OxmlElement('m:sub')
    for n in sub_nodes:
        sub.append(n)
    s.append(sub)
    return s


def _sSup(base_nodes, sup_nodes):
    s = OxmlElement('m:sSup')
    s.append(_wrap_e(base_nodes))
    sup = OxmlElement('m:sup')
    for n in sup_nodes:
        sup.append(n)
    s.append(sup)
    return s


class _Parser:
    """手写递归下降解析器：把 LaTeX 字符串解析为 OMML 节点列表。"""

    def __init__(self, s):
        self.s = s
        self.i = 0
        self.n = len(s)

    def peek(self):
        return self.s[self.i] if self.i < self.n else ''

    def error(self, msg):
        raise ValueError(f'LaTeX parse error at {self.i}: {msg}, context: {self.s[max(0,self.i-10):self.i+10]!r}')

    def parse_all(self):
        nodes = self.parse_seq(stop='')
        # 忽略末尾空白
        return nodes

    def parse_seq(self, stop):
        """解析到 stop 字符或结束，返回节点列表。
        支持文本累积、_{}、^{}、\\frac{}{}、\\sqrt{}。"""
        nodes = []
        buf = ''

        def flush():
            nonlocal buf
            if buf:
                nodes.append(_mr(buf))
                buf = ''

        while self.i < self.n:
            ch = self.s[self.i]
            if stop and ch == stop:
                break
            if ch == '}':
                self.error('unexpected }')
            if ch == '{':
                # 无名分组（少见），跳过内容作为文本
                flush()
                self.i += 1
                inner = self.parse_seq(stop='}')
                if self.i < self.n and self.s[self.i] == '}':
                    self.i += 1
                # 把分组内节点并入（作为子表达式，不额外包裹）
                nodes.extend(inner)
                continue
            if ch == '\\':
                flush()
                self.i += 1
                cmd = self._read_cmd()
                if cmd in ('frac', 'dfrac'):
                    num_nodes = self._read_group_or_atom()
                    den_nodes = self._read_group_or_atom()
                    nodes.append(_frac(num_nodes, den_nodes))
                elif cmd == 'sqrt':
                    content = self._read_group_or_atom()
                    nodes.append(_sqrt(content))
                elif cmd == 'text':
                    text_nodes = self._read_group_or_atom()
                    nodes.extend(text_nodes)
                elif cmd in ('angle',):
                    buf += '∠'
                elif cmd in ('circ',):
                    buf += '°'
                elif cmd in ('pm',):
                    buf += '±'
                elif cmd in ('times',):
                    buf += '×'
                elif cmd in ('cdot',):
                    buf += '·'
                elif cmd in ('div',):
                    buf += '÷'
                elif cmd in ('neq', 'ne'):
                    buf += '≠'
                elif cmd in ('le', 'leq'):
                    buf += '≤'
                elif cmd in ('ge', 'geq'):
                    buf += '≥'
                elif cmd in ('Delta',):
                    buf += 'Δ'
                elif cmd in ('triangle',):
                    buf += '△'
                elif cmd in ('odot',):
                    buf += '⊙'
                elif cmd in ('rm',):
                    # \rm 后常跟普通文本/分组，忽略样式命令本身
                    pass
                else:
                    # 未覆盖命令保留为可读文本，避免在 Word 中直接丢失
                    buf += '\\' + cmd
                continue
            if ch == '_':
                flush()
                self.i += 1
                sub_nodes = self._read_group_or_atom()
                if not nodes:
                    nodes.append(_sSub([_mr('')], sub_nodes))
                else:
                    base = nodes.pop()
                    nodes.append(_sSub([base], sub_nodes))
                continue
            if ch == '^':
                flush()
                self.i += 1
                sup_nodes = self._read_group_or_atom()
                if not nodes:
                    nodes.append(_sSup([_mr('')], sup_nodes))
                else:
                    base = nodes.pop()
                    nodes.append(_sSup([base], sup_nodes))
                continue
            # 普通字符（含全角字符、运算符）
            buf += ch
            self.i += 1
        flush()
        return nodes

    def _read_cmd(self):
        """读命令名（字母串）。"""
        start = self.i
        while self.i < self.n and self.s[self.i].isalpha():
            self.i += 1
        if start == self.i:
            self.error('bad command')
        return self.s[start:self.i]

    def _expect(self, ch):
        if self.peek() != ch:
            self.error(f'expect {ch!r}')
        self.i += 1

    def _read_group_or_atom(self):
        if self.peek() == '{':
            self.i += 1
            nodes = self.parse_seq(stop='}')
            self._expect('}')
            return nodes
        if self.i >= self.n:
            return [_mr('')]
        if self.peek() == '\\':
            self.i += 1
            cmd = self._read_cmd()
            text_map = {
                'circ': '°', 'pm': '±', 'times': '×', 'cdot': '·', 'div': '÷',
                'neq': '≠', 'ne': '≠', 'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥',
                'Delta': 'Δ', 'angle': '∠', 'triangle': '△', 'odot': '⊙',
            }
            return [_mr(text_map.get(cmd, '\\' + cmd))]
        ch = self.s[self.i]
        self.i += 1
        return [_mr(ch)]

    def _skip_optional_group(self, buf):
        """未知命令，跳过 {..}（若存在）。"""
        if self.peek() == '{':
            depth = 0
            while self.i < self.n:
                c = self.s[self.i]
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        self.i += 1
                        return
                self.i += 1


def latex_to_nodes(latex_str):
    """把一段 LaTeX 解析成 OMML 节点列表。"""
    return _Parser(latex_str).parse_all()


def latex_to_omath(p, latex_str):
    """在段落 p 中插入一个 LaTeX 公式（OMML oMath）。"""
    nodes = latex_to_nodes(latex_str)
    omath = OxmlElement('m:oMath')
    for n in nodes:
        omath.append(n)
    p._p.append(omath)
