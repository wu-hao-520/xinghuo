# -*- coding: utf-8 -*-
"""
学生错题管理工具 student_manager.py

提供学生档案（JSON）的读写、错题增删、可读档案（Markdown）生成、
薄弱点统计、练习单生成等能力。数据存放在 student-profiles/ 下。

用法示例（均为 ASCII 命令，中文放脚本源码里硬编码）：
  python student_manager.py init --name 学生姓名 --grade 高三
  python student_manager.py add-error --name 学生姓名 --json 错题.json
  python student_manager.py gen-md --name 学生姓名
  python student_manager.py stats --name 学生姓名
"""

import os
import sys
import json
import argparse
import datetime

BASE = r'e:\codebuddy\workflow\student-profiles'
STUDENTS_DIR = os.path.join(BASE, 'students')
EXAMS_DIR = os.path.join(BASE, 'exams')
BANK_PATH = os.path.join(BASE, '_question_bank.json')

SUBJECT_PREFIX = {'物理': 'P', '数学': 'M', '英语': 'E', '化学': 'C', '语文': 'W'}


def ensure_dirs():
    os.makedirs(STUDENTS_DIR, exist_ok=True)
    os.makedirs(EXAMS_DIR, exist_ok=True)


def student_path(name):
    return os.path.join(STUDENTS_DIR, f'{name}.json')


def load_student(name):
    p = student_path(name)
    if not os.path.exists(p):
        print(f'[error] 学生 {name} 不存在: {p}')
        sys.exit(1)
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_student(name, data):
    p = student_path(name)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'[saved] {p}')


def cmd_init(args):
    ensure_dirs()
    p = student_path(args.name)
    if os.path.exists(p):
        print(f'[warn] 学生 {args.name} 已存在，跳过创建')
        return
    data = {
        'name': args.name,
        'grade': args.grade or '',
        'subjects': [],
        'profile': {'整体水平': '', '薄弱学科': [], '备注': ''},
        'errors': [],
    }
    save_student(args.name, data)


def cmd_add_error(args):
    """从 json 文件读取一条或多条错题，追加到学生 errors。"""
    ensure_dirs()
    data = load_student(args.name)
    with open(args.json, encoding='utf-8') as f:
        errs = json.load(f)
    if isinstance(errs, dict):
        errs = [errs]
    subj = errs[0].get('subject', '') if errs else ''
    prefix = SUBJECT_PREFIX.get(subj, 'X')
    today = datetime.date.today().strftime('%Y%m%d')
    added = 0
    for e in errs:
        # 生成唯一 id（基于已有错误数 + 本次已添加数 + 1）
        seq = len(data['errors']) + 1
        e.setdefault('id', f'{prefix}-{today}-{seq:03d}')
        e.setdefault('date', datetime.date.today().strftime('%Y-%m-%d'))
        e.setdefault('review_status', '未复习')
        e.setdefault('review_count', 0)
        e.setdefault('review_history', [])
        e.setdefault('tags', [])
        data['errors'].append(e)
        added += 1
    # 更新 subjects 列表
    for e in errs:
        s = e.get('subject')
        if s and s not in data['subjects']:
            data['subjects'].append(s)
    save_student(args.name, data)
    print(f'[added {added} errors] to {args.name}')
    # 同步生成 MD
    gen_md(args.name, data)


def cmd_gen_md(args):
    ensure_dirs()
    data = load_student(args.name)
    gen_md(args.name, data)


def gen_md(name, data):
    lines = []
    lines.append(f'# {name} 学情档案\n')
    lines.append('> 本文件由 student_manager.py 从 JSON 自动生成，请勿手改（改 JSON 后重新生成）。\n')
    lines.append('## 基本信息\n')
    lines.append(f'- 姓名：{name}')
    lines.append(f'- 年级/学段：{data.get("grade", "")}')
    lines.append(f'- 学科：{"、".join(data.get("subjects", [])) or "未填写"}')
    lines.append(f'- 整体水平：{data.get("profile", {}).get("整体水平", "")}')
    lines.append(f'- 薄弱学科：{"、".join(data.get("profile", {}).get("薄弱学科", [])) or "无"}')
    lines.append(f'- 备注：{data.get("profile", {}).get("备注", "")}\n')

    errors = data.get('errors', [])
    lines.append(f'## 错题本（共 {len(errors)} 题）\n')
    if not errors:
        lines.append('（暂无错题）\n')
    else:
        lines.append('| ID | 日期 | 学科 | 题号 | 错误类型 | 难度 | 考点/知识点 | 复习状态 | 复习次数 |')
        lines.append('|----|------|------|------|----------|------|-------------|----------|----------|')
        for e in errors:
            kp = e.get('knowledge_point', '')
            ep = e.get('exam_point', '')
            kp_ep = f'{kp}｜{ep}' if ep else kp
            lines.append(
                f'| {e.get("id","")} | {e.get("date","")} | {e.get("subject","")} | '
                f'{e.get("question_no","")} | {e.get("error_type","")} | {e.get("difficulty","")} | '
                f'{kp_ep} | {e.get("review_status","")} | {e.get("review_count",0)} |'
            )
        lines.append('')

    # 薄弱点统计
    if errors:
        lines.append('## 薄弱知识点分析\n')
        from collections import Counter, defaultdict
        kp_counter = Counter(e.get('knowledge_point', '未知') for e in errors)
        et_counter = Counter(e.get('error_type', '未知') for e in errors)
        lines.append('### 知识点出错次数\n')
        for kp, cnt in kp_counter.most_common():
            lines.append(f'- {kp}：{cnt} 次')
        lines.append('\n### 错误类型分布\n')
        for et, cnt in et_counter.most_common():
            lines.append(f'- {et}：{cnt} 题')
        lines.append('')

    lines.append('---\n')
    lines.append('## 错题明细\n')
    for e in errors:
        lines.append(f"### {e.get('question_no','')} — {e.get('subject','')} · {e.get('difficulty','')} · {e.get('error_type','')}\n")
        lines.append(f"- **考点**：{e.get('exam_point','')}")
        lines.append(f"- **知识点**：{e.get('knowledge_point','')}")
        lines.append(f"- **题型**：{e.get('question_type','')}")
        lines.append(f"- **题目**：{e.get('question_text','')}")
        lines.append(f"- **正确答案**：{e.get('correct_answer','')}")
        lines.append(f"- **学生答案**：{e.get('student_answer','')}")
        lines.append(f"- **复习状态**：{e.get('review_status','')}（已复习 {e.get('review_count',0)} 次）")
        hist = e.get('review_history', [])
        if hist:
            lines.append(f"- **重做记录**：")
            for h in hist:
                lines.append(f"  - {h.get('date','')}：{h.get('result','')}｜{h.get('note','')}")
        lines.append('')

    md_path = os.path.join(STUDENTS_DIR, f'{name}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'[generated md] {md_path}')


def cmd_stats(args):
    ensure_dirs()
    data = load_student(args.name)
    errors = data.get('errors', [])
    from collections import Counter
    kp_counter = Counter(e.get('knowledge_point', '未知') for e in errors)
    et_counter = Counter(e.get('error_type', '未知') for e in errors)
    print(f'学生 {args.name}：共 {len(errors)} 道错题')
    print('\n知识点出错次数（降序）：')
    for kp, cnt in kp_counter.most_common():
        print(f'  {kp}: {cnt}')
    print('\n错误类型分布：')
    for et, cnt in et_counter.most_common():
        print(f'  {et}: {cnt}')
    unmastered = [e for e in errors if e.get('review_status') != '已掌握']
    print(f'\n未掌握错题：{len(unmastered)} 道')


def cmd_review_list(args):
    """生成今日该复习的错题清单（简版，直接打印）。"""
    ensure_dirs()
    data = load_student(args.name)
    errors = data.get('errors', [])
    todo = [e for e in errors if e.get('review_status') != '已掌握']
    print(f'学生 {args.name} 待复习错题（{len(todo)} 道）：')
    for e in todo:
        print(f"  [{e.get('id')}] {e.get('question_no')} {e.get('knowledge_point')} "
              f"({e.get('error_type')}) 复习{e.get('review_count',0)}次")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)

    c_init = sub.add_parser('init')
    c_init.add_argument('--name', required=True)
    c_init.add_argument('--grade')
    c_init.set_defaults(func=cmd_init)

    c_add = sub.add_parser('add-error')
    c_add.add_argument('--name', required=True)
    c_add.add_argument('--json', required=True)
    c_add.set_defaults(func=cmd_add_error)

    c_md = sub.add_parser('gen-md')
    c_md.add_argument('--name', required=True)
    c_md.set_defaults(func=cmd_gen_md)

    c_stats = sub.add_parser('stats')
    c_stats.add_argument('--name', required=True)
    c_stats.set_defaults(func=cmd_stats)

    c_review = sub.add_parser('review-list')
    c_review.add_argument('--name', required=True)
    c_review.set_defaults(func=cmd_review_list)

    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
