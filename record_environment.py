"""Record non-secret dependency and model provenance for the remote preparation."""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys

root=Path(__file__).resolve().parent
out=root/'artifacts/provenance';out.mkdir(parents=True,exist_ok=True)
data={'host_python':sys.version,'source_revision':json.loads((root/'prep/assets.json').read_text())['revision'],
      'scripts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.py')},
      'hardware':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv'],text=True)}
cache=Path.home()/'.cache/huggingface/hub/models--Systran--faster-whisper-large-v3/snapshots'
data['asr_model']={'repo':'Systran/faster-whisper-large-v3','cached_snapshots':sorted(p.name for p in cache.iterdir()) if cache.exists() else [],
                   'note':'Snapshot inventory retained; alias resolution was performed by faster-whisper.'}
for name in ('breeze-model-revision.json','breeze-source-revision.txt','asr-setup.json','breeze-setup.json','align-setup.json'):
    path=root/'environments'/name
    if path.exists():data[name]=path.read_text()
for stage in ('asr','breeze'):
    python=root/'environments'/stage/'bin/python'
    if python.exists():
        (out/(stage+'-final-dependencies.txt')).write_text(subprocess.check_output([str(python),'-m','pip','freeze'],text=True))
mfa_root=Path.home()/'Documents/MFA/pretrained_models'
data['mfa_models']=[{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in mfa_root.rglob('*') if p.is_file() and 'english_us_arpa' in p.name]
license_source=root/'environments/breeze-model/LICENSE'
if license_source.exists():
    licenses=out/'licenses';licenses.mkdir(exist_ok=True)
    shutil.copy2(license_source,licenses/'Breeze-TTS-2-LICENSE.txt')
    (licenses/'NOTICE.txt').write_text('Breeze TTS 2 is licensed under the BreezeBlue Research and Non-Commercial '
        'License Agreement. Copyright (c) 2026 RESONIA, INC. All Rights Reserved.\n'
        'Derived from Breeze TTS 2 by BreezeBlue and licensed for research and non-commercial use only.\n'
        'This notice does not grant rights in third-party game recordings or performances.\n')
    data['breeze_license_sha256']=hashlib.sha256(license_source.read_bytes()).hexdigest()
(out/'environment.json').write_text(json.dumps(data,indent=2))
print(json.dumps({'scripts':len(data['scripts']),'asr_snapshots':data['asr_model']['cached_snapshots'],
                  'mfa_files':len(data['mfa_models'])},indent=2))
print('========== DONE ==========',flush=True)
