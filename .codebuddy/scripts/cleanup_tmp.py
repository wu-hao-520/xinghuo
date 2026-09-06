# -*- coding: utf-8 -*-
"""
一键清理临时文件（工作区级通用工具，所有 skill 共用）。

工作区统一约定（各 skill 的 SKILL.md 均已引用）：
- skill 运行中产生的一切临时文件（一次性调试脚本、中间产物、解析缓存）
  统一写入工作区 `_tmp/` 目录，禁止散落在根目录或正式数据目录；
  `_tmp/` 已被根目录 `.gitignore` 排除。
- 运行结束后调用本脚本一次性清理，避免逐个删除文件、多次请求用户批准。

用法（在工作区根目录执行）：
    python .codebuddy/scripts/cleanup_tmp.py            # 清空 _tmp/
    python .codebuddy/scripts/cleanup_tmp.py --dry-run  # 只看会删什么，不删
    python .codebuddy/scripts/cleanup_tmp.py --legacy   # 额外清理根目录遗留的 *_work/ 临时目录

安全约定：
- 只删除 `_tmp/` 目录内容（以及 --legacy 时的根目录 `*_work/` 目录）。
- 不递归扫描其他目录，绝不触碰 .codebuddy/、question-bank/、exam-paper-output/ 等正式目录。
- 根目录散落的 `_*.py` 旧脚本可能被其他流程 import，本脚本不自动删，需人工确认后手动处理。
"""
import argparse
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')


def rmtree_safe(path, dry):
    """删除目录并返回删除的文件数。"""
    n = 0
    for root, _dirs, files in os.walk(path):
        n += len(files)
    if dry:
        print(f"  [dry-run] 将删除目录: {path}（{n} 个文件）")
    else:
        shutil.rmtree(path, ignore_errors=True)
        print(f"  已删除目录: {path}（{n} 个文件）")
    return n


def main():
    ap = argparse.ArgumentParser(description='一键清理 skill 运行产生的临时文件')
    ap.add_argument('--workspace', default='.', help='工作区根目录（默认当前目录）')
    ap.add_argument('--dry-run', action='store_true', help='只预览，不实际删除')
    ap.add_argument('--legacy', action='store_true', help='额外清理根目录遗留的 *_work/ 临时目录')
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    print(f"工作区: {ws}")

    total = 0
    tmp_dir = os.path.join(ws, '_tmp')
    if os.path.isdir(tmp_dir):
        print("清理 _tmp/ ...")
        total += rmtree_safe(tmp_dir, args.dry_run)
    else:
        print("_tmp/ 不存在，无需清理")

    if args.legacy:
        for name in sorted(os.listdir(ws)):
            p = os.path.join(ws, name)
            if os.path.isdir(p) and name.endswith('_work'):
                print(f"清理遗留临时目录 {name}/ ...")
                total += rmtree_safe(p, args.dry_run)

    print(f"完成，共清理 {total} 个文件。")


if __name__ == '__main__':
    main()
