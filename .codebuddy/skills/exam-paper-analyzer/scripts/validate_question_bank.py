#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
题库完整性校验工具（分库架构版）
来源：2026-09-05 结构性体检沉淀；同日适配「按年级/科目分库」架构。

校验项：
  1. 各库 JSON 可解析 / _meta.json 注册表一致
  2. id 全局唯一、5 位定长、跨库连续
  3. 必填字段齐全
  4. 枚举/日期/答案来源合法
  5. 选择题 options=4、答案字母数匹配
  6. (source_paper, question_no) 去重
  7. images 路径存在且正斜杠
  8. _papers.json 题数一致
  9. 实验题必须有配图

用法：python .codebuddy/skills/exam-paper-analyzer/scripts/validate_question_bank.py [--workspace DIR]
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

REQUIRED = ['id', 'subject', 'grade', 'source_paper', 'question_no', 'question_text',
            'answer', 'analysis', 'knowledge_point', 'exam_point', 'difficulty',
            'question_type', 'exam_date', 'exam_type']
DIFFS = {'基础', '中等', '较难', '难题'}
TYPES = {'单选题', '多选题', '填空题', '解答题', '实验题', '计算题'}
ETYPES = {'月考', '期中', '期末', '中考', '高考', '模拟考', '联考', '周测', '单元测试', '其他', '待确认'}
ASRC = {'真题答案', 'AI解答（待教师确认）', '教师确认', '未提供（待补答案）'}
TEXT_FIELDS = ('question_text', 'answer', 'analysis')
CONTROL_CHAR_NAMES = {
    7: 'BEL(疑似 \\angle 被转义)',
    8: 'BS(疑似 \\bar 被转义)',
    9: 'TAB(疑似 \\text 被转义，若非公式可忽略)',
    10: 'LF(疑似 \\ne/\\neq 被转义，若为正常换行可忽略)',
    12: 'FF(疑似 \\frac 被转义)',
    13: 'CR',
}


def find_formula_control_chars(text):
    """返回可能由 LaTeX 反斜杠被错误转义造成的控制字符位置。"""
    if text is None:
        return []
    hits = []
    s = str(text)
    for i, ch in enumerate(s):
        code = ord(ch)
        if code < 32 and ch not in ('\n', '\r'):
            hits.append((i, CONTROL_CHAR_NAMES.get(code, f'CTRL-{code}')))
        elif ch in ('\n', '\r'):
            tail = s[i:i + 5]
            if tail.startswith('\n:eq') or tail.startswith('\neq') or tail.startswith('\r:eq') or tail.startswith('\req'):
                hits.append((i, CONTROL_CHAR_NAMES.get(code, f'CTRL-{code}')))
    return hits


def has_broken_latex_fragment(text):
    if text is None:
        return False
    s = str(text)
    return any(marker in s for marker in ('\x0crac', '\x07ngle', '\x08ar', '\text', '\n:eq', '\neq'))


def main():
    ap = argparse.ArgumentParser(description='题库结构性体检（分库架构）')
    ap.add_argument('--workspace', default='.', help='工作区根目录（默认当前目录）')
    args = ap.parse_args()

    qb = os.path.join(os.path.abspath(args.workspace), 'question-bank')
    errors, warns = [], []

    # 发现所有分库 {年级}/{科目}/_questions.json
    libs = []
    if os.path.isdir(qb):
        for grade in sorted(os.listdir(qb)):
            gdir = os.path.join(qb, grade)
            if not os.path.isdir(gdir):
                continue
            for subject in sorted(os.listdir(gdir)):
                qp = os.path.join(gdir, subject, '_questions.json')
                if os.path.exists(qp):
                    libs.append((grade, subject, qp, os.path.join(gdir, subject)))
    print(f"[1] 发现分库: {len(libs)} 个 → {[(g, s) for g, s, _, _ in libs]}")

    meta_path = os.path.join(qb, '_meta.json')
    meta = json.load(open(meta_path, encoding='utf-8')) if os.path.exists(meta_path) else {}
    if libs and not meta:
        errors.append("缺少 _meta.json（全局 id 计数器与注册表）")

    all_qs, all_ids = [], []
    for grade, subject, qp, lib_dir in libs:
        qs = json.load(open(qp, encoding='utf-8'))
        all_qs.extend(qs)
        all_ids.extend(q['id'] for q in qs)

        # 库内 grade/subject 一致性
        for q in qs:
            if q.get('grade') != grade or q.get('subject') != subject:
                errors.append(f"{q.get('id')} 归属错库: 应在 {q.get('grade')}/{q.get('subject')}，实际在 {grade}/{subject}")

        # 必填字段 / 枚举 / 选项 / 去重 / 图片 / papers 一致性 / 实验配图
        keys = [(q['source_paper'], q['question_no']) for q in qs]
        dup = [k for k in set(keys) if keys.count(k) > 1]
        if dup:
            errors.append(f"[{grade}/{subject}] 重复题目: {dup}")
        papers = json.load(open(os.path.join(lib_dir, '_papers.json'), encoding='utf-8')) \
            if os.path.exists(os.path.join(lib_dir, '_papers.json')) else []
        from collections import Counter
        cnt = Counter(q['source_paper'] for q in qs)
        for p in papers:
            if p['question_count'] != cnt.get(p['name'], 0):
                errors.append(f"[{grade}/{subject}] papers 题数不符: {p['name']}")
        for q in qs:
            qid = q.get('id', '?')
            missing = [f for f in REQUIRED if not q.get(f)]
            if missing:
                errors.append(f"{qid} 缺字段: {missing}")
            if q.get('difficulty') not in DIFFS:
                errors.append(f"{qid} difficulty 非法: {q.get('difficulty')}")
            if q.get('question_type') not in TYPES:
                warns.append(f"{qid} question_type 非常规: {q.get('question_type')}")
            if q.get('exam_type') not in ETYPES:
                errors.append(f"{qid} exam_type 非法: {q.get('exam_type')}")
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(q.get('exam_date', ''))):
                errors.append(f"{qid} exam_date 格式错")
            src = q.get('answer_source')
            if src and src not in ASRC:
                errors.append(f"{qid} answer_source 非法: {src}")
            for field in TEXT_FIELDS:
                value = q.get(field, '')
                hits = find_formula_control_chars(value)
                if hits or has_broken_latex_fragment(value):
                    detail = ', '.join(f'{name}@{pos}' for pos, name in hits[:5]) or '疑似残缺 LaTeX 片段'
                    errors.append(f"{qid} {field} 含疑似 LaTeX 转义污染: {detail}")
            for opt_idx, opt in enumerate(q.get('options', []) or [], 1):
                hits = find_formula_control_chars(opt)
                if hits or has_broken_latex_fragment(opt):
                    detail = ', '.join(f'{name}@{pos}' for pos, name in hits[:5]) or '疑似残缺 LaTeX 片段'
                    errors.append(f"{qid} option[{opt_idx}] 含疑似 LaTeX 转义污染: {detail}")
            t, ans, opts = q.get('question_type'), q.get('answer', ''), q.get('options', [])
            skip_answer_check = q.get('answer_source') == '未提供（待补答案）'
            if t in ('单选题', '多选题'):
                if len(opts) != 4:
                    errors.append(f"{qid} {t} 选项数={len(opts)}")
                if not skip_answer_check:
                    letters = re.findall(r'[A-D]', ans)
                    if t == '单选题' and len(letters) != 1:
                        errors.append(f"{qid} 单选答案异常: {ans}")
                    if t == '多选题' and len(letters) < 2:
                        errors.append(f"{qid} 多选答案<2: {ans}")
            for pth in q.get('images', []):
                if '\\' in pth:
                    errors.append(f"{qid} 图片路径含反斜杠: {pth}")
                if not os.path.exists(os.path.join(lib_dir, *pth.split('/'))):
                    errors.append(f"{qid} 图片缺失: {pth}")
            if t == '实验题' and not q.get('images'):
                warns.append(f"{qid} 实验题无配图")

    # id 全局唯一 + 5 位 + 连续
    bad_fmt = [i for i in all_ids if not re.match(r'^Q-\d{5}$', i)]
    if bad_fmt:
        errors.append(f"id 非 5 位定长: {bad_fmt[:5]}")
    dup_ids = [i for i in set(all_ids) if all_ids.count(i) > 1]
    if dup_ids:
        errors.append(f"id 跨库重复: {dup_ids}")
    nums = sorted(int(i.split('-')[1]) for i in all_ids)
    if nums and nums != list(range(1, len(nums) + 1)):
        errors.append(f"id 不连续: 期望 1~{len(nums)}")
    if meta.get('next_id') and nums and meta['next_id'] != max(nums) + 1:
        errors.append(f"_meta.json next_id={meta['next_id']} 应为 {max(nums)+1}")
    print(f"[2] id: Q-00001~Q-{nums[-1]:05d}（{len(all_ids)} 题全局唯一）"
          if nums else "[2] id: （空库）")

    n_ai = sum(1 for q in all_qs if q.get('answer_source') == 'AI解答（待教师确认）')
    if n_ai:
        warns.append(f"AI 解答待确认: {n_ai} 题（建议教师优先抽查）")
    print(f"[3~9] 字段/枚举/选项/去重/图片/清单/配图: 检查完成（AI待确认 {n_ai} 题）")

    print("\n" + "=" * 50)
    print(f"错误: {len(errors)}")
    for e in errors:
        print("  ✗", e)
    print(f"警告: {len(warns)}")
    for w in warns:
        print("  ⚠", w)
    print("\n结论:", "题库健康" if not errors else "存在问题，需修复")
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()