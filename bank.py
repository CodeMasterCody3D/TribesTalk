"""Extract reviewed aligned phones into midpoint-to-midpoint PCM16 units.

Alignment JSON contains source WAV, speaker_id, emotion, text, aligner metadata,
review flags and phones [{label,start,end,variant?,anchor?,protected_release?}].
Times are seconds. Stop anchors must be explicitly checked in stable closure,
before protected release; unreviewed stops remain candidates, never production.
"""
from __future__ import annotations
from array import array
import hashlib
import json
from pathlib import Path
import sys
import wave
from phonetics import base

STOPS = {'P','B','T','D','K','G'}

def read_wav(path):
    with wave.open(str(path),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getcomptype()) != (1,2,'NONE'):
            raise ValueError('Expected mono PCM16 WAV')
        rate = w.getframerate()
        audio = array('h', w.readframes(w.getnframes()))
        if sys.byteorder != 'little':
            audio.byteswap()
        return rate,audio

def write_wav(path,rate,audio):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    a=array('h',audio)
    if sys.byteorder != 'little':
        a.byteswap()
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(a.tobytes())

def safe_path(root,name):
    root=Path(root).resolve()
    p=(root/name).resolve()
    if p != root and root not in p.parents:
        raise ValueError('Path outside bank')
    return p

def extract(alignment, output, handle_ms=5, reviewed_only=False):
    if not 2.5 <= handle_ms <= 5:
        raise ValueError('Handles must support a 5–10 ms total crossfade')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    source=Path(alignment['source'])
    rate,audio=read_wav(source)
    duration=len(audio)/rate
    phones=alignment['phones']
    prev=0
    for p in phones:
        if not p['label'] or not 0 <= p['start'] < p['end'] <= duration or p['start'] < prev-0.000001:
            raise ValueError('Invalid/overlapping phone intervals')
        if p['start']-prev > 0.002:
            raise ValueError('Alignment gap: represent silence explicitly')
        prev=p['end']
    anchors=[]
    for p in phones:
        anchor=p.get('anchor',(p['start']+p['end'])/2)
        if not p['start'] <= anchor <= p['end']:
            raise ValueError('Anchor outside phone')
        protected=p.get('protected_release')
        if protected and (not p['start'] <= protected[0] < protected[1] <= p['end'] or anchor >= protected[0]):
            raise ValueError('Stop anchor must precede protected release')
        anchors.append(round(anchor*rate))
    h=round(rate*handle_ms/1000)
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    if alignment.get('source_sha256') and alignment['source_sha256']!=source_sha:
        raise ValueError('Alignment source checksum changed')
    units=[]
    for i,(left,right) in enumerate(zip(phones,phones[1:])):
        a,b=anchors[i:i+2]
        if b <= a:
            raise ValueError('Non-increasing anchors')
        first,last=max(0,a-h),min(len(audio),b+h)
        sample=audio[first:last]
        if not sample:
            continue
        protected_ok=True
        for p,anchor in ((left,a),(right,b)):
            if base(p['label']) in STOPS:
                rel=p.get('protected_release')
                protected_ok &= bool(p.get('closure_verified') and rel and
                                     anchor+h <= round(rel[0]*rate))
        verified=all(alignment.get(k) is True for k in (
            'speaker_verified','transcript_verified','alignment_verified','emotion_verified')) and protected_ok
        if reviewed_only and not verified:
            continue
        key=f'{source_sha[:16]}-{i:04d}'
        path=f'units/{key}.wav'
        write_wav(output/path,rate,sample)
        units.append({'id':key,'phones':[left['label'],right['label']],
            'variants':[left.get('variant','canonical'),right.get('variant','canonical')],
            'context':{'previous':phones[i-1]['label'] if i else 'SIL',
                       'next':phones[i+2]['label'] if i+2<len(phones) else 'SIL'},
            'speaker_id':alignment['speaker_id'],'emotion':alignment.get('emotion','neutral'),
            'file':path,'rate':rate,'left_handle':a-first,'right_handle':last-b,
            'core_samples':b-a,'source_sha256':source_sha,'source':str(source),
            'start_seconds':a/rate,'end_seconds':b/rate,
            'sha256':hashlib.sha256((output/path).read_bytes()).hexdigest(),
            'verified':verified,'release_safe':protected_ok,
            'quality':{'clipped_fraction':sum(abs(x)>=32760 for x in sample)/len(sample),
                       'alignment_score':alignment.get('alignment_score'),
                       'aligner':alignment.get('aligner'), 'reviewer':alignment.get('reviewer')}})
    return units

def write_index(output, units, events=()):
    output=Path(output)
    ids=[u['id'] for u in units]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate unit IDs')
    speakers=sorted({x['speaker_id'] for x in [*units,*events]})
    d={'schema':1,'license':'Private development; Breeze-derived outputs research/noncommercial only.',
       'speakers':speakers,'units':units,'events':list(events)}
    d['content_digest']=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
    (output/'index.json').write_text(json.dumps(d,indent=2))
    return {'unit_count':len(units),'verified_units':sum(u['verified'] for u in units),
            'bytes':sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}
