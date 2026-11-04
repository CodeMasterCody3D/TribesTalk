"""Real sample-only smoke with unverified units explicitly restricted to audition."""
import json
import argparse
from pathlib import Path
from renderer import Renderer,MissingUnit
from phonetics import Lexicon,UnknownWords

root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--bank',type=Path,default=root/'artifacts/stock-alignment/candidate-bank')
p.add_argument('--speaker',default='Announcer')
p.add_argument('--bank-pronunciations',action='store_true')
p.add_argument('--tag',default='stitch-auditions');a=p.parse_args()
lex=Lexicon.load(root/'artifacts/reports/cmudict.json',root/'pronunciation-overrides.json')
if Path(a.tag).name!=a.tag:raise ValueError('Directory-safe tag required')
out=root/'artifacts'/a.tag;out.mkdir(parents=True,exist_ok=True)
bank=a.bank
renderer=Renderer(bank,lex,audition_unverified=True,bank_pronunciations=a.bank_pronunciations)
results=[]
for i,text in enumerate(('Game over. Prepare yourselves!', 'Match begins now. Game over.',
                         'You are out of bounds! Prepare yourselves.', 'This looks like a real battle.',
                         'Welcome to the server, Cody!', 'Welcome to the server, Cody. Defend the generator!')):
    try:
        path=out/f'announcer_{i:02d}.wav'
        metadata=renderer.render(a.speaker,text,path,out/'phrase-cache')
        metadata.update({'text':text,'file':str(path),'verified':False,'mode':'unverified candidate audition only'})
        results.append(metadata)
        print(json.dumps({'text':text,'audio_seconds':metadata['audio_seconds'],
                          'wall_seconds':metadata['wall_seconds'],'warnings':len(metadata['warnings'])}),flush=True)
    except (MissingUnit,UnknownWords,ValueError) as e:
        results.append({'text':text,'error':str(e),'verified':False})
        print('EXPLICIT REFUSAL:',text,str(e),flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2))
(out/'phrase-candidates.json').write_text(json.dumps([
    {'file':r['file'],'sha256':r['output_sha256'],'text':r['text'],'speaker_id':a.speaker,'verified':False}
    for r in results if 'file' in r],indent=2))
print('========== DONE ==========',flush=True)
