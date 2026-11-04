"""Build transparent provisional references, then time Breeze's load-once pilot.

Provisional reference mode is only for small auditions, not bank promotion or
bulk generation. No machine transcript/speaker label is silently marked reviewed.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time
from bank import read_wav,write_wav

ROOT=Path(__file__).resolve().parent
SOURCES={
    'Announcer':['voice/Announcer/ANN.60.WAV','voice/Announcer/ANN.gameover.WAV',
                 'voice/Announcer/ANN.bdscore.WAV','voice/Announcer/ANN.bescore.WAV',
                 'voice/Announcer/ANN.dsscore.WAV'],
    'TrainingFemale':['voice/Training/Mission1/T1_01.WAV','voice/Training/Mission1/T1_01a.WAV'],
    'BriefingMale':['voice/Training/Briefings/T1.brief02.WAV'],
}

def prepare_references(character_packs=False):
    rows={r['path']:r for r in map(json.loads,(ROOT/'artifacts/asr_candidates.jsonl').read_text().splitlines())}
    selection=dict(SOURCES)
    if character_packs:
        sys.path.insert(0,str(ROOT/'prep'))
        from voice_lab import transcript_seeds
        hints=transcript_seeds()
        def comparable(text):
            return ''.join(c for c in text.casefold() if c.isalnum() or c.isspace()).split()
        # Use normal speech hints as candidate transcript only if ASR has actually run.
        for pack in [*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),*(f'Derm{i}' for i in range(1,4)),'Bot1']:
            actual={name.casefold():name for name in rows if name.startswith('voice/'+pack+'/')}
            durations={r['path']:r['seconds'] for r in json.loads((ROOT/'artifacts/audio_inventory.json').read_text())}
            names=[];seconds=0
            for stem in ('gbl.hi','gbl.thanks','def.base','att.base','rep.generator','slf.def.base',
                         'need.support','def.flag','att.generator','def.generator','def.sensors','def.objective',
                         'rep.base','slf.att.base','gbl.bye'):
                name=actual.get(f'voice/{pack}/{stem}.wav'.casefold())
                # Reject evident ASR/hint disagreement; do not feed "we're our generator"
                # as if it were a complete, correct "repair our generator" reference.
                agreed=name and stem in hints and comparable(rows[name]['text'])==comparable(hints[stem])
                if agreed and rows[name]['text'].strip() and seconds+durations[name]+0.15<=15:
                    names.append(name);seconds+=durations[name]+0.15
                if seconds>=8:break
            if seconds<3:raise ValueError('Insufficient complete ASR candidate reference for '+pack)
            selection[pack]=names
    result=[]
    for speaker,names in selection.items():
        pieces=[];texts=[];used=[]
        for name in names:
            if name not in rows:raise ValueError('ASR incomplete: '+name)
            row=rows[name]
            if not row['text'].strip():raise ValueError('Empty transcript: '+name)
            rate,audio=read_wav(ROOT/'artifacts/pcm24k'/name)
            if len(audio)/rate>20:raise ValueError('Reference too long; select another complete clip: '+name)
            pieces.extend(audio);pieces.extend([0]*round(rate*0.15))
            texts.append(row['text']);used.append({'path':name,'asr_text':row['text']})
        duration=len(pieces)/rate
        if not 3<=duration<=20:raise ValueError(f'{speaker}: reference {duration:.2f}s outside 3–20s')
        out=ROOT/'artifacts/references-provisional'/f'{speaker}.wav'
        if out.exists():
            history=out.parent/'history'/hashlib.sha256(out.read_bytes()).hexdigest()[:16]
            history.mkdir(parents=True,exist_ok=True)
            for p in (out,out.with_suffix('.txt'),out.with_suffix('.json')):
                if p.exists():shutil.copy2(p,history/p.name)
        write_wav(out,rate,pieces)
        out.with_suffix('.txt').write_text(' '.join(texts))
        receipt={'speaker_id':speaker,'sources':used,'seconds':duration,'speaker_verified':False,
                 'transcript_verified':False,'reference_verified':False,
                 'warning':'ASR-derived, unreviewed reference for small cloning audition only. Training role is a hypothesis until acoustic review.',
                 'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
        out.with_suffix('.json').write_text(json.dumps(receipt,indent=2))
        result.append(receipt)
    (ROOT/'artifacts/references-provisional/references.json').write_text(json.dumps(result,indent=2))
    return result

def output_folder(tag='pilot'):
    if not tag or Path(tag).name!=tag or tag in ('.','..'):
        raise ValueError('Directory-safe output tag required')
    artifacts=(ROOT/'artifacts').resolve()
    out=(artifacts/tag).resolve()
    if not out.is_relative_to(artifacts):raise ValueError('Output tag escapes artifacts directory')
    return out

def generate(speakers,allow_provisional=False,expressions=False,text_jobs=None,include_events=True,output_tag='pilot',fast=False):
    permission_path=ROOT/'artifacts/permissions/rights-attestation.json'
    permission=json.loads(permission_path.read_text()) if permission_path.exists() else {}
    if (permission.get('performer_consent_and_recording_rights_confirmed') is not True or
            not set(speakers)<=set(permission.get('voice_ids',[]))):
        raise PermissionError('Breeze requires explicit performer consent and reference-recording rights. '
            'Record confirmed permissions for these voice IDs in artifacts/permissions/rights-attestation.json; '
            'do not infer consent from public game assets or noncommercial use.')
    if not allow_provisional:raise ValueError('Provisional refs require an explicit audition-only flag')
    out=output_folder(output_tag)
    source=ROOT/'environments/breeze-tts'
    sys.path.insert(0,str(source))
    import numpy as np
    import soundfile as sf
    import torch
    import infer as official
    from breeze_infer.runtime import load_runtime,resolve_device,set_all_seeds,update_generation_config_for_breeze
    from breeze_infer.templates import prepare_inputs,get_template,select_template_name
    from models.fast_streaming import FastBreezeStreamingRuntime,FastStreamingConfig
    sys.path.insert(0,str(ROOT/'prep'))
    from expression_support import EMOTIONS,BREEZE_EVENTS
    if not torch.cuda.is_available():raise RuntimeError('CUDA GPU required for preparation')
    out.mkdir(parents=True,exist_ok=True)
    jobs=[]
    for speaker in speakers:
        ref=ROOT/'artifacts/references-provisional'/f'{speaker}.wav'
        receipt=json.loads(ref.with_suffix('.json').read_text())
        assert hashlib.sha256(ref.read_bytes()).hexdigest()==receipt['sha256']
        for emotion,instruction in (EMOTIONS.items() if expressions else [('neutral',None)]):
            jobs.append({'id':speaker+'_'+emotion,'speaker_id':speaker,'emotion':emotion,'kind':'speech',
                'text':'Welcome to the server, Cody. Defend the generator!','instruction':instruction,
                'ref_audio_path':str(ref),'ref_text':ref.with_suffix('.txt').read_text()})
        if expressions and include_events:
            for event,text in BREEZE_EVENTS.items():
                jobs.append({'id':speaker+'_event_'+event,'speaker_id':speaker,'emotion':'neutral','kind':'event_candidate',
                    'event':event,'text':text,'instruction':None,'ref_audio_path':str(ref),'ref_text':ref.with_suffix('.txt').read_text()})
    if text_jobs is not None:
        for job in text_jobs:
            speaker=job['speaker_id']
            ref=ROOT/'artifacts/references-provisional'/f'{speaker}.wav'
            if (speaker not in speakers or Path(job['id']).name!=job['id'] or not job['text'].strip()
                    or job.get('emotion') not in EMOTIONS or job.get('kind')!='speech'):
                raise ValueError('Invalid corpus job identity or mode')
            if job['instruction']!=EMOTIONS[job['emotion']]:raise ValueError('Unselected voice direction')
            if job['ref_audio_path']!=str(ref) or job['ref_text']!=ref.with_suffix('.txt').read_text():
                raise ValueError('Corpus job reference changed')
        jobs=jobs+text_jobs if expressions else text_jobs
    torch.cuda.reset_peak_memory_stats()
    t0=time.perf_counter()
    tokenizer,model,codec=load_runtime(ROOT/'environments/breeze-model',device=resolve_device(),attn_implementation='eager')
    update_generation_config_for_breeze(model)
    cfg=FastStreamingConfig(max_new_tokens=official.MAX_NEW_TOKENS,max_seq_len=official.MAX_SEQ_LEN,
        fast_all=fast,fast_text_encoder=False,fast_backbone_prefill=False,fast_backbone_decode=False,
        fast_depth_decoder=False,fast_codec=False,repetition_penalty=official.REPETITION_PENALTY)
    runtime=FastBreezeStreamingRuntime(model,codec,cfg,tokenizer=tokenizer)
    torch.cuda.synchronize();load_seconds=time.perf_counter()-t0
    manifest=out/'pilot-jobs.json'
    records=json.loads(manifest.read_text()) if manifest.exists() else []
    by_id={r['id']:r for r in records}
    previous=out/'run-card.json'
    if previous.exists():
        history=out/'run-history';history.mkdir(exist_ok=True)
        old=previous.read_bytes()
        (history/(hashlib.sha256(old).hexdigest()[:16]+'.json')).write_bytes(old)
    for job in jobs:
        path=out/(job['id']+'.wav')
        if path.exists():
            old=json.loads(path.with_suffix('.json').read_text())
            if any(old.get(k)!=job.get(k) for k in ('text','instruction','ref_audio_path','ref_text')):
                raise ValueError('Refusing to overwrite changed pilot context: '+job['id'])
            if hashlib.sha256(path.read_bytes()).hexdigest()!=old['sha256']:
                raise ValueError('Existing pilot checksum mismatch')
            by_id[job['id']]=old
            print('Reusing checksum-matched pilot:',job['id'],flush=True)
            continue
        start=time.perf_counter();set_all_seeds(42)
        request={'id':job['id'],'speaker':'S0',**{k:job[k] for k in ('text','ref_audio_path','ref_text')}}
        if job['instruction']:request['instruction']=job['instruction']
        inputs=prepare_inputs(tokenizer,codec,model,[request],get_template(select_template_name(request)),
            guidance_scale=4.0 if job['instruction'] else 1.0,guidance_scale_ref=None,guidance_scale_ins=None)
        chunks=[];steps=[0]
        for chunk in runtime.iter_audio_chunks(inputs,request_id=job['id'],seed=42,
                token_observer=lambda _:steps.__setitem__(0,steps[0]+1)):
            chunks.append(np.asarray(chunk.audio,dtype=np.float32).reshape(-1))
        torch.cuda.synchronize()
        audio=np.concatenate(chunks) if chunks else np.zeros(0,dtype=np.float32)
        if not np.isfinite(audio).all() or not len(audio) or not np.any(audio):
            raise RuntimeError('Invalid/silent audio; reject this pilot')
        complete=bool(len(audio)) and steps[0]<official.MAX_NEW_TOKENS
        sf.write(path,audio,runtime.sample_rate,subtype='PCM_16')
        record={**job,'source':str(path),'seed':42,'audio_seconds':len(audio)/runtime.sample_rate,
            'wall_seconds':time.perf_counter()-start,'codec_steps':steps[0],'complete_by_frame_guard':complete,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'verified':False,
            'absolute_peak':float(np.max(np.abs(audio))),
            'clipped_fraction':float(np.mean(np.abs(audio)>=0.9999)),
            'speaker_verified':False,'transcript_verified':False,'reference_verified':False,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        path.with_suffix('.json').write_text(json.dumps(record,indent=2));by_id[job['id']]=record
        manifest.write_text(json.dumps(list(by_id.values()),indent=2))
        print(json.dumps({k:record[k] for k in ('id','audio_seconds','wall_seconds','complete_by_frame_guard','peak_allocated_bytes')}),flush=True)
        if not complete:raise RuntimeError('Incomplete generation; reject, never slice or train on this result')
    versions={}
    for name in ('torch','torchaudio','transformers','qwen-tts','numpy','soundfile'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    (out/'run-card.json').write_text(json.dumps({'model':json.loads((ROOT/'environments/breeze-model-revision.json').read_text()),
        'source_revision':(ROOT/'environments/breeze-source-revision.txt').read_text().strip(),
        'load_seconds':load_seconds,'gpu':torch.cuda.get_device_name(),'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory,
        'dependencies':versions,'jobs':list(by_id.values()),'this_run_job_ids':[j['id'] for j in jobs],
        'fast_path':fast,'large_corpus_authorized_by_pilot':False},indent=2))
    print('========== DONE ==========',flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['references','generate'])
    p.add_argument('--speakers',nargs='+',default=['Announcer']);p.add_argument('--allow-provisional-reference',action='store_true')
    p.add_argument('--expressions',action='store_true');p.add_argument('--character-packs',action='store_true')
    p.add_argument('--jobs',type=Path,help='Explicit small corpus job list with the same reference and review status')
    p.add_argument('--no-events',action='store_true',help='Speech emotion auditions only, without event carriers')
    p.add_argument('--output-tag',default='pilot',help='Separate artifacts subdirectory for an independent generation shard; default unchanged')
    p.add_argument('--fast',action='store_true',help='Opt in to the official accelerated streaming stages; default remains eager')
    a=p.parse_args()
    if a.stage=='references':print(json.dumps(prepare_references(a.character_packs),indent=2))
    else:generate(a.speakers,a.allow_provisional_reference,a.expressions,
                   json.loads(a.jobs.read_text()) if a.jobs else None,not a.no_events,a.output_tag,a.fast)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        out=ROOT/'artifacts/pilot';out.mkdir(parents=True,exist_ok=True)
        (out/'last-failure.json').write_text(json.dumps({'type':type(exc).__name__,'message':str(exc)},indent=2))
        raise
