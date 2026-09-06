# -*- coding: utf-8 -*-
"""
OMML 公式 → LaTeX 转换器。

把 docx 里的 Office Math (OMML) 公式转成 LaTeX 字符串，解决"公式结构丢失"问题。
这是题库录入的核心：必须完整还原公式的上下标、分数、根号结构，否则录入的题目与原题不一致。

支持的 OMML 元素：
- m:r / m:t        普通文本
- m:sSup          上标  base^sup
- m:sSub          下标  base_sub
- m:sSubSup       上下标 base_sub^sup
- m:f / m:num / m:den  分数 num/den
- m:rad / m:deg   根号  sqrt
- m:d / m:e       容器/分隔符

用法：
    from omml2latex import omml_to_latex
    latex = omml_to_latex(omath_inner_xml)
"""
from lxml import etree

M_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'


def _tag(el):
    return etree.QName(el).localname


def _r_text(el):
    """提取 m:r 里的文本（所有 m:t）。"""
    ts = el.findall('{%s}t' % M_NS)
    return ''.join(t.text for t in ts if t.text)


def to_latex(node):
    """递归把 OMML 节点转成 LaTeX。"""
    tag = _tag(node)
    if tag == 'r':
        return _r_text(node)
    elif tag == 't':
        return node.text or ''
    elif tag == 'sSup':
        base = node.find('{%s}e' % M_NS)
        sup = node.find('{%s}sup' % M_NS)
        b = to_latex(base) if base is not None else ''
        s = to_latex(sup) if sup is not None else ''
        return '%s^{%s}' % (b, s)
    elif tag == 'sSub':
        base = node.find('{%s}e' % M_NS)
        sub = node.find('{%s}sub' % M_NS)
        b = to_latex(base) if base is not None else ''
        s = to_latex(sub) if sub is not None else ''
        return '%s_{%s}' % (b, s)
    elif tag == 'sSubSup':
        base = node.find('{%s}e' % M_NS)
        sub = node.find('{%s}sub' % M_NS)
        sup = node.find('{%s}sup' % M_NS)
        b = to_latex(base) if base is not None else ''
        sb = to_latex(sub) if sub is not None else ''
        sp = to_latex(sup) if sup is not None else ''
        return '%s_{%s}^{%s}' % (b, sb, sp)
    elif tag == 'f':
        num = node.find('{%s}num' % M_NS)
        den = node.find('{%s}den' % M_NS)
        n = to_latex(num) if num is not None else ''
        d = to_latex(den) if den is not None else ''
        return '\\frac{%s}{%s}' % (n, d)
    elif tag == 'rad':
        deg = node.find('{%s}deg' % M_NS)
        deg_hide = node.find('{%s}radPr/{%s}degHide' % (M_NS, M_NS))
        e = node.find('{%s}e' % M_NS)
        content = to_latex(e) if e is not None else ''
        if deg_hide is not None and deg_hide.get('{%s}val' % M_NS) == '1':
            return '\\sqrt{%s}' % content
        elif deg is not None and _r_text(deg):
            return '\\sqrt[%s]{%s}' % (_r_text(deg), content)
        else:
            return '\\sqrt{%s}' % content
    elif tag in ('e', 'd', 'num', 'den', 'oMath', 'oMathPara'):
        return ''.join(to_latex(c) for c in node)
    else:
        # 未知元素：递归子节点
        return ''.join(to_latex(c) for c in node)


def omml_to_latex(omath_inner_xml):
    """把 oMath 的内部 XML 字符串转成 LaTeX。

    参数 omath_inner_xml 是 <m:oMath>...</m:oMath> 内部的内容（不含 oMath 标签本身）。
    """
    ns_decl = ('xmlns:m="%s" '
               'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
               'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
               ) % M_NS
    wrapper = '<m:oMath %s>%s</m:oMath>' % (ns_decl, omath_inner_xml)
    root = etree.fromstring(wrapper.encode('utf-8'))
    return to_latex(root)
