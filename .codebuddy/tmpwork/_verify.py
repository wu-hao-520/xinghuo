import glob,os
root=r'e:\codebuddy\workflow\classroom-evaluation-output\reports'
for p in glob.glob(os.path.join(root,'20260905*')):
 print(os.path.basename(p), os.path.getsize(p))
