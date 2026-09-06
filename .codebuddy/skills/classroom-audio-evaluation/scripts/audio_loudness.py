#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课堂录音响度分析工具
来源：2026-09-05 吴嘉敏听评课实战验证（原 _loud.py / _analyze_loud.py / _probe.py，已参数化归整）。

功能：
  1. 探测音频时长（ffprobe）
  2. 解码为 16k 单声道 wav（供后续转写/预处理复用）
  3. 30s 窗口 RMS 响度时间线（dB）
  4. 识别「清晰讲解段」（≥ 阈值 dB 的相邻窗口合并），用于估算教师有效讲授时长

用法：
  python audio_loudness.py <音频文件> [-o 输出目录] [--threshold -31] [--window 30]

经验参数（实战验证）：
  - 远端/录制音量偏低的课堂录音，清晰讲解窗口阈值 -31 dB 比较合适；
    录音设备较好时可上调到 -28 dB 左右。
"""
import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def probe_duration(src):
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'json', src],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    return float(json.loads(r.stdout)['format']['duration'])


def main():
    ap = argparse.ArgumentParser(description='课堂录音响度分析')
    ap.add_argument('input', help='音频文件（m4a/mp3/wav 等）')
    ap.add_argument('-o', '--output', help='输出目录（默认音频同目录下 _loudness_work/）')
    ap.add_argument('--threshold', type=float, default=-31.0,
                    help='清晰讲解窗口阈值 dB（默认 -31）')
    ap.add_argument('--window', type=float, default=30.0,
                    help='分析窗口秒数（默认 30）')
    args = ap.parse_args()

    src = os.path.abspath(args.input)
    if not os.path.exists(src):
        sys.exit(f'文件不存在: {src}')

    out_dir = os.path.abspath(args.output) if args.output \
        else os.path.join(os.path.dirname(src), '_loudness_work')
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, 'full_16k_mono.wav')

    dur = probe_duration(src)
    print(f'时长: {dur/60:.1f} min')

    # 解码 16k mono
    if not os.path.exists(wav):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src,
                        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le', wav],
                       capture_output=True)
    w = wave.open(wav, 'rb')
    n, sr = w.getnframes(), w.getframerate()
    print(f'采样率 {sr}, 帧数 {n}, {n/sr/60:.1f} min')

    # 窗口 RMS
    step = int(args.window * sr)
    rows = []
    for i in range(0, n, step):
        w.setpos(i)
        a = np.frombuffer(w.readframes(min(step, n - i)),
                          dtype=np.int16).astype(np.float32) / 32768.0
        if a.size == 0:
            continue
        rms = float(np.sqrt(np.mean(a * a)))
        rows.append([round(i / sr), round(20 * np.log10(rms + 1e-10), 1)])
    w.close()

    with open(os.path.join(out_dir, 'loudness.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False)

    # 清晰讲解段（相邻达标窗口合并）
    groups, cur = [], None
    for t, db in rows:
        if db >= args.threshold:
            cur = [t, t + args.window, db] if cur is None \
                else [cur[0], t + args.window, max(cur[2], db)]
        elif cur:
            groups.append(cur)
            cur = None
    if cur:
        groups.append(cur)

    print(f'\n清晰讲解段 (>= {args.threshold} dB, {args.window:.0f}s 窗口合并):')
    total = 0.0
    for g in groups:
        d = g[1] - g[0]
        total += d
        print(f'  {g[0]/60:6.1f} -> {g[1]/60:6.1f} min  '
              f'({int(d//60)}m{int(d%60):02d}s)  peak={g[2]:.1f}dB')
    print(f'\n总清晰讲解时长约: {total/60:.1f} min（占比 {total/dur*100:.0f}%）')

    # 时间线（每 2 min）
    print(f'\n=== {args.window:.0f}s 响度时间线（每 2min 采样） ===')
    for i in range(0, len(rows), int(120 / args.window)):
        t, db = rows[i]
        print(f'  {int(t//60):03d}:{int(t%60):02d}  {db:6.1f}  '
              + '#' * max(0, int((db + 45) / 1.5)))


if __name__ == '__main__':
    main()
