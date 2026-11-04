"""Turn a defined set-cover script into explicit Breeze candidate-material jobs."""
import argparse
import json
from pathlib import Path
from phonetics import Lexicon

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--speaker',default='Announcer');a=p.parse_args()
plan=json.loads((root/'artifacts/reports'/f'gap-script-{a.speaker}.json').read_text())
lex=Lexicon.load(root/'artifacts/reports/cmudict.json',root/'pronunciation-overrides.json')
ref=root/'artifacts/references-provisional'/f'{a.speaker}.wav'
assert ref.is_file()
jobs=[]
for i,item in enumerate(plan['selected']):
    phones=lex.pronounce(item['text'])['phones']
    if phones!=item['phones']:raise ValueError('Pronunciation changed since set-cover selection')
    jobs.append({'id':f'{a.speaker}_neutral_gap_{i:03d}','speaker_id':a.speaker,'emotion':'neutral','kind':'speech',
        'text':item['text'],'predicted_phones':phones,'instruction':None,'ref_audio_path':str(ref),
        'ref_text':ref.with_suffix('.txt').read_text(),'verified':False,'pronunciation_verified':False})
out=root/'artifacts'/f'gap-jobs-{a.speaker}.json';out.write_text(json.dumps(jobs,indent=2))
print(json.dumps({'jobs':len(jobs),'file':str(out),'target_pairs':plan['target_transition_count'],
    'warning':'Predicted dictionary coverage only. Validate generated words and phone alignment before extraction.'},indent=2))
