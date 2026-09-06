# -*- coding: utf-8 -*-
"""
docx 试卷 → 结构化题目提取器（含 OMML 公式完整还原）。

用法：
    from extract_docx import extract_paper
    questions, section = extract_paper(docx_path)

返回题目列表，每道题含 question_no、question_text、options、answer、analysis。
题干和选项保留原文（公式转 LaTeX），解析保留原文（公式转 LaTeX）。

关键：OMML 公式用 omml2latex 完整还原，而不是只提取 <m:t> 文本（否则结构丢失）。
"""
import re
from lxml import etree
from docx import Document
from docx.oxml.ns import qn

from omml2latex import omml_to_latex


def _run_to_text(run_el):
    """把一个 w:r 转成文本，处理 w:vertAlign 上下标（转成 ~x~ / ^x^ 标记）。"""
    t = run_el.find(qn('w:t'))
    if t is None or not t.text:
        return ''
    text = t.text
    # 检查 vertAlign（普通文本的上下标）
    rpr = run_el.find(qn('w:rPr'))
    if rpr is not None:
        va = rpr.find(qn('w:vertAlign'))
        if va is not None:
            val = va.get(qn('w:val'))
            if val == 'subscript':
                return '~' + text + '~'
            elif val == 'superscript':
                return '^' + text + '^'
    return text


def para_full_text(p):
    """提取段落完整文本：普通 run 文本（含 vertAlign 上下标）+ OMML 公式转 LaTeX。

    关键：OMML 公式转 LaTeX；普通文本 run 里的 w:vertAlign 上下标转 ~x~/^x^ 标记。
    """
    parts = []
    for child in p._p:
        tag = child.tag.split('}')[-1]
        if tag == 'r':
            parts.append(_run_to_text(child))
        elif tag == 'oMath':
            xml = etree.tostring(child, encoding='unicode')
            inner = re.sub(r'^<m:oMath[^>]*>|</m:oMath>$', '', xml)
            parts.append('$' + omml_to_latex(inner) + '$')
        elif tag == 'oMathPara':
            for om in child.findall(qn('m:oMath')):
                xml = etree.tostring(om, encoding='unicode')
                inner = re.sub(r'^<m:oMath[^>]*>|</m:oMath>$', '', xml)
                parts.append('$' + omml_to_latex(inner) + '$')
    return ''.join(parts)


def extract_paper(docx_path):
    """提取 docx 试卷的所有题目。"""
    doc = Document(docx_path)
    paras = []
    for p in doc.paragraphs:
        t = para_full_text(p).strip()
        if t:
            paras.append(t)

    questions = []
    current_q = None
    current_section = ''

    for t in paras:
        # 题型标题（如「一、单选题」）
        if re.match(r'^[一二三四五六七八]、', t):
            current_section = re.sub(r'^[一二三四五六七八]、', '', t)
            continue
        # 题号开始（兼容半角「1.」与全角「1．」两种题号风格，如江西卷用全角）
        m = re.match(r'^(\d+)[.．]', t)
        if m:
            qno = int(m.group(1))
            current_q = {
                'question_no': f'第{qno}题',
                'question_text': t,
                'options': [],
                'answer': '',
                'analysis': '',
                'section': current_section,  # 记录题目所属小节（题型来源）
            }
            questions.append(current_q)
            continue
        # 选项（兼容全角句号；一行多选项自动拆分；「答案」出现后停止收集，
        # 防止解析续行"B．xxx错误"被误收为选项——2025-09-05 批量录入 18 份高考卷踩坑）
        if current_q and not current_q['answer'] and re.match(r'^[A-D][.．$]', t):
            # 拆分挤行："A.0.5 hB.3 hC.28 hD.166 h" → 4 条
            for pt in re.split(r'(?=[A-D][.．$])', t):
                pt = pt.strip()
                if pt and re.match(r'^[A-D][.．$]', pt):
                    current_q['options'].append(pt)
            continue
        # 答案
        if current_q and t.startswith('答案'):
            current_q['answer'] = t.replace('答案', '').replace('　', '').strip()
            continue
        # 解析
        if current_q and t.startswith('解析'):
            current_q['analysis'] = t.replace('解析', '').replace('　', '').strip()
            continue
        # 续行（题干续行或解析续行）
        if current_q:
            if current_q['answer']:
                current_q['analysis'] += t
            else:
                current_q['question_text'] += '\n' + t

    return questions, current_section
