#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课堂录音预处理工具（ffmpeg 滤波链）
来源：2026-09-05 吴嘉敏听评课实战对比验证（原 _pretest.py / _vad2.py，已参数化归整）。

背景：远端收音/录制音量偏低的课堂录音直接转写识别率差。实测 4 种滤波方案后
总结出 3 档预设（具体对比数据见 CHANGELOG 2026-09-05）：

  standard  高通80Hz去低频隆隆声 + EBU R128 响度标准化（两遍，保留相对响度差）——默认首选
  enhance   在 standard 基础上加 dynaudnorm 动态增益——适合音量忽大忽小/整体偏弱的录音
  denoise   降噪声 + 强动态增益 + 更保守响度——适合环境噪声明显的录音

用法：
  python audio_preprocess.py <音频文件> [-o 输出wav] [--plan standard|enhance|denoise]

输出 16k 单声道 wav，可直接交给 transcribe_audio.py / transcribe_long.py。
"""
import argparse
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PLANS = {
    # 实战验证的滤波链（勿随意改动参数，均为对比测试后的最优值）
    'standard': 'highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11',
    'enhance':  'highpass=f=80,dynaudnorm=f=200:g=20,loudnorm=I=-16:TP=-1.5:LRA=11',
    'denoise':  'highpass=f=100,afftdn=nf=-25,dynaudnorm=f=200:g=20,loudnorm=I=-18:TP=-1:LRA=11',
}


def main():
    ap = argparse.ArgumentParser(description='课堂录音预处理')
    ap.add_argument('input', help='输入音频文件')
    ap.add_argument('-o', '--output', help='输出 wav（默认输入同目录 processed_16k.wav）')
    ap.add_argument('--plan', choices=list(PLANS), default='standard',
                    help='预处理方案（默认 standard）')
    args = ap.parse_args()

    src = os.path.abspath(args.input)
    if not os.path.exists(src):
        sys.exit(f'文件不存在: {src}')
    out = os.path.abspath(args.output) if args.output \
        else os.path.join(os.path.dirname(src), 'processed_16k.wav')

    filt = PLANS[args.plan]
    print(f'方案: {args.plan}\n滤波链: {filt}')
    r = subprocess.run(
        ['ffmpeg', '-y', '-v', 'error', '-i', src,
         '-af', filt, '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le', out],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        sys.exit(f'ffmpeg 失败: {r.stderr[:500]}')
    print(f'完成: {out} ({os.path.getsize(out)/1024/1024:.1f} MB)')


if __name__ == '__main__':
    main()
