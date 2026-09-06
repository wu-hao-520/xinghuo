import os, shutil, subprocess, sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = r"e:\codebuddy\workflow"
WORK = os.path.join(ROOT, ".codebuddy", "tmpwork")
os.makedirs(WORK, exist_ok=True)

src = r"C:\Users\Administrator\Desktop\吴嘉敏9.5听评课.m4a"
dst = os.path.join(WORK, "audio_src.m4a")
if not os.path.exists(dst):
    shutil.copy2(src, dst)
    print("copied", flush=True)

out_json = os.path.join(WORK, "transcript_long.json")
script = os.path.join(ROOT, ".codebuddy", "skills", "classroom-audio-evaluation", "scripts", "transcribe_long.py")

cmd = [sys.executable, script, dst, "-o", out_json, "--chunk", "600",
       "--model", "small", "--preprocess", "standard"]
print("CMD:", " ".join(cmd), flush=True)
p = subprocess.run(cmd, cwd=ROOT)
print("rc:", p.returncode, flush=True)
