"""MFA phone-alignment bridge. Automatic output stays unverified until reviewed."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from bank import extract,read_wav,write_index
from phonetics import Lexicon,normalize,base

def stage(jobs,lexicon,corpus):
    corpus=Path(corpus);corpus.mkdir(parents=True,exist_ok=True)
    metadata={}
    for job in jobs:
        if job.get('kind','speech')!='speech':
            continue
        p=lexicon.pronounce(job['text']) # refuse unknown words before spending alignment time
        source=Path(job['source'])
        key=hashlib.sha256((str(source)+job['text']).encode()).hexdigest()[:20]
        # Each known/candidate voice has its own MFA speaker directory, never Training as one voice.
        speaker=job['speaker_id']
        if not speaker or Path(speaker).name!=speaker:
            raise ValueError('Directory-safe, explicit speaker ID required')
        folder=corpus/speaker;folder.mkdir(exist_ok=True)
        shutil.copy2(source,folder/(key+'.wav'))
        (folder/(key+'.lab')).write_text(' '.join(p['words']))
        metadata[speaker+'/'+key]={**job,'source':str(source.resolve()),'normalized':p['normalized']}
    (corpus/'jobs.json').write_text(json.dumps(metadata,indent=2))
    return metadata

def export_dictionary(lexicon,path):
    with Path(path).open('w') as f:
        for word,prons in {**lexicon.entries,**lexicon.overrides}.items():
            if ' ' in word:continue
            if not isinstance(prons[0],(list,tuple)):prons=[prons]
            for pron in prons:
                f.write(word+'\t'+' '.join(pron)+'\n')

def convert(textgrid_path,job):
    import textgrid
    tg=textgrid.TextGrid.fromFile(str(textgrid_path))
    tier=next(t for t in tg.tiers if t.name=='phones' or t.name.endswith(' - phones'))
    rate,audio=read_wav(job['source']); duration=len(audio)/rate
    phones=[];prev=0
    for interval in tier.intervals:
        start,end=float(interval.minTime),float(interval.maxTime)
        label=interval.mark.strip()
        if end-start<=0:continue
        if start>prev+0.000001:phones.append({'label':'SIL','start':prev,'end':start})
        # spn is unknown/noise, not certified silence; keep it explicit.
        label='SIL' if label in ('','sil','sp') else ('SPN' if label=='spn' else label)
        phones.append({'label':label,'start':start,'end':min(end,duration),'variant':'canonical',
                       'closure_verified':False})
        prev=end
    if prev<duration:phones.append({'label':'SIL','start':prev,'end':duration})
    # Merge adjacent silence intervals; internal pauses remain explicit units.
    merged=[]
    for p in phones:
        if merged and p['label']=='SIL' and merged[-1]['label']=='SIL':merged[-1]['end']=p['end']
        else:merged.append(p)
    return {**job,'phones':merged,'source_sha256':hashlib.sha256(Path(job['source']).read_bytes()).hexdigest(),
            'aligner':'Montreal Forced Aligner 3.3.9 / english_us_arpa',
            'alignment_verified':False,'emotion_verified':False,'speaker_verified':False,
            'transcript_verified':False,'reviewer':None,
            'notes':'Automatic candidate. Review boundaries, silence, allophones and stop closures/releases before promotion.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--jobs',type=Path,required=True)
    p.add_argument('--lexicon',type=Path,required=True);p.add_argument('--overrides',type=Path)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--mfa',type=Path,required=True)
    p.add_argument('--model',default='english_us_arpa')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    lex=Lexicon.load(a.lexicon,a.overrides); jobs=json.loads(a.jobs.read_text())
    corpus=a.out/'corpus';meta=stage(jobs,lex,corpus)
    dictionary=a.out/'lexicon.dict';export_dictionary(lex,dictionary)
    aligned=a.out/'aligned'
    env=dict(os.environ)
    env['PATH']=str(a.mfa.resolve().parent)+os.pathsep+env.get('PATH','')
    subprocess.run([str(a.mfa.resolve()),'align',str(corpus.resolve()),str(dictionary.resolve()),a.model,str(aligned.resolve()),
                    '--clean','--overwrite','--num_jobs','2','--output_format','long_textgrid'],check=True,env=env)
    units=[]
    for name,job in meta.items():
        alignment=convert(aligned/(name+'.TextGrid'),job)
        dest=a.out/'alignment-json'/(name+'.json');dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(alignment,indent=2))
        units.extend(extract(alignment,a.out/'candidate-bank'))
    receipt=write_index(a.out/'candidate-bank',units)
    (a.out/'receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    print('========== DONE ==========',flush=True)

if __name__=='__main__':main()
