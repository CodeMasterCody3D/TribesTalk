"""Remote dictionary export, per-speaker predicted coverage and compact script selection."""
from pathlib import Path
import argparse
import csv
import json
import importlib.metadata
import sys
from phonetics import Lexicon,coverage,select_gaps,transitions,UnknownWords

ROOT=Path(__file__).resolve().parent
EXPECTED=[*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),
          *(f'Derm{i}' for i in range(1,4)),'Bot1','Announcer','TrainingFemale','BriefingMale']

def candidates():
    subjects=['Cody','The blue team','The red team','Our heavy armor','Your scout','The enemy',
              'A quiet warrior','The administrator','Five brave soldiers','The commander']
    verbs=['will defend','must repair','should protect','can attack','will approach','must watch']
    objects=['the generator','our flag','the eastern tower','the base','the vehicle station','the bridge',
             'the sensor','the command center','the launch pad']
    lines=[f'{s} {v} {o}.' for s in subjects for v in verbs for o in objects]
    lines += ['Welcome to the server, Cody!','Prepare for battle.','The match begins in sixty seconds.',
              'Your username pronunciation requires an override.','Please join the blue team.',
              'Shields are down. Charge the hill!','Watch the ridge, then cross the valley.',
              'Five quick scouts jump past three heavy tanks.','A veteran warrior quietly repairs the damaged vehicle.',
              'Stop shooting. Check your targets.','The administrator has banned player forty two.',
              'Server maintenance begins in two minutes.','The final score is twenty three to nineteen.',
              'Cody, defend the generator!','A fresh squad has reached the northern entrance.']
    return lines

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bank',type=Path,action='append')
    args=ap.parse_args()
    import cmudict
    out=ROOT/'artifacts/reports';out.mkdir(parents=True,exist_ok=True)
    entries=cmudict.dict()
    licenses=[]
    dist=importlib.metadata.distribution('cmudict')
    for path in dist.files or []:
        if 'license' in str(path).casefold() and dist.locate_file(path).is_file():
            licenses.append(str(path)+'\n'+dist.locate_file(path).read_text())
    if not licenses:raise RuntimeError('CMUdict license missing; do not export unattributed dictionary')
    (out/'CMUDICT-LICENSE.txt').write_text('\n\n'.join(licenses))
    (out/'cmudict.json').write_text(json.dumps(entries,separators=(',',':')))
    lex=Lexicon.load(out/'cmudict.json',ROOT/'pronunciation-overrides.json')
    with (ROOT/'artifacts/review.csv').open() as f:rows=list(csv.DictReader(f))
    asr={}
    path=ROOT/'artifacts/asr_candidates.jsonl'
    if path.exists():asr={r['path']:r for r in map(json.loads,path.read_text().splitlines())}
    for r in rows:
        if not r['text'] and r['path'] in asr:
            r['text']=asr[r['path']]['text']
        if r['group']=='Training' and not r['speaker_id']:
            # Never collapse all 334 training recordings into a fictional single speaker.
            r['speaker_id']='UNASSIGNED:'+r['path']
        if r['group']=='Announcer' and not Path(r['path']).name.startswith('ANN.'):
            r['speaker_id']='UNASSIGNED:'+r['path']
    bank_paths=args.bank or [ROOT/'artifacts/stock-alignment/candidate-bank/index.json',
                            ROOT/'artifacts/phone-alignment/candidate-bank/index.json']
    units={}
    for path in bank_paths:
        if path.exists():
            for u in json.loads(path.read_text())['units']:
                units[(u['speaker_id'],u['emotion'],u['id'])]=u
    report=coverage(rows,lex,units.values())
    (out/'coverage-predicted.json').write_text(json.dumps(report,indent=2))
    status=[]
    for speaker in EXPECTED:
        r=report.get(speaker+'/neutral',{})
        status.append({'speaker_id':speaker,'display_name_verified':False,
            'transcript_predicted_transitions':len(r.get('predicted_transitions',{})),
            'verified_usable_transitions':len(r.get('verified_usable_transitions',[])),
            'emotions':{e:'not yet validated' for e in ('neutral','angry','sad','excited','calm')},
            'assignment':'pending acoustic/source review' if speaker in ('TrainingFemale','BriefingMale') else 'asset pack id, not certified display-name mapping'})
    (out/'voice-status.json').write_text(json.dumps(status,indent=2))
    sentences=candidates()
    # Target = declared Tribes announcement workload. This is NOT all English diphones.
    target=set()
    for s in sentences:
        try:target.update(transitions(lex.pronounce(s)['phones']))
        except UnknownWords:pass
    candidate_coverage={}
    for unit in units.values():
        key=unit['speaker_id']+'/'+unit['emotion']
        r=candidate_coverage.setdefault(key,{'unit_count':0,'pairs':set(),'verified_pairs':set(),
                                             'unreviewed_stop_units':0})
        r['unit_count']+=1;r['pairs'].add(tuple(unit['phones']))
        if unit.get('verified') is True:r['verified_pairs'].add(tuple(unit['phones']))
        if unit.get('release_safe') is not True:r['unreviewed_stop_units']+=1
    audio_report={k:{'unit_count':r['unit_count'],'candidate_transition_count':len(r['pairs']),
                     'candidate_transitions':['|'.join(p) for p in sorted(r['pairs'])],
                     'verified_transition_count':len(r['verified_pairs']),
                     'candidate_target_covered':len(r['pairs']&target),
                     'candidate_target_missing':['|'.join(p) for p in sorted(target-r['pairs'])],
                     'unreviewed_stop_units':r['unreviewed_stop_units']} for k,r in candidate_coverage.items()}
    (out/'coverage-audio-candidates.json').write_text(json.dumps(audio_report,indent=2))
    for speaker in EXPECTED:
        existing=[tuple(x.split('|')) for x in report.get(speaker+'/neutral',{}).get('verified_usable_transitions',[])]
        r=select_gaps(sentences,lex,target,existing,max_sentences=60)
        r.update({'speaker_id':speaker,'target_transition_count':len(target),
                  'baseline':'verified usable audio only; hints do not reduce gaps'})
        (out/f'gap-script-{speaker}.json').write_text(json.dumps(r,indent=2))
    (out/'gap-candidates.txt').write_text('\n'.join(sentences)+'\n')
    print(json.dumps({'rows':len(rows),'asr_candidates':len(asr),'reports':len(report),
                      'voices':len(status),'target_transition_count':len(target)},indent=2))
    print('========== DONE ==========',flush=True)

if __name__=='__main__':main()
