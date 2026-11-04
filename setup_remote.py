"""Isolated remote dependencies; records exact resolved source/model revisions."""
import argparse
import importlib.metadata
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

def run(*args,**kwargs):
    subprocess.run(list(map(str,args)),check=True,**kwargs)

def create_env(path, system=False):
    if not (path/'bin/python').exists():
        run(sys.executable,'-m','venv','--without-pip',*(['--system-site-packages'] if system else []),path)
    # Kaggle's Python 3.13 omits ensurepip. The host pip can seed an isolated env.
    run(sys.executable,'-m','pip','--python',path/'bin/python','install','pip')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['asr','breeze','align'])
    a=ap.parse_args()
    root=Path(__file__).resolve().parent
    assert str(root).startswith('/kaggle/'), 'Remote only'
    env=root/'environments';env.mkdir(exist_ok=True)
    lock=json.loads((root/'toolchain-lock.json').read_text()) if (root/'toolchain-lock.json').exists() else {}
    start=time.time()
    if a.stage=='asr':
        venv=env/'asr'
        create_env(venv,system=True)
        run(venv/'bin/python','-m','pip','install','faster-whisper==1.2.1','av==16.0.1','cmudict==1.1.1','textgrid==1.6.1',
            'nvidia-cublas-cu12==12.8.4.1','nvidia-cudnn-cu12==9.10.2.21')
        freeze=subprocess.check_output([str(venv/'bin/python'),'-m','pip','freeze'],text=True)
    elif a.stage=='breeze':
        source=env/'breeze-tts'
        if not source.exists():
            if lock.get('breeze_source_revision'):
                run('git','init',source)
                run('git','-C',source,'remote','add','origin','https://github.com/breezeblue-ai/breeze-tts.git')
                run('git','-C',source,'fetch','--depth','1','origin',lock['breeze_source_revision'])
                run('git','-C',source,'checkout','--detach','FETCH_HEAD')
            else:
                run('git','clone','--depth','1','https://github.com/breezeblue-ai/breeze-tts.git',source)
        rev=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        if lock.get('breeze_source_revision') and rev!=lock['breeze_source_revision']:
            raise RuntimeError('Existing Breeze source differs from lock; preserve it and use a separate environment')
        (env/'breeze-source-revision.txt').write_text(rev+'\n')
        venv=env/'breeze'
        create_env(venv)
        run(venv/'bin/python','-m','pip','install','--upgrade','pip')
        requirements=root/'requirements-breeze.lock.txt'
        run(venv/'bin/python','-m','pip','install','-r',requirements if requirements.exists() else source/'requirements.txt')
        # A model revision pin is resolved once and reused on every later invocation.
        pin=env/'breeze-model-revision.json'
        if not pin.exists():
            if lock.get('breeze_model'):
                pin.write_text(json.dumps(lock['breeze_model'],indent=2))
            else:
                with urllib.request.urlopen('https://huggingface.co/api/models/BreezeBlue/Breeze-TTS-2',timeout=60) as r:
                    d=json.load(r)
                pin.write_text(json.dumps({'repo':'BreezeBlue/Breeze-TTS-2','revision':d['sha']},indent=2))
        if lock.get('breeze_model') and json.loads(pin.read_text())!=lock['breeze_model']:
            raise RuntimeError('Existing model revision differs from lock; refusing to replace it')
        run(venv/'bin/python','-c',
            'import json,sys; from huggingface_hub import snapshot_download; d=json.load(open(sys.argv[1])); snapshot_download(d["repo"], revision=d["revision"],local_dir=sys.argv[2])',pin,env/'breeze-model')
        freeze=subprocess.check_output([str(venv/'bin/python'),'-m','pip','freeze'],text=True)
    else:
        # MFA is isolated from both Torch environments and supplies its own Kaldi dependencies.
        micromamba=env/'bin/micromamba'
        if not micromamba.exists():
            archive=env/'micromamba.tar.bz2'
            urllib.request.urlretrieve('https://micro.mamba.pm/api/micromamba/linux-64/latest',archive)
            run('tar','-xjf',archive,'-C',env,'bin/micromamba')
        prefix=env/'mfa'
        run(micromamba,'create','-y','-p',prefix,'-c','conda-forge','montreal-forced-aligner=3.3.9','python=3.11')
        for kind,name in [('acoustic','english_us_arpa'),('dictionary','english_us_arpa')]:
            run(micromamba,'run','-p',prefix,'mfa','model','download',kind,name)
        base=Path.home()/'Documents/MFA/pretrained_models'
        for key,path in (('mfa_acoustic_sha256',base/'acoustic/english_us_arpa.zip'),
                         ('mfa_dictionary_sha256',base/'dictionary/english_us_arpa.dict')):
            if lock.get(key) and hashlib.sha256(path.read_bytes()).hexdigest()!=lock[key]:
                raise RuntimeError('Downloaded MFA model differs from tested lock: '+str(path))
        freeze=subprocess.check_output([str(micromamba),'list','-p',str(prefix),'--json'],text=True)
    (env/(a.stage+'-resolved.txt')).write_text(freeze)
    (env/(a.stage+'-setup.json')).write_text(json.dumps({'stage':a.stage,'seconds':time.time()-start},indent=2))
    print('========== DONE ==========',flush=True)

if __name__=='__main__':main()
