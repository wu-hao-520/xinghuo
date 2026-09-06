import json
p=r'e:\codebuddy\workflow\classroom-evaluation-output\transcripts\20260905_吴嘉敏_郭子辰_transcript.json'
d=json.load(open(p,encoding='utf-8'))
with open(r'e:\codebuddy\workflow\.codebuddy\tmpwork\transcript.txt','w',encoding='utf-8') as f:
 for s in d['segments']:
  f.write(f"[{s['start']/60:6.1f}-{s['end']/60:6.1f}] {s['text']}\n")
print(len(d['text']))
