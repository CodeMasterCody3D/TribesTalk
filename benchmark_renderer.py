"""Measure actual full-dictionary sample-only rendering, including cache behavior."""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import time
from phonetics import Lexicon
from renderer import Renderer

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--bank',type=Path,default=root/'artifacts/stock-alignment/candidate-bank')
p.add_argument('--speaker',default='Announcer');p.add_argument('--text',default='This looks like a real battle.')
p.add_argument('--tag',default='baseline');a=p.parse_args()
assert str(root).startswith('/kaggle/'), 'Remote numerical test only'
out=root/'artifacts/renderer-benchmark'/a.tag;out.mkdir(parents=True,exist_ok=True)
t0=time.perf_counter()
lex=Lexicon.load(root/'artifacts/reports/cmudict.json',root/'pronunciation-overrides.json')
r=Renderer(a.bank,lex,audition_unverified=True)
startup=time.perf_counter()-t0
prof=cProfile.Profile();prof.enable()
first=r.render(a.speaker,a.text,out/'profile.wav')
prof.disable();stats=pstats.Stats(prof)
top=sorted(stats.stats.items(),key=lambda x:x[1][3],reverse=True)[:12]
uncached=[r.render(a.speaker,a.text,out/'uncached.wav')['wall_seconds'] for _ in range(10)]
r.render(a.speaker,a.text,out/'cached.wav',out/'phrase-cache')
cached=[r.render(a.speaker,a.text,out/'cached.wav',out/'phrase-cache')['wall_seconds'] for _ in range(10)]
report={'text':a.text,'bank':str(a.bank),'voice_quality':'unverified candidate audition; not a production verdict',
        'startup_seconds':startup,'audio_seconds':first['audio_seconds'],'output_bytes':first['bytes'],
        'uncached_seconds':uncached,'cached_seconds':cached,'uncached_mean_seconds':sum(uncached)/10,
        'cached_mean_seconds':sum(cached)/10,'dictionary_words':len(lex.entries),
        'profile':[{'function':f'{key[0]}:{key[1]}:{key[2]}','cumulative_seconds':value[3]} for key,value in top]}
(out/'result.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
print('========== DONE ==========',flush=True)
