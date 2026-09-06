import json, os, subprocess, sys, time, wave
idx = int(sys.argv[1])
ROOT = r"e:\codebuddy\workflow"
WORK = os.path.join(ROOT, ".codebuddy", "tmpwork", "_long_work")
WAV = os.path.join(WORK, "input_16k.wav")
CHUNK = 600.0
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
w = wave.open(WAV, 'rb'); total = w.getnframes()/w.getframerate(); w.close()
t0 = idx * CHUNK; dur = min(CHUNK, total-t0)
cw = os.path.join(WORK, f'_p{idx:03d}.wav')
subprocess.run(['ffmpeg','-y','-v','error','-ss',str(t0),'-t',str(dur),'-i',WAV,'-ar','16000','-ac','1','-acodec','pcm_s16le',cw], capture_output=True)
from faster_whisper import WhisperModel
m = WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=4)
tt=time.time()
segs=list(m.transcribe(cw, language='zh', beam_size=5, condition_on_previous_text=False, vad_filter=False, temperature=[0.0])[0])
r={'chunk_idx':idx,'abs_start':t0,'abs_end':t0+dur,'nseg':len(segs),'elapsed':round(time.time()-tt,1),'segments':[{'start':round(t0+s.start,2),'end':round(t0+s.end,2),'text':s.text.strip()} for s in segs]}
with open(os.path.join(WORK,f'result_{idx:03d}.json'),'w',encoding='utf-8') as f: json.dump(r,f,ensure_ascii=False)
try: os.remove(cw)
except OSError: pass
print(f'done {idx} nseg={len(segs)} elapsed={r["elapsed"]:.0f}s', flush=True)
