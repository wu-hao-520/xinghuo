#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长课堂录音分块转写工具（断点续传）
来源：2026-09-05 吴嘉敏 2 小时听评课实战验证（原 _transcribe_full.py，已参数化归整）。

适用场景：超过 30 分钟的长录音。一次整段转写一旦中断就要全部重来；
本工具按块（默认 10 min）转写，每块结果立即追加写入 jsonl，中断后重跑自动跳过已完成块。

用法：
  python transcribe_long.py <音频文件> [-o 输出json] [--chunk 600] [--model base]
                           [--preprocess standard|enhance|denoise|none]

流程：
  1. （可选）audio_preprocess 滤波提升识别率
  2. faster-whisper int8 分块转写（绝对时间偏移已换算）
  3. 结束后合并为标准 transcript JSON（与 transcribe_audio.py 输出格式一致，
     可直接归档到 classroom-evaluation-output/transcripts/）
"""
import argparse
import json
import os
import subprocess
import sys
import time
import wave

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# 与 audio_preprocess.py 保持一致的滤波方案
PRE_PLANS = {
    'standard': 'highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11',
    'enhance':  'highpass=f=80,dynaudnorm=f=200:g=20,loudnorm=I=-16:TP=-1.5:LRA=11',
    'denoise':  'highpass=f=100,afftdn=nf=-25,dynaudnorm=f=200:g=20,loudnorm=I=-18:TP=-1:LRA=11',
}


def main():
    ap = argparse.ArgumentParser(description='长录音分块转写（断点续传）')
    ap.add_argument('input', help='音频文件')
    ap.add_argument('-o', '--output', help='最终输出 JSON（默认音频同目录 <名>_transcript_long.json）')
    ap.add_argument('--chunk', type=float, default=600.0, help='分块秒数（默认 600）')
    ap.add_argument('--model', default='base', help='faster-whisper 模型（默认 base）')
    ap.add_argument('--preprocess', choices=list(PRE_PLANS) + ['none'], default='none',
                    help='预处理方案（默认 none，长录音建议 standard）')
    args = ap.parse_args()

    src = os.path.abspath(args.input)
    if not os.path.exists(src):
        sys.exit(f'文件不存在: {src}')
    work = os.path.join(os.path.dirname(src), '_long_work')
    os.makedirs(work, exist_ok=True)

    # 1) 预处理 → 16k mono wav
    wav = os.path.join(work, 'input_16k.wav')
    if not os.path.exists(wav):
        af = PRE_PLANS[args.preprocess] if args.preprocess != 'none' else 'anull'
        print(f'解码/预处理（{args.preprocess}）...', flush=True)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-af', af,
                        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le', wav],
                       capture_output=True)

    w = wave.open(wav, 'rb')
    total = w.getnframes() / w.getframerate()
    w.close()
    print(f'总时长 {total/60:.1f} min', flush=True)

    # 2) faster-whisper 分块转写 + 断点续传
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    from faster_whisper import WhisperModel
    threads = max(4, (os.cpu_count() or 4) // 2)
    m = WhisperModel(args.model, device='cpu', compute_type='int8', cpu_threads=threads)

    out_jsonl = os.path.join(work, 'chunks.jsonl')
    done = set()
    if os.path.exists(out_jsonl):
        with open(out_jsonl, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(json.loads(line)['chunk_idx'])
    nchunks = int(total // args.chunk) + (1 if total % args.chunk > 1 else 0)
    print(f'共 {nchunks} 块，已完成 {len(done)} 块', flush=True)

    fout = open(out_jsonl, 'a', encoding='utf-8')
    for idx in range(nchunks):
        if idx in done:
            continue
        t0 = idx * args.chunk
        dur = min(args.chunk, total - t0)
        if dur < 5:
            break
        cw = os.path.join(work, f'_c{idx:03d}.wav')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t0), '-t', str(dur),
                        '-i', wav, '-ar', '16000', '-ac', '1',
                        '-acodec', 'pcm_s16le', cw], capture_output=True)
        tt = time.time()
        segs = list(m.transcribe(cw, language='zh', beam_size=5,
                                 condition_on_previous_text=False,
                                 vad_filter=False, temperature=[0.0])[0])
        el = time.time() - tt
        out_segs = [{'start': round(t0 + s.start, 2), 'end': round(t0 + s.end, 2),
                     'text': s.text.strip()} for s in segs]
        json.dump({'chunk_idx': idx, 'abs_start': t0, 'abs_end': t0 + dur,
                   'nseg': len(segs), 'elapsed': round(el, 1),
                   'segments': out_segs}, fout, ensure_ascii=False)
        fout.write('\n')
        fout.flush()
        os.remove(cw)
        print(f'[块 {idx:03d}/{nchunks}] {t0/60:5.1f}-{(t0+dur)/60:5.1f}min '
              f'nseg={len(segs)} {el:.0f}s ({dur/el:.1f}x) :: '
              + ' '.join(s.text.strip() for s in segs[:3])[:60], flush=True)
    fout.close()

    # 3) 合并为标准 transcript JSON
    all_segs = []
    with open(out_jsonl, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                all_segs.extend(json.loads(line)['segments'])
    all_segs.sort(key=lambda s: s['start'])
    out_json = os.path.abspath(args.output) if args.output \
        else os.path.join(os.path.dirname(src), f'{os.path.splitext(os.path.basename(src))[0]}_transcript_long.json')
    data = {
        'file_name': os.path.basename(src),
        'file_path': src,
        'model': f'faster-whisper-{args.model}(long-chunked)',
        'language': 'zh',
        'duration': round(total, 1),
        'text': ''.join(s['text'] for s in all_segs),
        'segments': all_segs,
    }
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'\nALL DONE: {out_json}（{len(all_segs)} 段）')


if __name__ == '__main__':
    main()
