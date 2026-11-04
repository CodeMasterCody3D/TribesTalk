"""Export playable reference/clone comparisons with explicit review status."""
import csv
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--jobs',type=Path);a=p.parse_args()
allowed={j['id'] for j in json.loads(a.jobs.read_text())} if a.jobs else None
out=root/'artifacts/auditions';out.mkdir(parents=True,exist_ok=True)
records=[];parts=['<!doctype html><meta charset="utf-8"><title>Tribes 2 voice auditions</title>',
    '<h1>Tribes 2 voice auditions</h1><p>Private research/noncommercial. Originals and generated clones below. '
    'All references, transcripts and speaker labels remain provisional until reviewed.</p>']
for ref in sorted((root/'artifacts/references-provisional').glob('*.wav')):
    speaker=ref.stem;parts.append('<h2>'+html.escape(speaker)+'</h2>')
    sources=[('Original reference',ref,ref.with_suffix('.txt').read_text())]
    for p in sorted((root/'artifacts/pilot').glob(speaker+'_*.wav')):
        if '_gap_' in p.stem:continue
        if allowed is not None and p.stem not in allowed:continue
        meta=json.loads(p.with_suffix('.json').read_text())
        sources.append(('Breeze generated '+p.stem,p,meta['text']))
    for label,path,text in sources:
        name=('reference_' if label=='Original reference' else 'generated_')+path.name
        shutil.copy2(path,out/name)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        parts.append('<h3>'+html.escape(label)+'</h3><audio controls preload="none" src="'+html.escape(name)+'"></audio><p>'+html.escape(text)+'</p>')
        records.append({'speaker_candidate':speaker,'label':label,'file':name,'sha256':digest,'candidate_text':text,
                        'speaker_verified':'false','transcript_verified':'false','emotion_verified':'false',
                        'event_verified':'false','corrected_transcript':'','notes':''})
(out/'index.html').write_text('\n'.join(parts))
review=out/'review.csv'
if review.exists():
    old_bytes=review.read_bytes();history=out/'review-history';history.mkdir(exist_ok=True)
    (history/(hashlib.sha256(old_bytes).hexdigest()[:16]+'.csv')).write_bytes(old_bytes)
    with review.open() as f:old={(r['file'],r['sha256']):r for r in csv.DictReader(f)}
    for row in records:
        previous=old.get((row['file'],row['sha256']),{})
        for key in ('speaker_verified','transcript_verified','emotion_verified','event_verified','corrected_transcript','notes'):
            if key in previous:row[key]=previous[key]
with (out/'review.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
(out/'comparison.m3u').write_text('#EXTM3U\n'+'\n'.join(r['file'] for r in records)+'\n')
(out/'manifest.json').write_text(json.dumps(records,indent=2))
print(json.dumps({'clips':len(records),'directory':str(out),'bytes':sum(p.stat().st_size for p in out.iterdir() if p.is_file())},indent=2))
print('========== DONE ==========',flush=True)
