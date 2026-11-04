"""Export whole reviewed vocal events; generated carrier speech is not an event."""
import hashlib
from pathlib import Path
from bank import read_wav,write_wav
from renderer import EVENTS,EMOTIONS

def export_events(reviews,output):
    output=Path(output);result=[]
    for r in reviews:
        if not all(r.get(k) is True for k in ('speaker_verified','event_verified','boundaries_verified')):
            continue
        if r['event'] not in EVENTS or r.get('emotion','neutral') not in EMOTIONS:
            raise ValueError('Invalid event or emotion')
        if r.get('contains_carrier_speech') is not False:
            raise ValueError('Explicitly exclude carrier speech before event export')
        if r.get('event_type') not in ('wordless','spoken_cheer','other_vocalization'):
            raise ValueError('Classify speech versus wordless sound; do not guess from cues')
        source_sha=hashlib.sha256(Path(r['source']).read_bytes()).hexdigest()
        if r.get('source_sha256',r.get('sha256'))!=source_sha:
            raise ValueError('Event source lacks a matching review checksum')
        rate,audio=read_wav(r['source'])
        a,b=round(r['start']*rate),round(r['end']*rate)
        if not 0<=a<b<=len(audio):raise ValueError('Invalid event boundaries')
        sample=audio[a:b]
        digest=hashlib.sha256(sample.tobytes()).hexdigest()
        path='events/'+digest[:24]+'.wav';write_wav(output/path,rate,sample)
        result.append({'id':digest[:24],'speaker_id':r['speaker_id'],'emotion':r.get('emotion','neutral'),
            'event':r['event'],'event_type':r['event_type'],'file':path,'rate':rate,'verified':True,
            'sha256':hashlib.sha256((output/path).read_bytes()).hexdigest(),
            'source':r['source'],'start':r['start'],'end':r['end'],'reviewer':r.get('reviewer')})
    return result
