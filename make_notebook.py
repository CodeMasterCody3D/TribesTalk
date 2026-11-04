"""Build a self-contained private Kaggle workflow, preserving the original notebook."""
import ast
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
files={str(p.relative_to(root)):p.read_text() for p in root.glob('*.py')
       if p.name not in ('bootstrap.py','inspect_sources.py','inspect_extra_sources.py','make_notebook.py')}
files.update({str(p.relative_to(root)):p.read_text() for p in (root/'prep').iterdir() if p.is_file()})
files['pronunciation-overrides.json']=(root/'pronunciation-overrides.json').read_text()
for name in ('toolchain-lock.json','requirements-breeze.lock.txt','rights-attestation.example.json'):
    files[name]=(root/name).read_text()
cells=[]
def md(s):cells.append({'cell_type':'markdown','metadata':{},'source':s})
def code(s):
    ast.parse(s)
    cells.append({'cell_type':'code','metadata':{},'source':s,'execution_count':None,'outputs':[]})
md('''# Tribes 2 sample-only voice engine
Private research/noncommercial preparation using Breeze TTS 2 on Kaggle.

The final renderer uses only PCM samples, a pronunciation dictionary and the
Python standard library. No neural inference or GPU is required at playback.

Run stages separately. Automatic ASR, speaker comparisons and alignment output
are candidates, not reviews. Training contains several speakers. Stock expressive
filenames and generated event cues are not trusted labels. Do not generate a large
gap corpus before listening to the small pilot. No passage guarantees every
English diphone or username. All exports remain private and noncommercial.
''')
code('''from pathlib import Path
import hashlib, json, subprocess, sys
ROOT=Path('/kaggle/temp/tribes2-voice-lab')
ROOT.mkdir(parents=True,exist_ok=True)
FILES='''+repr(files)+'''
for name,text in FILES.items():
    path=ROOT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_text()!=text:
        old=path.read_bytes()
        vault=ROOT/'code_vault'/f'{path.name}.{hashlib.sha256(old).hexdigest()[:16]}'
        vault.parent.mkdir(exist_ok=True); vault.write_bytes(old)
    path.write_text(text)
def run(*args):
    subprocess.run([str(x) for x in args],cwd=ROOT,check=True)
print('Materialized',len(FILES),'files')
run('nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv')
run('ffmpeg','-version')
''')
md('## Original audio: pinned download, preserved source and FFmpeg decode')
code("run(sys.executable,'-u',ROOT/'remote_prepare.py')")
md('## Transcription candidates: isolated environment and resumable ASR')
code("run(sys.executable,'-u',ROOT/'setup_remote.py','asr')\nASR=ROOT/'environments/asr/bin/python'\nrun(ASR,'-u',ROOT/'asr_entry.py','--asr','--all-asr','--skip-prep')\nrun(ASR,ROOT/'build_reports.py')")
md('''## Speaker comparisons and review
Compare training recordings individually with enrolled candidate voices.
Cosine scores are not identity probabilities. Review the original audio and
matching complete transcript, including any ASR errors, before certifying a source.
The game mission scripts identify Kenzie and Akanruth roles; acoustic assignments
and numbered-pack to in-game display-name mappings remain separate evidence.
''')
code("run(ASR,'-m','pip','install','kaldi-native-fbank==1.22.5')\nrun(ASR,'-u',ROOT/'speaker_audit.py')\nrun(ASR,ROOT/'pilot.py','references','--character-packs')")
md('''## Breeze pilot: three independent voices, one model load
These small auditions explicitly use provisional references, NOT production banks.
Listen to each reference and clone together; the process does not mark them verified.
Dependencies, model/source revisions, memory and generation times are saved.
''')
code('''RIGHTS_CONFIRMED=False  # Set only after the required permissions are actually secured.
permission_path=ROOT/'artifacts/permissions/rights-attestation.json'
if not permission_path.exists():
    if not RIGHTS_CONFIRMED:
        raise PermissionError('Breeze sections 5(c) and 5(d) require explicit performer consent and reference-recording rights; noncommercial use alone is not consent.')
    permission=json.loads((ROOT/'rights-attestation.example.json').read_text())
    permission['performer_consent_and_recording_rights_confirmed']=True
    permission['voice_ids']=['Announcer','TrainingFemale','BriefingMale',
        *(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),
        *(f'Derm{i}' for i in range(1,4)),'Bot1']
    permission_path.parent.mkdir(parents=True,exist_ok=True)
    permission_path.write_text(json.dumps(permission,indent=2))
run(sys.executable,'-u',ROOT/'setup_remote.py','breeze')
BREEZE=ROOT/'environments/breeze/bin/python'
run(BREEZE,'-u',ROOT/'pilot.py','generate','--speakers','Announcer','TrainingFemale','BriefingMale','--allow-provisional-reference')
''')
code('''from IPython.display import Audio,display
for voice in ('Announcer','TrainingFemale','BriefingMale'):
    print(voice,'ORIGINAL REFERENCE — provisional transcript/speaker review')
    display(Audio(filename=str(ROOT/'artifacts/references-provisional'/f'{voice}.wav')))
    print(voice,'BREEZE GENERATED AUDITION — unreviewed')
    display(Audio(filename=str(ROOT/'artifacts/pilot'/f'{voice}_neutral.wav')))
''')
md('''## Character-pack neutral pilots
The same short test sentence is rendered for the fourteen numbered packs.
This takes about four minutes on the tested T4, with one model load.
Numbered pack IDs are not verified in-game display-name mappings.
''')
code("CHARACTERS=[*(f'Male{i}' for i in range(1,6)),*(f'Fem{i}' for i in range(1,6)),*(f'Derm{i}' for i in range(1,4)),'Bot1']\nrun(BREEZE,'-u',ROOT/'pilot.py','generate','--speakers',*CHARACTERS,'--allow-provisional-reference')\nrun(ASR,'-u',ROOT/'validate_pilots.py')\nrun(sys.executable,ROOT/'build_auditions.py')")
md('''## Emotion and event auditions (review gate)
Five emotions use separate Voice Direction jobs. The documented English cues
are laugh, sigh, cough and clears throat in parentheses. Generated carrier speech
must be isolated away from a reviewed event; unsupported cues are never assumed.
Stock grunts, pain and cheers remain candidates until classified as spoken or wordless.
''')
code('''RUN_EXPRESSIVE_AUDITIONS=False  # compute control, not automatic quality approval
if RUN_EXPRESSIVE_AUDITIONS:
    VOICES=['Announcer','TrainingFemale','BriefingMale',*CHARACTERS]
    run(BREEZE,'-u',ROOT/'pilot.py','generate','--speakers',*VOICES,'--expressions','--no-events','--allow-provisional-reference')
    run(BREEZE,'-u',ROOT/'pilot.py','generate','--speakers','Announcer','--expressions','--allow-provisional-reference')
else:
    print('Optional style sweep is disabled: approximately 35–40 minutes for the non-neutral speech auditions on the tested T4.')
''')
md('''## Compact gap material
The declared announcement workload has 333 predicted stress-sensitive transitions.
The set-cover selector chose 32 sentences. This is not all English or all names.
The announcer-only neutral material takes about five minutes on the tested T4.
''')
code('''RUN_GAP_MATERIAL=False
run(sys.executable,ROOT/'gap_jobs.py','--speaker','Announcer')
if RUN_GAP_MATERIAL:
    run(BREEZE,'-u',ROOT/'pilot.py','generate','--speakers','Announcer',
        '--jobs',ROOT/'artifacts/gap-jobs-Announcer.json','--allow-provisional-reference')
run(ASR,'-u',ROOT/'validate_pilots.py')
''')
md('''## Phone alignment and candidate bank
MFA emits phone intervals. ASR word times must never be used as diphone boundaries.
Unknown pronunciations are refused before alignment. Review stops in waveform or
spectrogram: mark an anchor inside the closure, before the full protected release.
Stress variants are retained; allophones require explicit annotation. The automatic
bank is intentionally unverified, and the production renderer rejects it.
''')
code('''RUN_ALIGNMENT=False
if RUN_ALIGNMENT:
    run(sys.executable,'-u',ROOT/'setup_remote.py','align')
    run(sys.executable,ROOT/'make_alignment_jobs.py','--stock-announcer','--pilots')
    run(ASR,'-u',ROOT/'alignment.py','--jobs',ROOT/'artifacts/alignment-jobs.json',
        '--lexicon',ROOT/'artifacts/reports/cmudict.json','--overrides',ROOT/'pronunciation-overrides.json',
        '--out',ROOT/'artifacts/phone-alignment','--mfa',ROOT/'environments/mfa/bin/mfa')
else:
    print('Alignment stage ready; enable after the short pilot.')
''')
code('''if RUN_ALIGNMENT:
    run(sys.executable,ROOT/'render_auditions.py','--bank',ROOT/'artifacts/phone-alignment/candidate-bank','--bank-pronunciations')
    run(sys.executable,'-S',ROOT/'render_voice_matrix.py','--bank-pronunciations')
    run(ASR,ROOT/'build_reports.py')
''')
md('''## Sample-only runtime tests and measured fixture benchmark
The tests use synthetic fixtures, not a claim about voice naturalness or phonetic
coverage. Production rendering requires a bank whose actual reviews have passed.
Unknown words, missing units/events and missing emotion banks raise explicit errors.
Optional neutral/stress fallback must be selected explicitly and is reported.
''')
code("run(sys.executable,ROOT/'test_engine.py')\nrun(ASR,ROOT/'test_preparation.py')\nrun(sys.executable,ROOT/'test_companion.py')\nprint((ROOT/'test-results.json').read_text())")
md('''## Export durable private artifacts
The archive excludes environments and model weights. Stock and decoded audio,
reports, references, pilot WAVs and sample banks are included. The VL2 packager
only accepts reviewed rendered phrases. Every native client must have the bytes;
server-side filenames do not transfer audio. Live client playback is not certified.
''')
code('''run(sys.executable,ROOT/'build_auditions.py')
run(sys.executable,ROOT/'build_event_auditions.py')
run(sys.executable,ROOT/'export_review.py')
run(sys.executable,ROOT/'record_environment.py')
run(sys.executable,ROOT/'archive_artifacts.py')
print('/kaggle/working/tribes2-voice-artifacts.tar.gz')
print('========== DONE ==========')
''')
nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','language':'python','display_name':'Python 3'},
     'kaggle':{'accelerator':'gpu','isInternetEnabled':True,'language':'python','sourceType':'notebook'}},'cells':cells}
out=root/'workflow';out.mkdir(exist_ok=True)
(out/'tribes2_sample_engine.ipynb').write_text(json.dumps(nb,indent=1))
(out/'kernel-metadata.json').write_text(json.dumps({'id':'codemastercody3d/tribes2-sample-engine-workflow',
    'title':'Tribes 2 Sample Engine Workflow','code_file':'tribes2_sample_engine.ipynb','language':'python',
    'kernel_type':'notebook','is_private':True,'enable_gpu':True,'enable_internet':True,
    'dataset_sources':[],'competition_sources':[],'kernel_sources':[]},indent=2))
print('Built',len(cells),'cells,',len(files),'embedded files; NOT pushed or executed here.')
