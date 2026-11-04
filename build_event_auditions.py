"""Playable stock/event-cue review set; filename and ASR labels remain hypotheses."""
import csv
import hashlib
import html
import json
from pathlib import Path
import re
import shutil

root=Path(__file__).resolve().parent
out=root/'artifacts/event-auditions';out.mkdir(parents=True,exist_ok=True)
with (root/'artifacts/expressive_review.csv').open() as f:stock=list(csv.DictReader(f))
asr={r['path']:r for r in map(json.loads,(root/'artifacts/asr_candidates.jsonl').read_text().splitlines())}
seen={r['source_path'] for r in stock}
extra=[]
for name,row in asr.items():
    if name not in seen and re.search(r'\b(?:ha[ ,!.-]*){3,}',row['text'],re.I):
        extra.append({'source_path':name,'speaker_id':name.split('/')[1] if '/Training/' not in name else '',
                      'candidate_label':'possible_laugh','candidate_type':'ASR hint, not classification'})
entries=[]
for row in [*stock,*extra]:
    source=root/'artifacts/pcm24k'/row['source_path']
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    file='original_'+digest[:20]+'.wav';shutil.copy2(source,out/file)
    entries.append({'source':row['source_path'],'file':file,'sha256':digest,'speaker_candidate':row['speaker_id'],
        'label_candidate':row['candidate_label'],'kind':'stock_candidate','hint_type':row['candidate_type'],
        'asr_text':asr.get(row['source_path'],{}).get('text',''),'speaker_verified':'false','event_verified':'false',
        'boundaries_verified':'false','emotion':'','event_type':'','start_seconds':'','end_seconds':'','contains_carrier_speech':'','notes':''})
for event in ('laugh','sigh','cough','clear_throat'):
    source=root/'artifacts/pilot'/f'Announcer_event_{event}.wav'
    if not source.exists():continue
    file='generated_'+source.name;shutil.copy2(source,out/file)
    entries.append({'source':str(source),'file':file,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'speaker_candidate':'Announcer','label_candidate':event,'kind':'generated_carrier_sentence',
        'hint_type':'documented cue; actual event not verified','asr_text':'','speaker_verified':'false','event_verified':'false',
        'boundaries_verified':'false','emotion':'','event_type':'','start_seconds':'','end_seconds':'','contains_carrier_speech':'true','notes':'Audition and isolate; never export the whole carrier as an event.'})
review=out/'review.csv'
if review.exists():
    old_bytes=review.read_bytes();history=out/'review-history';history.mkdir(exist_ok=True)
    (history/(hashlib.sha256(old_bytes).hexdigest()[:16]+'.csv')).write_bytes(old_bytes)
    with review.open() as f:old={(r['file'],r['sha256']):r for r in csv.DictReader(f)}
    for row in entries:
        previous=old.get((row['file'],row['sha256']),{})
        for key in ('speaker_verified','event_verified','boundaries_verified','emotion','event_type','start_seconds','end_seconds','contains_carrier_speech','notes'):
            if key in previous:row[key]=previous[key]
with (out/'review.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(entries[0]));w.writeheader();w.writerows(entries)
(out/'manifest.json').write_text(json.dumps(entries,indent=2))
parts=['<!doctype html><meta charset="utf-8"><title>Vocal event review</title><h1>Unverified vocal-event candidates</h1>',
    '<p>A spoken aww is not crying. Spoken cheers are not wordless sounds. A cue does not prove an event occurred. '
    'Generated carrier sentences must be listened to and bounded before export.</p>']
for e in entries:
    parts.append('<h3>'+html.escape(e['speaker_candidate']+' / '+e['label_candidate']+' / '+e['kind'])+'</h3>'+
                 '<audio controls preload="none" src="'+e['file']+'"></audio><p>ASR hint: '+html.escape(e['asr_text'])+'</p>')
(out/'index.html').write_text('\n'.join(parts))
print(json.dumps({'stock_candidates':len(stock),'additional_ASR_hints':len(extra),'generated_carriers':len(entries)-len(stock)-len(extra),
                  'verified_events':0,'bytes':sum(p.stat().st_size for p in out.iterdir() if p.is_file())},indent=2))
print('========== DONE ==========',flush=True)
