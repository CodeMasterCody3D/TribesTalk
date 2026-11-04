"""Build a strict reviewed bank, or an explicitly labeled candidate audition bank."""
import argparse
import hashlib
import json
from pathlib import Path
from bank import extract,write_index,safe_path
from events import export_events

def merge_banks(paths,output,include_candidates=False):
    """Preserve distinct alignments of one source; old source/index IDs can collide."""
    output=Path(output);units=[];seen=set()
    for source in paths:
        source=Path(source)
        index=json.loads((source/'index.json').read_text())
        if index.get('events'):
            raise ValueError('Speech-bank merge refuses banks containing events; preserve/export reviewed events separately')
        for original in index['units']:
            if not include_candidates and original.get('verified') is not True:continue
            audio=safe_path(source,original['file']).read_bytes()
            if hashlib.sha256(audio).hexdigest()!=original['sha256']:
                raise ValueError('Source-bank sample checksum mismatch')
            # Bind identity to actual bytes, phone labels, timing, review and voice.
            metadata={k:v for k,v in original.items() if k not in ('id','file')}
            digest=hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest()
            if digest in seen:continue
            seen.add(digest)
            name='units/'+digest+'.wav';destination=output/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists() and destination.read_bytes()!=audio:
                raise ValueError('Refusing conflicting merged sample overwrite')
            destination.write_bytes(audio)
            units.append({**original,'id':digest,'file':name})
    return units

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--alignments',type=Path)
    p.add_argument('--bank',type=Path,action='append',default=[],help='Merge existing banks without dropping alternate alignments')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--events',type=Path)
    p.add_argument('--include-candidates',action='store_true')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if not a.alignments and not a.bank:p.error('Supply --alignments or one or more --bank paths')
    units=merge_banks(a.bank,a.output,a.include_candidates);skipped=[]
    for path in sorted(a.alignments.rglob('*.json')) if a.alignments else []:
        data=json.loads(path.read_text())
        if not a.include_candidates and not all(data.get(k) is True for k in (
                'speaker_verified','transcript_verified','alignment_verified','emotion_verified')):
            skipped.append({'file':str(path),'reason':'missing explicit audio/speaker/transcript/emotion reviews'});continue
        if not a.include_candidates and not data.get('source_sha256'):
            skipped.append({'file':str(path),'reason':'review is not bound to a source checksum'});continue
        extracted=extract(data,a.output,reviewed_only=not a.include_candidates)
        units.extend(extracted if a.include_candidates else [u for u in extracted if u['verified']])
    events=export_events(json.loads(a.events.read_text()),a.output) if a.events else []
    receipt=write_index(a.output,units,events)
    receipt.update({'candidate_mode':a.include_candidates,'skipped':skipped,'events':len(events)})
    (a.output/'build-receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))
    print('========== DONE ==========',flush=True)

if __name__=='__main__':main()
