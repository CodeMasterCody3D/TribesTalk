"""Side-by-side review candidates; never overwrite the human source-review table."""
import csv
import json
from pathlib import Path
import re

root=Path(__file__).resolve().parent
out=root/'artifacts/reports';out.mkdir(parents=True,exist_ok=True)
with (root/'artifacts/review.csv').open() as f:original=list(csv.DictReader(f))
asr={r['path']:r for r in map(json.loads,(root/'artifacts/asr_candidates.jsonl').read_text().splitlines())}
audit_path=root/'artifacts/speaker-audit/speaker-comparisons.json'
audit={r['path']:r for r in json.loads(audit_path.read_text())['records']} if audit_path.exists() else {}
def comparable(s):return re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?",s.casefold())
rows=[]
for row in original:
    machine=asr.get(row['path'],{})
    speaker=audit.get(row['path'],{})
    top=speaker.get('top_matches',[])
    rows.append({'path':row['path'],'pack_id':row['group'],'reviewed_speaker_id':row['speaker_id'] if row['speaker_verified']=='true' else '',
        'speaker_verified':row['speaker_verified'],'speaker_match_candidate':top[0][0] if top else '',
        'speaker_cosine_not_probability':top[0][1] if top else '',
        'speaker_window_disagreement':speaker.get('window_disagreement',''),
        'stock_transcript_hint':row['text'],'ASR_candidate':machine.get('text',''),
        'hint_ASR_disagree':bool(row['text'] and comparable(row['text'])!=comparable(machine.get('text',''))),
        'ASR_empty':not bool(machine.get('text','').strip()),'transcript_verified':row['transcript_verified'],
        'notes':row['notes']})
with (out/'transcript-and-speaker-candidates.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
registry=out/'voice-registry.json'
if not registry.exists():
    ids=[*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),*(f'Derm{i}' for i in range(1,4)),
         'Bot1','Announcer','TrainingFemale','BriefingMale']
    values=[]
    for speaker in ids:
        values.append({'id':speaker,'in_game_display_name':None,'display_mapping_verified':False,
            'speaker_acoustic_verified':False,
            'canonical_role_name_in_mission_source':{'TrainingFemale':'Kenzie','BriefingMale':'Akanruth'}.get(speaker),
            'role_source':'Training1.mis briefing text; TrainingGui.cs associates briefing WAV sequence' if speaker in ('TrainingFemale','BriefingMale') else None,
            'mapping_evidence':[],'notes':'Numbered asset-pack ID is not an authenticated in-game display-name mapping.'})
    registry.write_text(json.dumps({'voices':values,
        'secondary_display_name_list_source':'https://tribes.fandom.com/wiki/Voice_Packs',
        'secondary_list_not_a_numbered_mapping':True,
        'search_limitations':'SearXNG queries had blocked/rate-limited Brave, DuckDuckGo and Wikipedia engines. Search was not exhaustive.',
        'warning':'Do not map names from list order or assign all 334 training WAVs to one voice.'},indent=2))
print(json.dumps({'rows':len(rows),'ASR_empty':sum(r['ASR_empty'] for r in rows),
                  'hint_ASR_disagreements':sum(r['hint_ASR_disagree'] for r in rows),
                  'human_source_review_unchanged':True,'display_mappings_verified':0},indent=2))
print('========== DONE ==========',flush=True)
