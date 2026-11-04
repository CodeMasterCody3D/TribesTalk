"""Freeze completed job receipts without reading a live aggregate manifest."""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--id-pattern',action='append',default=[])
p.add_argument('--output',type=Path,required=True);p.add_argument('--expected',type=int)
a=p.parse_args();jobs=[]
for path in sorted((root/'artifacts/pilot').glob('*.json')):
    if a.id_pattern and not any(fnmatch.fnmatchcase(path.stem,pattern) for pattern in a.id_pattern):continue
    job=json.loads(path.read_text())
    if not isinstance(job,dict) or job.get('id')!=path.stem:continue
    source=path.with_suffix('.wav')
    if Path(job['source']).resolve()!=source.resolve():raise ValueError('Job audio path changed')
    if not job.get('complete_by_frame_guard'):raise ValueError('Incomplete generation: '+job['id'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=job['sha256']:raise ValueError('Changed audio: '+job['id'])
    jobs.append(job)
if a.expected is not None and len(jobs)!=a.expected:raise ValueError(f'Expected {a.expected} jobs, found {len(jobs)}')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(jobs,indent=2))
print(json.dumps({'completed_jobs':len(jobs),'snapshot':str(a.output)},indent=2))
print('========== DONE ==========',flush=True)
