#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课堂录音转写脚本 v2.0
支持多种音频格式：MP3, WAV, M4A, FLAC, OGG, AAC 等
支持批量处理多个录音文件

三通道自动切换（按速度/可用性自动选择）：
  1. 云端 Whisper API（openai SDK，需 OPENAI_API_KEY）
  2. 本地 faster-whisper（CTranslate2 int8 量化 + VAD 静音跳过，CPU 加速首选）
  3. 本地 openai-whisper（torch，回退方案）
"""

import os
import sys
import json
import tempfile
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Windows GBK 控制台兼容：stdout/stderr 统一 UTF-8 容错输出，避免非 ASCII 字符崩溃
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ──────────────────────────────────────────────
#  依赖检查
# ──────────────────────────────────────────────
def _check_faster_whisper():
    """检查 faster-whisper（CTranslate2 量化加速）是否可用。"""
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False

def _check_local():
    """检查本地 openai-whisper 是否可用（torch 不崩溃即算可用）。"""
    try:
        import torch  # noqa: F401
        import whisper  # noqa: F401
        return True
    except Exception:
        return False

def _check_openai_sdk():
    """检查 openai SDK 是否已安装。"""
    try:
        import openai
        return True
    except Exception:
        return False

FASTER_OK  = _check_faster_whisper()
LOCAL_OK   = _check_local()
OPENAI_OK  = _check_openai_sdk()

# 进程内模型缓存：批量转写时复用已加载的模型，避免每个文件都重新加载。
# 原实现每次转写都重新加载模型，批量 N 个文件就要加载 N 次，是转写慢的重要原因之一。
_MODEL_CACHE = {}

def _cpu_threads() -> int:
    """返回合理的 CPU 线程数。

    CTranslate2(faster-whisper) 在 CPU 上线程数超过物理核心数时会因线程竞争/上下文切换
    反而变慢，故取逻辑核心数的一半（超线程机器约等于物理核心数），并保证至少 4 线程。
    """
    return max(4, (os.cpu_count() or 4) // 2)

# ──────────────────────────────────────────────
#  辅助函数
# ──────────────────────────────────────────────
SUPPORTED_FORMATS = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma', '.opus']

def validate_audio(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"音频文件不存在: {path}")
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的音频格式 {path.suffix}，支持: {', '.join(SUPPORTED_FORMATS)}")
    return path

def ensure_wav(input_path: Path, temp_dir: Path) -> Path:
    """将任意音频转为 16kHz 单声道 WAV，方便 Whisper 和 API 使用。"""
    wav_path = temp_dir / f"{input_path.stem}_16k.wav"
    cmd = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
        str(wav_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 转换失败:\n{result.stderr}")
    return wav_path

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def write_srt(segments, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp(seg['start'])
            end   = format_timestamp(seg['end'])
            text  = seg['text'].strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

# ──────────────────────────────────────────────
#  通道 1：本地 faster-whisper（CTranslate2 int8 量化，CPU 首选）
# ──────────────────────────────────────────────
def transcribe_faster(audio_path: Path, model_size='base', language='zh') -> dict:
    # 国内网络默认走 hf-mirror 镜像下载模型，避免连接 huggingface.co 超时
    os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
    # 禁用 xet 协议（镜像不支持 xet 的 CAS 重建，会导致 401）
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    from faster_whisper import WhisperModel
    cache_key = ('faster', model_size)
    model = _MODEL_CACHE.get(cache_key)
    if model is None:
        cpu_threads = _cpu_threads()
        print(f"  [faster-whisper] 加载 {model_size} 模型（int8 量化，首次运行自动下载，{cpu_threads} 线程）...")
        model = WhisperModel(model_size, device='cpu', compute_type='int8',
                             cpu_threads=cpu_threads)
        _MODEL_CACHE[cache_key] = model
    print(f"  [faster-whisper] 开始转写（VAD 跳过静音）: {audio_path.name}")
    segments_iter, info = model.transcribe(
        str(audio_path), language=language, task='transcribe',
        beam_size=5, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500))
    segments = []
    chunks = []
    for seg in segments_iter:
        t = seg.text.strip()
        chunks.append(t)
        segments.append({'start': round(seg.start, 3),
                         'end': round(seg.end, 3), 'text': t})
    return {'text': ''.join(chunks), 'segments': segments,
            'duration': round(getattr(info, 'duration', 0.0), 3)}

# ──────────────────────────────────────────────
#  通道 2：本地 openai-whisper（torch，回退）
# ──────────────────────────────────────────────
def transcribe_local(audio_path: Path, model_size='base', language='zh') -> dict:
    # 注意：不要设置 OMP_NUM_THREADS=1 等单线程环境变量。openai-whisper 在 CPU 上依赖
    # torch 的多线程矩阵运算加速，强制单线程会让多核机器只用 1 核，转写慢 10 倍以上
    # （历史转写产物 model=whisper-base 走的就是此通道，单线程是当时慢的直接原因）。
    import whisper
    cache_key = ('whisper', model_size)
    model = _MODEL_CACHE.get(cache_key)
    if model is None:
        print(f"  [本地] 加载 Whisper {model_size} 模型（首次较慢）...")
        model = whisper.load_model(model_size)
        _MODEL_CACHE[cache_key] = model
    print(f"  [本地] 开始转写: {audio_path.name}")
    result = model.transcribe(str(audio_path), language=language, task='transcribe', verbose=False)
    # 补齐 duration 字段（openai-whisper 返回结果无该字段，之前恒为 0，导致报告时长显示为 0）
    if result.get('segments'):
        result['duration'] = round(result['segments'][-1]['end'], 3)
    else:
        result['duration'] = 0.0
    return result

# ──────────────────────────────────────────────
#  通道 2：云端 Whisper API（OpenAI 兼容）
# ──────────────────────────────────────────────
def transcribe_cloud(audio_path: Path, api_key: str,
                     model='whisper-1', base_url=None,
                     language=None) -> dict:
    import openai
    client_kwargs = {'api_key': api_key}
    if base_url:
        client_kwargs['base_url'] = base_url
    client = openai.OpenAI(**client_kwargs)

    print(f"  [云端] 调用 Whisper API: {audio_path.name}")
    with open(audio_path, 'rb') as f:
        if language:
            resp = client.audio.transcriptions.create(
                model=model, file=f, language=language)
        else:
            resp = client.audio.transcriptions.create(
                model=model, file=f)

    text = resp.text
    # API 只返回纯文本，我们用分句 heuristic 构造 segments
    import re
    sentences = re.split(r'([。！？\n]+)', text)
    segments = []
    start = 0.0
    avg_speed = 4.0  # 约 4 字/秒
    for i in range(0, len(sentences) - 1, 2):
        seg_text = (sentences[i] + sentences[i + 1]).strip()
        if not seg_text:
            continue
        duration = max(1.0, len(seg_text) / avg_speed)
        segments.append({'start': start, 'end': start + duration, 'text': seg_text})
        start += duration + 0.3

    return {'text': text, 'segments': segments}

# ──────────────────────────────────────────────
#  统一入口
# ──────────────────────────────────────────────
def transcribe(audio_path, *, output_dir=None, output_format='json',
               model_size='base', language='zh',
               api_key=None, base_url=None, cloud_model='whisper-1') -> dict:
    """
    统一转写函数，按以下顺序尝试可用通道：
      1. api_key  → 云端 Whisper API（最可靠）
      2. LOCAL_OK → 本地 Whisper
      3. 否则 → 报错
    """
    path = validate_audio(Path(audio_path))

    # ── 预处理：转 WAV ──────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wav_path = ensure_wav(path, tmp_path)

        # ── 选择通道（速度优先：faster-whisper ＞ openai-whisper）──
        used_model = None
        if api_key:
            used_model = cloud_model
            result = transcribe_cloud(wav_path, api_key,
                                      model=cloud_model, base_url=base_url,
                                      language=language if language != 'zh' else None)
        elif FASTER_OK:
            try:
                used_model = f"faster-whisper-{model_size}"
                result = transcribe_faster(wav_path, model_size=model_size, language=language)
            except Exception as e:
                print(f"  [警告] faster-whisper 失败（{e}），回退到 openai-whisper ...")
                if not LOCAL_OK:
                    raise
                used_model = f"whisper-{model_size}"
                result = transcribe_local(wav_path, model_size=model_size, language=language)
        elif LOCAL_OK:
            used_model = f"whisper-{model_size}"
            result = transcribe_local(wav_path, model_size=model_size, language=language)
        else:
            raise RuntimeError(
                "无法转写：本地 faster-whisper / openai-whisper 均不可用，"
                "且未提供 API Key。\n"
                "解决方案：\n"
                "  ① 设置环境变量  OPENAI_API_KEY=sk-...  使用云端 API\n"
                "  ② 或执行 pip install faster-whisper 后重新运行"
            )

    # ── 保存结果 ───────────────────────────────
    if output_dir is None:
        output_dir = path.parent
    else:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    base_name = path.stem
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    data = {
        'file_name': path.name,
        'file_path': str(path.absolute()),
        'model':     used_model or f"whisper-{model_size}",
        'language':  language,
        'timestamp': ts,
        'duration':  result.get('duration', 0),
        'text':      result['text'],
        'segments':  result.get('segments', [])
    }

    outputs = []
    if output_format in ('json', 'all'):
        p = Path(output_dir) / f"{base_name}_transcript_{ts}.json"
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        outputs.append(('JSON', p))
    if output_format in ('txt', 'all'):
        p = Path(output_dir) / f"{base_name}_transcript_{ts}.txt"
        with open(p, 'w', encoding='utf-8') as f:
            f.write(f"课堂录音转写结果\n")
            f.write(f"文件: {path.name}\n时间: {ts}\n\n{result['text']}")
        outputs.append(('TXT', p))
    if output_format in ('srt', 'all'):
        p = Path(output_dir) / f"{base_name}_transcript_{ts}.srt"
        write_srt(result.get('segments', []), p)
        outputs.append(('SRT', p))

    print(f"[OK] 转写完成: {path.name}")
    for label, fp in outputs:
        print(f"  {label}: {fp.name}")

    return data

# ──────────────────────────────────────────────
#  批量处理
# ──────────────────────────────────────────────
def batch_transcribe(input_dir, *, output_dir=None, output_format='json',
                     model_size='base', language='zh',
                     api_key=None, base_url=None, cloud_model='whisper-1',
                     recursive=False):
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise NotADirectoryError(f"输入路径不是目录: {input_dir}")

    files = []
    for fmt in SUPPORTED_FORMATS:
        pattern = f'**/*{fmt}' if recursive else f'*{fmt}'
        files.extend(input_dir.glob(pattern))

    if not files:
        print(f"未在 {input_dir} 中找到音频文件（支持: {', '.join(SUPPORTED_FORMATS)}）")
        return []

    print(f"找到 {len(files)} 个音频文件")
    results = []
    for i, f in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {f.name}")
        try:
            r = transcribe(f, output_dir=output_dir, output_format=output_format,
                           model_size=model_size, language=language,
                           api_key=api_key, base_url=base_url, cloud_model=cloud_model)
            results.append(r)
        except Exception as e:
            print(f"  [X] 失败: {e}")

    print(f"\n批量完成: {len(results)}/{len(files)} 个文件")
    return results

# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description='课堂录音转写工具 v2.0（本地 Whisper + 云端 API）')
    p.add_argument('input', help='音频文件或目录路径')
    p.add_argument('-o', '--output',   help='输出目录')
    p.add_argument('-m', '--model',    default='base',
                   choices=['tiny','base','small','medium','large'],
                   help='本地模型大小（默认 base，越小越快、准确率越低）；云端忽略此参数')
    p.add_argument('-l', '--language',  default='zh',
                   help='语言代码，如 zh / en（默认 zh）')
    p.add_argument('-f', '--format',   default='json',
                   choices=['json','txt','srt','all'],
                   help='输出格式（默认 json）')
    p.add_argument('-r', '--recursive', action='store_true', help='递归子目录')
    p.add_argument('--batch',          action='store_true',  help='批量处理（输入为目录）')
    p.add_argument('--api-key',        default=os.environ.get('OPENAI_API_KEY'),
                   help='云端 API Key（默认从 OPENAI_API_KEY 环境变量读取）')
    p.add_argument('--base-url',       default=os.environ.get('OPENAI_BASE_URL'),
                   help='API 端点（如使用代理），默认 OpenAI 官方')
    p.add_argument('--cloud-model',    default='whisper-1',
                   help='云端模型名（默认 whisper-1）')

    args = p.parse_args()

    try:
        if args.batch or Path(args.input).is_dir():
            batch_transcribe(
                args.input, output_dir=args.output, output_format=args.format,
                model_size=args.model, language=args.language,
                api_key=args.api_key, base_url=args.base_url,
                cloud_model=args.cloud_model, recursive=args.recursive)
        else:
            transcribe(
                args.input, output_dir=args.output, output_format=args.format,
                model_size=args.model, language=args.language,
                api_key=args.api_key, base_url=args.base_url,
                cloud_model=args.cloud_model)
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
