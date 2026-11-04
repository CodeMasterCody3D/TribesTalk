"""Plan only missing voice/style material; text coverage never certifies audio."""
import argparse
import hashlib
import json
from pathlib import Path
from phonetics import Lexicon,UnknownWords,normalize,select_gaps,transitions
from renderer import Renderer
from prep.expression_support import EMOTIONS

WARNING='Predicted material only. Validate generated words, actual phone alignment and acoustic quality; never promote review flags from text coverage.'

def plan_incremental(root,bank,lex,speakers,emotions,max_sentences=4,candidate_coverage=False,carrier='',sentences=None):
    from build_reports import candidates
    root=Path(root);bank=Path(bank)
    if not 1<=max_sentences<=60:raise ValueError('Select 1–60 sentences per voice/style')
    if not speakers or not emotions or any(e not in EMOTIONS for e in emotions):raise ValueError('Explicit known voices/styles required')
    renderer=Renderer(bank,lex,audition_unverified=candidate_coverage,bank_pronunciations=True)
    pool=list(dict.fromkeys(candidates() if sentences is None else sentences))
    target=set();unknown=[]
    for text in pool:
        try:target.update(transitions(lex.pronounce(text)['phones']))
        except UnknownWords as exc:unknown.append({'text':text,'unknown':exc.words})
    # Complete and failed-but-intact attempts both stay excluded: seed/context
    # are deterministic, so silently repeating the same bad take buys nothing.
    attempted={}
    manifest=root/'artifacts/pilot/pilot-jobs.json'
    for old in json.loads(manifest.read_text()) if manifest.exists() else []:
        if old.get('kind')!='speech':continue
        source=Path(old['source'])
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=old['sha256']:
            raise ValueError('Existing generated source missing/changed; restore before planning: '+old['id'])
        attempted.setdefault((old['speaker_id'],old['emotion']),set()).add(normalize(old['text'],lex.aliases))
    jobs=[];reports={}
    for speaker in speakers:
        if not speaker or Path(speaker).name!=speaker:raise ValueError('Directory-safe speaker ID required')
        ref=root/'artifacts/references-provisional'/f'{speaker}.wav'
        ref_sha=hashlib.sha256(ref.read_bytes()).hexdigest()
        receipt=json.loads(ref.with_suffix('.json').read_text())
        if ref_sha!=receipt['sha256']:raise ValueError('Reference checksum changed: '+speaker)
        ref_text=ref.with_suffix('.txt').read_text()
        if not ref_text.strip():raise ValueError('Empty reference transcript: '+speaker)
        for emotion in emotions:
            existing=renderer.available.get((speaker,emotion),set())
            missing_texts=[];supported=0;excluded=0
            for text in pool:
                renderer.warnings=[]
                try:
                    renderer.pronounce_for_bank(speaker,emotion,text);supported+=1
                except UnknownWords:continue
                except ValueError:
                    spoken=(carrier.strip()+' '+text).strip()
                    if normalize(spoken,lex.aliases) in attempted.get((speaker,emotion),set()):excluded+=1
                    else:missing_texts.append(spoken)
            selected=select_gaps(missing_texts,lex,target,existing,max_sentences=max_sentences)
            for item in selected['selected']:
                identity={'speaker':speaker,'emotion':emotion,'text':item['text'],
                          'instruction':EMOTIONS[emotion],'reference_sha256':ref_sha,'ref_text':ref_text}
                key=speaker+'_'+emotion+'_gap_'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]
                jobs.append({'id':key,'speaker_id':speaker,'emotion':emotion,'kind':'speech','text':item['text'],
                    'instruction':EMOTIONS[emotion],'predicted_phones':item['phones'],
                    'predicted_new_pairs':item['new_pairs'],'ref_audio_path':str(ref),'ref_text':ref_text,
                    'reference_sha256':ref_sha,'source':str(root/'artifacts/pilot'/(key+'.wav')),
                    'verified':False,'pronunciation_verified':False,'reference_verified':False})
            reports[speaker+'/'+emotion]={'workload_requests':len(pool),'supported_phone_paths':supported,
                'selected_sentences':len(selected['selected']),'existing_attempts_excluded':excluded,
                'canonical_target_pairs':len(target),'canonical_missing_before':['|'.join(x) for x in sorted(target-existing)],
                'predicted_uncovered_after':selected['uncovered'],'selection_rejections':selected['rejected'],
                'coverage_baseline':'UNREVIEWED CANDIDATES, private planning only' if candidate_coverage else 'reviewed units only',
                'audio_verified':False}
    return jobs,{'schema':1,'warning':WARNING,'bank_digest':renderer.digest,'candidate_coverage':candidate_coverage,
                 'carrier':carrier,'unknown_workload_items':unknown,'groups':reports}

def immutable_json(path,data):
    path=Path(path);text=json.dumps(data,indent=2)
    if path.exists() and path.read_text()!=text:raise ValueError('Refusing to overwrite changed job plan: '+str(path))
    if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)

def main():
    root=Path(__file__).resolve().parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--speaker',nargs='+',default=['Announcer'])
    p.add_argument('--emotions',nargs='+',choices=list(EMOTIONS),default=['neutral'])
    p.add_argument('--bank',type=Path);p.add_argument('--candidate-coverage',action='store_true')
    p.add_argument('--carrier',default='');p.add_argument('--max-sentences',type=int,default=4)
    p.add_argument('--out',type=Path);a=p.parse_args()
    lex=Lexicon.load(root/'artifacts/reports/cmudict.json',root/'pronunciation-overrides.json')
    if a.bank:
        if not a.out:p.error('Incremental planning requires an explicit NEW --out path')
        jobs,report=plan_incremental(root,a.bank,lex,a.speaker,a.emotions,a.max_sentences,a.candidate_coverage,a.carrier)
        immutable_json(a.out,jobs);immutable_json(a.out.with_suffix('.report.json'),report)
        print(json.dumps({'jobs':len(jobs),'file':str(a.out),'groups':report['groups'],'warning':WARNING},indent=2))
        return
    if len(a.speaker)!=1 or a.emotions!=['neutral'] or a.carrier or a.candidate_coverage:
        p.error('Multi-voice/style, carrier and incremental coverage options require --bank')
    # Preserve the original neutral set-cover command and IDs for existing work.
    speaker=a.speaker[0]
    plan=json.loads((root/'artifacts/reports'/f'gap-script-{speaker}.json').read_text())
    ref=root/'artifacts/references-provisional'/f'{speaker}.wav'
    if not ref.is_file():raise ValueError('Missing reference: '+speaker)
    jobs=[]
    for i,item in enumerate(plan['selected']):
        phones=lex.pronounce(item['text'])['phones']
        if phones!=item['phones']:raise ValueError('Pronunciation changed since set-cover selection')
        jobs.append({'id':f'{speaker}_neutral_gap_{i:03d}','speaker_id':speaker,'emotion':'neutral','kind':'speech',
             'text':item['text'],'predicted_phones':phones,'instruction':None,'ref_audio_path':str(ref),
             'ref_text':ref.with_suffix('.txt').read_text(),'verified':False,'pronunciation_verified':False})
    out=a.out or root/'artifacts'/f'gap-jobs-{speaker}.json'
    immutable_json(out,jobs)
    print(json.dumps({'jobs':len(jobs),'file':str(out),'target_pairs':plan['target_transition_count'],'warning':WARNING},indent=2))

if __name__=='__main__':main()
