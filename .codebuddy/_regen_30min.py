# -*- coding: utf-8 -*-
"""重新生成 30 分钟测试练习 docx（用修复后的公式渲染器）。"""
import sys, os, json

sys.path.insert(0, r'e:\codebuddy\workflow\.codebuddy\skills\exam-paper-analyzer\scripts')
from render_docx_practice import write_practice_docx

BANK = r'e:\codebuddy\workflow\question-bank\_questions.json'
OUT = r'e:\codebuddy\workflow\student-profiles\exams\练习_20260905_测试_物理_30分钟.docx'

# 先读旧 docx 的标题/副标题（若存在），保持一致
def read_old_title(path):
    if not os.path.exists(path):
        return None, None
    from docx import Document
    d = Document(path)
    ps = [p.text for p in d.paragraphs if p.text.strip()]
    title = ps[0] if ps else None
    subtitle = ps[1] if len(ps) > 1 and not ps[1].startswith('第') else None
    return title, subtitle

old_title, old_subtitle = read_old_title(OUT)
print('old title:', old_title)
print('old subtitle:', old_subtitle)

qs = json.load(open(BANK, encoding='utf-8'))
test_ids = ['Q-0011', 'Q-0015', 'Q-0016', 'Q-0018', 'Q-0024']
sel = [q for q in qs if q.get('id') in test_ids]
# 按 test_ids 顺序排序
sel = sorted(sel, key=lambda q: test_ids.index(q['id']))
print('selected:', [q['id'] for q in sel])

title = old_title or '测试练习（30 分钟物理）'
subtitle = old_subtitle or '来源：高考真题（2025年高考广东卷物理真题） · 时长约 30 分钟 · 共 5 题'
write_practice_docx(sel, OUT, title=title, subtitle=subtitle)
print('DONE')
