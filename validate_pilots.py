"""ASR pre-sort of generated words. Never certifies speaker, emotion or alignment."""
from dataclasses import asdict
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import sys
from phonetics import normalize

if not os.environ.get('T2_VALIDATION_LIBS_READY'):
    dirs=[str(p) for path in sys.path for p in Path(path).glob('nvidia/*/lib') if Path(path).is_dir()]
    env=dict(os.environ,T2_VALIDATION_LIBS_READY='1')
    env['LD_LIBRARY_PATH']=':'.join(dirs+[env.get('LD_LIBRARY_PATH','')])
    os.execve(sys.executable,[sys.executable,__file__,*sys.argv[1:]],env)

from remote_prepare import load_asr_model
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--jobs',type=Path,default=root/'artifacts/pilot/pilot-jobs.json')
p.add_argument('--output',type=Path,default=root/'artifacts/pilot/asr-validation.json');a=p.parse_args()
jobs=json.loads(a.jobs.read_text())
model=load_asr_model()
records=[]
def words(s):return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?",normalize(s))
for job in jobs:
    segments,_=model.transcribe(job['source'],language='en',beam_size=5,condition_on_previous_text=False)
    segments=[asdict(s) for s in segments]
    actual=' '.join(s['text'].strip() for s in segments)
    expected=re.sub(r'\([^)]*\)','',job['text'])
    record={'id':job['id'],'expected':expected,'asr_text':actual,'exact_normalized_words':words(actual)==words(expected),
            'segments':segments,'human_verified':False,'kind':job['kind'],
            'source_sha256':hashlib.sha256(Path(job['source']).read_bytes()).hexdigest()}
    records.append(record);print(json.dumps({k:record[k] for k in ('id','asr_text','exact_normalized_words')}),flush=True)
a.output.write_text(json.dumps(records,indent=2))
print('========== DONE ==========',flush=True)
