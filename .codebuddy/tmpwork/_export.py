import os, sys
ROOT=r'e:\codebuddy\workflow'
script=os.path.join(ROOT,'.codebuddy','skills','classroom-audio-evaluation','scripts','export_report.py')
report=os.path.join(ROOT,'classroom-evaluation-output','reports','20260905_吴嘉敏老师_郭子辰_听评课报告.md')
outdir=os.path.join(ROOT,'classroom-evaluation-output','reports')
sys.argv=[script,report,'--teacher','吴嘉敏','--student','郭子辰','--date','2026-09-05','-f','pdf','--output-dir',outdir]
exec(compile(open(script,encoding='utf-8').read(),script,'exec'),{'__name__':'__main__','__file__':script})
