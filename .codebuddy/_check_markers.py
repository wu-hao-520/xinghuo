# -*- coding: utf-8 -*-
"""检查高考卷题库中 ~ 和 ^ 标记是否成对（奇数则可能为区间记号或录入错误）。"""
import json

qs = json.load(open(r'e:\codebuddy\workflow\question-bank\_questions.json', encoding='utf-8'))
gk = [q for q in qs if q.get('exam_type') == '高考']

print('高考卷题目数:', len(gk))
print('--- 各题 ~ / ^ 计数（~ 应为偶数） ---')
for q in gk:
    fields = [q['question_text']] + list(q.get('options', [])) + [q['analysis']]
    t = sum(f.count('~') for f in fields)
    c = sum(f.count('^') for f in fields)
    flag = '' if t % 2 == 0 else '  <-- 奇数!'
    print(f"{q['id']:8s} ~={t:2d}  ^={c:2d}{flag}")
