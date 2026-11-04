"""Select a small, explicit phone-alignment smoke; reject unknown pronunciations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from phonetics import Lexicon,UnknownWords

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--pilots',action='store_true');p.add_argument('--stock-announcer',action='store_true')
p.add_argument('--stock-character-packs',action='store_true')
p.add_argument('--validation',type=Path,action='append',default=[])
p.add_argument('--out',type=Path,default=root/'artifacts/alignment-jobs.json')
a=p.parse_args();jobs=[];rejected=[]
lex=Lexicon.load(root/'artifacts/reports/cmudict.json',root/'pronunciation-overrides.json')
if a.stock_announcer:
    rows={r['path']:r for r in map(json.loads,(root/'artifacts/asr_candidates.jsonl').read_text().splitlines())}
    for name in ('ANN.10sec.WAV','ANN.15sec.WAV','ANN.30.WAV','ANN.60.WAV','ANN.gameover.WAV',
                 'ANN.closegame_01.WAV','ANN.closegame_03.WAV','ANN.closegame_04.WAV',
                 'ANN.match_begins.WAV','ANN.prepare.WAV','ANN.ib.WAV','ANN.oob.WAV'):
        path='voice/Announcer/'+name
        jobs.append({'id':name,'source':str(root/'artifacts/pcm24k'/path),'text':rows[path]['text'],
            'speaker_id':'Announcer','emotion':'neutral','kind':'speech','verified':False,
             'speaker_verified':False,'transcript_verified':False})
if a.stock_character_packs:
    sys.path.insert(0,str(root/'prep'))
    from voice_lab import transcript_seeds
    from expression_support import STOCK_CANDIDATES
    hints=transcript_seeds()
    rows=map(json.loads,(root/'artifacts/asr_candidates.jsonl').read_text().splitlines())
    packs={*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),
           *(f'Derm{i}' for i in range(1,4)),'Bot1'}
    def words(text):return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?",text.casefold())
    for row in rows:
        path=Path(row['path']);parts=path.parts
        if len(parts)!=3 or parts[0]!='voice' or parts[1] not in packs:continue
        stem=path.stem.casefold()
        # Expressive/nonverbal stock files stay in their review lane, not neutral speech.
        if stem in STOCK_CANDIDATES or stem.startswith('avo.'):continue
        hint=hints.get(stem)
        if not hint or not words(row['text']) or words(hint)!=words(row['text']):continue
        jobs.append({'id':'stock_'+parts[1]+'_'+stem,'source':str(root/'artifacts/pcm24k'/path),
                     'text':row['text'],'speaker_id':parts[1],'emotion':'neutral','kind':'speech',
                     'verified':False,'speaker_verified':False,'transcript_verified':False,
                     'selection':'stock hint and machine words agree; acoustic/emotion review still required'})
if a.pilots:
    validations={r['id']:r for r in json.loads((root/'artifacts/pilot/asr-validation.json').read_text())}
    for path in a.validation:
        for record in json.loads(path.read_text()):
            if record['id'] in validations and validations[record['id']]!=record:
                raise ValueError('Conflicting validation for '+record['id'])
            validations[record['id']]=record
    for job in json.loads((root/'artifacts/pilot/pilot-jobs.json').read_text()):
        if job['kind']!='speech':continue
        checked=validations.get(job['id'],{})
        digest=hashlib.sha256(Path(job['source']).read_bytes()).hexdigest()
        if (not job.get('complete_by_frame_guard') or checked.get('exact_normalized_words') is not True
                or checked.get('source_sha256')!=digest):
            rejected.append({'id':job['id'],'reason':'missing/mismatched/failed generated-word validation'})
            continue
        jobs.append(job)
accepted=[]
for job in jobs:
    try:lex.pronounce(job['text']);accepted.append(job)
    except UnknownWords as e:rejected.append({'id':job['id'],'unknown':e.words})
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(accepted,indent=2))
a.out.with_suffix('.rejected.json').write_text(json.dumps(rejected,indent=2))
if not accepted:raise ValueError('No alignable jobs')
print(json.dumps({'accepted':len(accepted),'rejected':rejected,'jobs':str(a.out)},indent=2))
