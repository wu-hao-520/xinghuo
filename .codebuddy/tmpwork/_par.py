import json, os, subprocess, sys, time, wave
from concurrent.futures import ProcessPoolExecutor
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

ROOT = r"e:\codebuddy\workflow"
WORK = os.path.join(ROOT, ".codebuddy", "tmpwork", "_long_work")
WAV = os.path.join(WORK, "input_16k.wav")
JSONL = os.path.join(WORK, "chunks.jsonl")
CHUNK = 600.0
MODEL = sys.argv[1] if len(sys.argv) > 1 else "small"

w = wave.open(WAV, 'rb')
total = w.getnframes() / w.getframerate()
w.close()
nchunks = int(total // CHUNK) + (1 if total % CHUNK > 1 else 0)

done = set()
if os.path.exists(JSONL):
    with open(JSONL, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                done.add(json.loads(line)['chunk_idx'])

todo = [i for i in range(nchunks) if i not in done]
print(f'total={total/60:.1f}min nchunks={nchunks} done={sorted(done)} todo={todo}', flush=True)


def work(idx):
    t0 = idx * CHUNK
    dur = min(CHUNK, total - t0)
    cw = os.path.join(WORK, f'_p{idx:03d}.wav')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t0), '-t', str(dur),
                    '-i', WAV, '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le', cw],
                   capture_output=True)
    from faster_whisper import WhisperModel
    m = WhisperModel(MODEL, device='cpu', compute_type='int8', cpu_threads=4)
    tt = time.time()
    segs = list(m.transcribe(cw, language='zh', beam_size=5,
                             condition_on_previous_text=False,
                             vad_filter=False, temperature=[0.0])[0])
    el = time.time() - tt
    out = {'chunk_idx': idx, 'abs_start': t0, 'abs_end': t0 + dur, 'nseg': len(segs),
           'elapsed': round(el, 1),
           'segments': [{'start': round(t0 + s.start, 2), 'end': round(t0 + s.end, 2),
                         'text': s.text.strip()} for s in segs]}
    try:
        os.remove(cw)
    except Exception:
        pass
    return out


if todo:
    with ProcessPoolExecutor(max_workers=len(todo)) as ex:
        for r in ex.map(work, todo):
            with open(JSONL, 'a', encoding='utf-8') as f:
                json.dump(r, f, ensure_ascii=False)
                f.write('\n')
            print(f'[块 {r["chunk_idx"]:03d}] nseg={r["nseg"]} {r["elapsed"]:.0f}s :: '
                  + ' '.join(s['text'] for s in r['segments'][:3])[:60], flush=True)

print('PARALLEL DONE', flush=True)
