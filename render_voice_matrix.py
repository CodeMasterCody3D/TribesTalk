"""Audition every voice/style using samples only; refusals are part of the report."""
import argparse
import html
import json
from pathlib import Path
from phonetics import Lexicon
from renderer import Renderer


def main():
    root=Path(__file__).resolve().parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bank',type=Path,default=root/'artifacts/phone-alignment/candidate-bank')
    p.add_argument('--text',default='Defend the generator!')
    p.add_argument('--bank-pronunciations',action='store_true')
    p.add_argument('--tag',default='voice-matrix')
    p.add_argument('--check-workload',action='store_true',help='Check declared workload phone paths only, not audio quality')
    a=p.parse_args()
    lex=Lexicon.load(root/'artifacts/reports/cmudict.json',root/'pronunciation-overrides.json')
    if Path(a.tag).name!=a.tag:raise ValueError('Directory-safe tag required')
    renderer=Renderer(a.bank,lex,audition_unverified=True,bank_pronunciations=a.bank_pronunciations)
    voices=[*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),
            *(f'Derm{i}' for i in range(1,4)),'Bot1','Announcer','TrainingFemale','BriefingMale']
    emotions=('neutral','angry','sad','excited','calm')
    out=root/'artifacts'/a.tag;out.mkdir(parents=True,exist_ok=True)
    if a.check_workload:
        from build_reports import candidates
        sentences=candidates();groups={}
        for voice in voices:
            for emotion in emotions:
                supported=[];missing=[]
                for text in sentences:
                    renderer.warnings=[]
                    try:
                        renderer.pronounce_for_bank(voice,emotion,text)
                        supported.append(text)
                    except ValueError as exc:
                        missing.append({'text':text,'error':str(exc)})
                groups[voice+'/'+emotion]={'requests':len(sentences),'supported_phone_paths':len(supported),
                    'supported':supported,'missing':missing}
        report={'scope':'Declared announcement workload only; phone-path feasibility, NOT audio/identity/emotion/native-playback review',
                'bank':str(a.bank),'bank_digest':renderer.digest,'groups':groups,'verified':False}
        (out/'results.json').write_text(json.dumps(report,indent=2))
        print(json.dumps({key:{'requests':x['requests'],'supported_phone_paths':x['supported_phone_paths']}
                          for key,x in groups.items()},indent=2),flush=True)
        print('========== DONE ==========',flush=True)
        return
    rows=[]
    page=['<!doctype html><meta charset="utf-8"><title>Sample-only voice matrix</title>',
          '<h1>Sample-only voice matrix</h1><p>Private candidate auditions. No neural runtime. '
          'Speaker identities, emotions and boundaries are NOT certified. Missing units are refused, '
          'not replaced by a different speaker, emotion or pronunciation.</p>',
          '<p>Text: '+html.escape(a.text)+'</p>']
    for voice in voices:
        page.append('<h2>'+html.escape(voice)+'</h2>')
        for emotion in emotions:
            key=voice+'_'+emotion
            row={'speaker_id':voice,'emotion':emotion,'text':a.text,'verified':False,
                 'bank_pronunciations':a.bank_pronunciations}
            page.append('<h3>'+html.escape(emotion)+'</h3>')
            try:
                text=a.text if emotion=='neutral' else f'[{emotion}]{a.text}[/{emotion}]'
                result=renderer.render(voice,text,out/(key+'.wav'))
                row.update(result,file=key+'.wav',status='unverified_audition')
                page.append('<audio controls preload="none" src="'+key+'.wav"></audio>')
            except ValueError as exc:
                row.update(status='refused',error=str(exc))
                page.append('<p>REFUSED: '+html.escape(str(exc))+'</p>')
            rows.append(row)
    (out/'results.json').write_text(json.dumps(rows,indent=2))
    (out/'index.html').write_text('\n'.join(page))
    print(json.dumps({'requests':len(rows),'rendered':sum(r['status']=='unverified_audition' for r in rows),
                      'refused':[{'speaker_id':r['speaker_id'],'emotion':r['emotion'],'error':r['error']}
                                 for r in rows if r['status']=='refused'],
                      'verified':0,'directory':str(out)},indent=2),flush=True)
    print('========== DONE ==========',flush=True)


if __name__=='__main__':main()
