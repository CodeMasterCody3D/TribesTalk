"""Durable Kaggle output archive; only explicit artifact and version records."""
import hashlib
import argparse
import json
from pathlib import Path
import tarfile

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path);p.add_argument('--name',default='tribes2-voice-artifacts')
a=p.parse_args()
if Path(a.name).name!=a.name:raise ValueError('Directory-safe archive name required')
output=Path('/kaggle/working')/(a.name+'.tar.gz')
assert str(root).startswith('/kaggle/'), 'Remote archive only'
files=[p for p in (root/'artifacts').rglob('*') if p.is_file() and not p.name.endswith(('.part','.tmp'))]
if a.snapshot:
    # Exclude the live writer's directory, then include only completed, hash-matched jobs.
    files=[p for p in files if root/'artifacts/pilot' not in p.parents]
    for job in json.loads(a.snapshot.read_text()):
        path=Path(job['source']).resolve()
        if root/'artifacts' not in path.parents:raise ValueError('Snapshot source outside artifact directory')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=job['sha256']:
            raise ValueError('Snapshot source changed: '+job['id'])
        files.extend((path,path.with_suffix('.json')))
files.extend(p for p in root.glob('test*results.json'))
for name in ('asr-resolved.txt','breeze-resolved.txt','align-resolved.txt','breeze-source-revision.txt',
             'breeze-model-revision.json','asr-setup.json','breeze-setup.json','align-setup.json'):
    p=root/'environments'/name
    if p.exists():files.append(p)
manifest=[]
for path in sorted(files):
    manifest.append({'path':str(path.relative_to(root)),'bytes':path.stat().st_size,
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
manifest_path=root/(a.name+'-manifest.json')
manifest_path.write_text(json.dumps(manifest,indent=2))
with tarfile.open(output.with_suffix('.gz.part'),'w:gz') as tar:
    for path in sorted(files):tar.add(path,arcname=str(path.relative_to(root)),recursive=False)
    tar.add(manifest_path,arcname='artifact-manifest.json')
output.with_suffix('.gz.part').replace(output)
receipt={'archive':str(output),'bytes':output.stat().st_size,'files':len(files),
         'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
output.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
print('========== DONE ==========',flush=True)
