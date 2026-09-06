import json, os, glob
ROOT=r'e:\codebuddy\workflow'; work=os.path.join(ROOT,'.codebuddy','tmpwork','_long_work')
rows=[]
with open(os.path.join(work,'chunks.jsonl'),encoding='utf-8') as f:
 for line in f:
  if line.strip(): rows.append(json.loads(line))
for p in glob.glob(os.path.join(ROOT,'.codebuddy','tmpwork','result_*.json')):
 rows.append(json.load(open(p,encoding='utf-8')))
rows.sort(key=lambda x:x['chunk_idx'])
segs=[]
for r in rows: segs.extend(r['segments'])
segs.sort(key=lambda x:x['start'])
out={'file_name':'吴嘉敏9.5听评课.m4a','file_path':r'C:\Users\Administrator\Desktop\吴嘉敏9.5听评课.m4a','model':'faster-whisper-small(long-chunked)','language':'zh','duration':123.6,'text':''.join(s['text'] for s in segs),'segments':segs}
outp=os.path.join(ROOT,'classroom-evaluation-output','transcripts','20260905_吴嘉敏_郭子辰_transcript.json')
with open(outp,'w',encoding='utf-8') as f: json.dump(out,f,ensure_ascii=False,indent=2)
print(outp, len(segs), len(out['text']))
