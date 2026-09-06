#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标准中间题目包快速入库工具。

用法：
  python .codebuddy/skills/exam-paper-analyzer/scripts/import_standard_package.py --zip <题目包.zip>
  python .codebuddy/skills/exam-paper-analyzer/scripts/import_standard_package.py --download-name <下载目录内zip文件名>
  python .codebuddy/skills/exam-paper-analyzer/scripts/import_standard_package.py --latest-download
  python .codebuddy/skills/exam-paper-analyzer/scripts/import_standard_package.py --download-name <下载目录内zip文件名> --validate

说明：
- 读取 standard-intermediate-question-package ZIP；
- 体检 package_manifest/manifest/questions 结构与 LaTeX 控制字符污染；
- 按 grade/subject 写入 question-bank/{年级}/{科目}/；
- 复制 figures/original 到分库 images/{paper_id}/；
- 自动分配全局 Q-xxxxx id、更新 _papers/_meta/_index；
- 无源答案时不阻塞逐题解答，写入“待教师确认”，并标记 answer_source="未提供（待补答案）"。
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

GRADE_MAP = {
    '九年级': '初三', '初三': '初三',
    '八年级': '初二', '初二': '初二',
    '七年级': '初一', '初一': '初一',
    '高三': '高三', '高二': '高二', '高一': '高一',
}
TYPE_MAP = {
    '选择题': '单选题',
    '单项选择题': '单选题',
    '单选题': '单选题',
    '多选题': '多选题',
    '多项选择题': '多选题',
    '填空题': '填空题',
    '解答题': '解答题',
    '计算题': '计算题',
    '实验题': '实验题',
}
REQUIRED_Q_FIELDS = ('schema_version', 'question_id', 'question_no', 'source', 'content', 'conversion')
POLLUTION_MARKERS = ('\x0crac', '\x07ngle', '\x08ar', '\n:eq', '\neq')


def load_json_file(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []


def save_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def text_has_pollution(text):
    if not isinstance(text, str):
        return False
    if any(ord(ch) < 32 and ch not in '\r\n\t' for ch in text):
        return True
    return any(marker in text for marker in POLLUTION_MARKERS)


def walk_texts(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from walk_texts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_texts(value)


def safe_paper_dir_name(name):
    return re.sub(r'[\\/:*?"<>|\s]+', '_', str(name)).strip('_')[:80] or 'paper'


def normalize_grade(grade):
    return GRADE_MAP.get(str(grade), str(grade))


def normalize_question_type(raw):
    return TYPE_MAP.get(str(raw or '').strip(), str(raw or '其他').strip() or '其他')


def build_question_text(content):
    stem = content.get('stem') or ''
    subs = content.get('subquestions') or []
    if subs:
        stem += '\n' + '\n'.join(f'（{i}）{sub}' for i, sub in enumerate(subs, 1))
    return stem


def build_options(options):
    if isinstance(options, dict):
        return [f'{k}.{v}' for k, v in sorted(options.items())]
    if isinstance(options, list):
        return options
    return []


def latest_download_zip():
    downloads = Path.home() / 'Downloads'
    zips = sorted(downloads.glob('*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        raise FileNotFoundError(f'未在下载目录找到 zip: {downloads}')
    return zips[0]


def download_zip_by_name(name):
    path = Path(name)
    if path.is_absolute():
        return path
    return Path.home() / 'Downloads' / name


def read_zip_json(zf, name):
    return json.loads(zf.read(name).decode('utf-8-sig'))


def inspect_package(zf):
    names = zf.namelist()
    if 'package_manifest.json' not in names:
        raise ValueError('缺少 package_manifest.json')
    pkg = read_zip_json(zf, 'package_manifest.json')
    papers = pkg.get('papers') or []
    if not papers:
        raise ValueError('package_manifest.json 中 papers 为空')
    return pkg, papers


def validate_intermediate_questions(questions):
    errors = []
    pollution = []
    for idx, q in enumerate(questions, 1):
        missing = [field for field in REQUIRED_Q_FIELDS if field not in q]
        if missing:
            errors.append(f'第 {idx} 条缺字段: {missing}')
        if any(text_has_pollution(text) for text in walk_texts(q)):
            pollution.append(q.get('question_id') or idx)
    return errors, pollution


def update_index(qb, meta):
    lines = ['# 题库索引', '', f"- 全局下一题号：`Q-{int(meta.get('next_id', 1)):05d}`", '']
    for lib in meta.get('libraries', []):
        lines.append(f"- {lib['grade']}/{lib['subject']}：{lib['count']} 题，{lib['papers']} 份试卷，{lib['images_dirs']} 个图片目录")
    (qb / '_index.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def import_package(zip_path, workspace, exam_date, exam_type):
    qb = workspace / 'question-bank'
    meta_path = qb / '_meta.json'
    if not meta_path.exists():
        raise FileNotFoundError(f'缺少题库元数据: {meta_path}')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    next_id = int(meta.get('next_id', 1))
    total_added = 0
    total_skipped = 0
    total_pollution = []

    with zipfile.ZipFile(zip_path) as zf:
        pkg, paper_refs = inspect_package(zf)
        print(f"[包体] {pkg.get('package_title', zip_path.name)}：{len(paper_refs)} 份试卷，声明 {pkg.get('question_count_total')} 题")

        for pref in paper_refs:
            paper_dir = pref.get('directory')
            manifest_path = pref.get('manifest') or f'{paper_dir}/manifest.json'
            questions_path = pref.get('questions') or f'{paper_dir}/questions.json'
            manifest = read_zip_json(zf, manifest_path)
            questions = read_zip_json(zf, questions_path)
            errors, pollution = validate_intermediate_questions(questions)
            if errors:
                raise ValueError(f'{questions_path} 结构错误: ' + '; '.join(errors[:10]))
            if pollution:
                raise ValueError(f'{questions_path} 发现 LaTeX 转义污染: {pollution[:20]}')
            total_pollution.extend(pollution)

            subject = manifest.get('subject') or pref.get('subject')
            grade = normalize_grade(manifest.get('grade') or pref.get('grade'))
            paper_title = manifest.get('paper_title') or pref.get('paper_title') or paper_dir
            paper_id = manifest.get('paper_id') or paper_dir or safe_paper_dir_name(paper_title)
            lib = qb / grade / subject
            lib.mkdir(parents=True, exist_ok=True)
            questions_file = lib / '_questions.json'
            papers_file = lib / '_papers.json'
            bank_questions = load_json_file(questions_file)
            bank_papers = load_json_file(papers_file)
            existing = {(q.get('source_paper'), q.get('question_no')) for q in bank_questions}

            image_root = lib / 'images' / safe_paper_dir_name(paper_id)
            copied = 0
            for name in zf.namelist():
                if name.startswith(f'{paper_dir}/figures/') and not name.endswith('/'):
                    dest = image_root / 'figures' / Path(name).name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(name))
                    copied += 1
                elif name.startswith(f'{paper_dir}/original/') and not name.endswith('/'):
                    dest = image_root / 'original' / Path(name).name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(name))
                    copied += 1

            added = skipped = 0
            for q in questions:
                qno = f"第{q.get('question_no')}题"
                if (paper_title, qno) in existing:
                    skipped += 1
                    continue
                content = q.get('content') or {}
                raw_answer = q.get('answer_raw')
                raw_solution = q.get('solution_raw')
                has_source_answer = bool(raw_answer)
                figures = q.get('figures') or []
                original_image = q.get('original_image')
                record = {
                    'id': f'Q-{next_id:05d}',
                    'subject': subject,
                    'grade': grade,
                    'source_paper': paper_title,
                    'question_no': qno,
                    'question_text': build_question_text(content),
                    'options': build_options(content.get('options')),
                    'answer': str(raw_answer) if has_source_answer else '待教师确认',
                    'answer_source': '真题答案' if has_source_answer else '未提供（待补答案）',
                    'analysis': str(raw_solution) if raw_solution else '原题包未提供答案解析，待补答案/解析。',
                    'knowledge_point': '待标注',
                    'exam_point': '待标注',
                    'difficulty': '中等',
                    'question_type': normalize_question_type(q.get('question_type_raw')),
                    'exam_date': exam_date,
                    'exam_type': exam_type,
                    'images': [f"images/{safe_paper_dir_name(paper_id)}/{fig.get('path')}" for fig in figures],
                    'original_image': f"images/{safe_paper_dir_name(paper_id)}/{original_image}" if original_image else '',
                    'raw_item_id': q.get('question_id'),
                    'source_file': manifest.get('source_file'),
                    'score': q.get('score'),
                    'conversion_confidence': (q.get('conversion') or {}).get('confidence'),
                    'conversion_requires_review': (q.get('conversion') or {}).get('requires_review'),
                    'conversion_issues': (q.get('conversion') or {}).get('issues') or [],
                }
                bank_questions.append(record)
                next_id += 1
                added += 1

            if not any(p.get('name') == paper_title for p in bank_papers):
                bank_papers.append({
                    'name': paper_title,
                    'subject': subject,
                    'grade': grade,
                    'date': exam_date,
                    'exam_date': exam_date,
                    'exam_type': exam_type,
                    'question_count': sum(1 for q in bank_questions if q.get('source_paper') == paper_title),
                    'source_file': manifest.get('source_file'),
                    'paper_id': paper_id,
                    'schema_version': manifest.get('schema_version'),
                    'answer_present': bool(manifest.get('has_source_answers')),
                })

            save_json_file(questions_file, bank_questions)
            save_json_file(papers_file, bank_papers)
            total_added += added
            total_skipped += skipped
            print(f"[入库] {grade}/{subject}《{paper_title}》新增 {added} 题，跳过重复 {skipped} 题，复制图片 {copied} 个")

    meta['next_id'] = next_id
    libs = []
    for qfile in qb.glob('*/*/_questions.json'):
        grade = qfile.parts[-3]
        subject = qfile.parts[-2]
        qdata = load_json_file(qfile)
        pdata = load_json_file(qfile.parent / '_papers.json')
        img_dir = qfile.parent / 'images'
        image_dirs = len([p for p in img_dir.iterdir() if p.is_dir()]) if img_dir.exists() else 0
        libs.append({'grade': grade, 'subject': subject, 'count': len(qdata), 'papers': len(pdata), 'images_dirs': image_dirs})
    meta['libraries'] = sorted(libs, key=lambda x: (x['grade'], x['subject']))
    save_json_file(meta_path, meta)
    update_index(qb, meta)
    print(f"[完成] 新增 {total_added} 题，跳过 {total_skipped} 题，next_id=Q-{next_id:05d}，LaTeX污染=0")


def main():
    parser = argparse.ArgumentParser(description='标准中间题目包快速入库')
    parser.add_argument('--zip', dest='zip_path', help='标准中间题目包 zip 路径')
    parser.add_argument('--download-name', help='下载目录内 zip 文件名；也可传绝对路径')
    parser.add_argument('--latest-download', action='store_true', help='自动使用下载目录最新 zip（避开中文路径传参乱码）')
    parser.add_argument('--workspace', default=str(Path.cwd()), help='工作区根目录，默认当前目录')
    parser.add_argument('--exam-date', default='2025-09-06', help='考试日期 YYYY-MM-DD；未知时可后续修正')
    parser.add_argument('--exam-type', default='单元测试', help='考试类型，默认 单元测试')
    parser.add_argument('--validate', action='store_true', help='导入完成后自动运行 validate_question_bank.py')
    args = parser.parse_args()

    if args.latest_download:
        zip_path = latest_download_zip()
    elif args.download_name:
        zip_path = download_zip_by_name(args.download_name)
    elif args.zip_path:
        zip_path = Path(args.zip_path)
    else:
        raise SystemExit('请提供 --zip、--download-name 或 --latest-download')
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    workspace = Path(args.workspace).resolve()
    import_package(zip_path.resolve(), workspace, args.exam_date, args.exam_type)
    if args.validate:
        import subprocess
        subprocess.check_call([
            sys.executable,
            str(Path(__file__).resolve().parent / 'validate_question_bank.py'),
            '--workspace', str(workspace),
        ], cwd=str(workspace))


if __name__ == '__main__':
    main()
