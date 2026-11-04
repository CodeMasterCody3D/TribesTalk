"""Kaggle-only source download, decode, inventory and ASR candidate preparation."""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'prep'))
import voice_lab as lab
import expression_support

def load_asr_model():
    from faster_whisper import WhisperModel
    lock_path=ROOT/'toolchain-lock.json'
    if lock_path.exists():
        from huggingface_hub import snapshot_download
        spec=json.loads(lock_path.read_text())['asr_model']
        model=snapshot_download(spec['repo'],revision=spec['revision'])
    else:
        model='large-v3'
    return WhisperModel(model,device='cuda',compute_type='float16',device_index=0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asr', action='store_true')
    ap.add_argument('--all-asr', action='store_true')
    ap.add_argument('--skip-prep', action='store_true', help='Reuse completed download/decode receipt')
    args = ap.parse_args()
    if not str(ROOT).startswith('/kaggle/'):
        raise RuntimeError('Run preparation on the assigned Kaggle VM, not the laptop')
    out = ROOT/'artifacts'
    out.mkdir(exist_ok=True)
    raw, pcm = out/'originals', out/'pcm24k'
    start = time.time()
    if not args.skip_prep:
        lab.download_assets(raw, workers=8)
    rows = lab.build_review(out/'review.csv')
    expression_support.build_expressive_review(lab,out/'expressive_review.csv')
    details = []
    for i,row in enumerate(rows if not args.skip_prep else []):
        dest = pcm/row['path']
        if not dest.exists():
            lab.decode_pcm(raw/row['path'],dest)
        with wave.open(str(dest)) as w:
            details.append({'path':row['path'],'seconds':w.getnframes()/w.getframerate(),
                            'pcm_bytes':dest.stat().st_size,'rate':w.getframerate()})
        if (i+1)%200 == 0:
            print('decoded',i+1,flush=True)
    if not args.skip_prep:
        (out/'audio_inventory.json').write_text(json.dumps(details,indent=2))
        (out/'download_decode_receipt.json').write_text(json.dumps({
            'files':len(details),'original_bytes':sum(p.stat().st_size for p in raw.rglob('*') if p.is_file()),
            'pcm_bytes':sum(d['pcm_bytes'] for d in details),'audio_seconds':sum(d['seconds'] for d in details),
            'seconds':time.time()-start,'revision':lab.read_manifest()['revision'],
        },indent=2))
    else:
        receipt=json.loads((out/'download_decode_receipt.json').read_text())
        assert receipt['files']==len(rows), 'Incomplete source preparation'
    if args.asr:
        model = load_asr_model()
        targets = rows if args.all_asr else [r for r in rows if r['group'] in ('Announcer','Training')]
        transcript_path = out/'asr_candidates.jsonl'
        done = {json.loads(line)['path'] for line in transcript_path.read_text().splitlines()} if transcript_path.exists() else set()
        with transcript_path.open('a',buffering=1) as f:
            for row in targets:
                if row['path'] in done:
                    continue
                t0=time.time()
                segments,info = model.transcribe(str(pcm/row['path']),language='en',beam_size=5,
                    vad_filter=True,word_timestamps=True,condition_on_previous_text=False)
                segments=[asdict(s) for s in segments]
                result={'path':row['path'],'text':' '.join(s['text'].strip() for s in segments),
                        'segments':segments,'seconds':time.time()-t0,'speaker_id':row['speaker_id'],
                        'speaker_verified':False,'transcript_verified':False,
                        'asr_model':'Systran/faster-whisper-large-v3','language_probability':info.language_probability}
                f.write(json.dumps(result)+'\n')
                print('ASR',row['path'],result['text'],flush=True)
    print('========== DONE ==========',flush=True)

if __name__ == '__main__':
    main()
